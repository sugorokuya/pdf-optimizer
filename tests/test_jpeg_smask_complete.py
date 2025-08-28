#!/usr/bin/env python3

import fitz
from PIL import Image
import io
import os

def complete_jpeg_smask_separation(doc, page, xref, img, quality=70, verbose=True):
    """
    完全なJPEG+SMask分離処理
    両方ともJPEG形式で保存してPNG膨張を完全回避
    """
    try:
        if img.mode not in ('RGBA', 'LA'):
            return False, "Not RGBA/LA image"
            
        # SMask参照を取得
        smask_ref = doc.xref_get_key(xref, "SMask")
        if not smask_ref or smask_ref in [None, 'null', ('null', 'null')]:
            return False, "No SMask found"
            
        # SMask xrefを抽出
        smask_xref = None
        if isinstance(smask_ref, tuple) and len(smask_ref) >= 2:
            smask_str = smask_ref[1]
            if ' 0 R' in smask_str:
                smask_xref = int(smask_str.split(' 0 R')[0])
                
        if not smask_xref:
            return False, "Invalid SMask xref"
            
        # RGBA分離
        if img.mode == 'RGBA':
            r, g, b, a = img.split()
            rgb_img = Image.merge('RGB', (r, g, b))
            alpha_img = a
        elif img.mode == 'LA':
            l, a = img.split()
            rgb_img = Image.merge('RGB', (l, l, l))
            alpha_img = a
            
        # 1. RGB部分をJPEGで保存
        jpeg_output = io.BytesIO()
        rgb_img.save(jpeg_output, format='JPEG', quality=quality, optimize=True, progressive=True)
        new_jpeg_data = jpeg_output.getvalue()
        
        # 2. Alpha部分もJPEGで保存（グレースケール）
        # アルファチャンネルをRGBに変換してJPEG保存
        alpha_rgb = Image.merge('RGB', (alpha_img, alpha_img, alpha_img))
        alpha_jpeg_output = io.BytesIO()
        alpha_rgb.save(alpha_jpeg_output, format='JPEG', quality=quality, optimize=True)
        new_alpha_data = alpha_jpeg_output.getvalue()
        
        # 3. 元画像をJPEGで置換
        page.replace_image(xref, stream=new_jpeg_data)
        
        # 4. SMaskをJPEGで置換
        page.replace_image(smask_xref, stream=new_alpha_data)
        
        # 5. オブジェクト属性を更新
        # JPEG画像のオブジェクト属性
        doc.xref_set_key(xref, "Width", str(rgb_img.width))
        doc.xref_set_key(xref, "Height", str(rgb_img.height))
        # ColorSpaceとFilterは既存のままにする（変更すると破損の可能性）
        
        # SMaskのオブジェクト属性  
        doc.xref_set_key(smask_xref, "Width", str(alpha_img.width))
        doc.xref_set_key(smask_xref, "Height", str(alpha_img.height))
        # SMaskも既存設定を維持
        
        if verbose:
            print(f"        完全JPEG分離: RGB {len(new_jpeg_data):,}b + Alpha {len(new_alpha_data):,}b")
            
        return True, f"Success: {len(new_jpeg_data)} + {len(new_alpha_data)} bytes"
        
    except Exception as e:
        if verbose:
            print(f"        JPEG完全分離エラー: {e}")
        return False, f"Error: {e}"

def test_complete_jpeg_smask():
    """完全JPEG+SMask分離のテスト"""
    
    print("=== 完全JPEG+SMask分離テスト ===")
    
    doc = fitz.open('smasked-image-sample.pdf')
    page = doc[0]
    images = page.get_images()
    
    # テスト用画像選択（小さめの画像）
    test_cases = []
    for img_info in images:
        xref = img_info[0]
        try:
            base_image = doc.extract_image(xref)
            if (base_image.get('ext') == 'jpeg' and 
                base_image['width'] <= 800 and base_image['height'] <= 800):
                
                # SMask確認
                smask_ref = doc.xref_get_key(xref, "SMask")
                if smask_ref and smask_ref not in [None, 'null', ('null', 'null')]:
                    test_cases.append((xref, base_image))
                    if len(test_cases) >= 3:  # 3つまで
                        break
        except:
            continue
            
    print(f"テスト対象: {len(test_cases)}個の画像")
    
    success_count = 0
    total_savings = 0
    
    for i, (xref, base_image) in enumerate(test_cases):
        print(f"\\n{i+1}. xref{xref} ({base_image['width']}x{base_image['height']})")
        
        # 元のサイズ確認
        try:
            original_stream_size = len(doc.xref_stream(xref))
            print(f"    元PDF内サイズ: {original_stream_size:,} bytes")
        except:
            original_stream_size = 0
            
        # RGBA画像を構築
        try:
            # combine_jpeg_with_smask の簡易版
            jpeg_img = Image.open(io.BytesIO(base_image['image']))
            
            # SMask取得
            smask_ref = doc.xref_get_key(xref, "SMask")
            smask_xref = int(smask_ref[1].split(' 0 R')[0])
            smask_image = doc.extract_image(smask_xref)
            smask_img = Image.open(io.BytesIO(smask_image['image']))
            
            # サイズ調整
            if jpeg_img.size != smask_img.size:
                smask_img = smask_img.resize(jpeg_img.size, Image.Resampling.LANCZOS)
                
            # RGBA合成
            if jpeg_img.mode != 'RGB':
                jpeg_img = jpeg_img.convert('RGB')
            if smask_img.mode != 'L':
                smask_img = smask_img.convert('L')
                
            r, g, b = jpeg_img.split()
            rgba_img = Image.merge('RGBA', (r, g, b, smask_img))
            
            # リサイズ（テスト用）
            small_img = rgba_img.resize((min(rgba_img.width//4, 128), min(rgba_img.height//4, 128)), 
                                      Image.Resampling.LANCZOS)
            
            # 完全JPEG分離実行
            success, result = complete_jpeg_smask_separation(
                doc, page, xref, small_img, quality=70, verbose=True
            )
            
            if success:
                success_count += 1
                
                # 分離後のサイズ確認
                try:
                    new_stream_size = len(doc.xref_stream(xref))
                    savings = original_stream_size - new_stream_size
                    total_savings += savings
                    
                    if original_stream_size > 0:
                        reduction = (savings / original_stream_size) * 100
                        print(f"    分離後サイズ: {new_stream_size:,} bytes ({reduction:.1f}% 削減)")
                except:
                    pass
            else:
                print(f"    分離失敗: {result}")
                
        except Exception as e:
            print(f"    処理エラー: {e}")
    
    # 結果保存とテスト
    test_output = "complete_jpeg_smask_test.pdf"
    doc.save(test_output, deflate=True)
    
    # 最終結果
    original_size = os.path.getsize('smasked-image-sample.pdf')
    test_size = os.path.getsize(test_output)
    total_reduction = (1 - test_size / original_size) * 100
    
    print(f"\\n=== 最終結果 ===")
    print(f"成功した分離: {success_count}/{len(test_cases)}")
    print(f"元ファイル: {original_size:,} bytes ({original_size/1024/1024:.1f} MB)")
    print(f"分離後: {test_size:,} bytes ({test_size/1024/1024:.1f} MB)")
    print(f"総削減率: {total_reduction:.1f}%")
    
    if total_savings > 0:
        print(f"推定削減量: {total_savings:,} bytes")
    
    # 内部検証
    print(f"\\n=== 内部検証 ===")
    doc2 = fitz.open(test_output)
    page2 = doc2[0]
    images2 = page2.get_images()
    
    for i, img_info in enumerate(images2[:5]):
        xref = img_info[0]
        try:
            img_data = doc2.extract_image(xref)
            stream_size = len(doc2.xref_stream(xref))
            expansion = stream_size / len(img_data['image']) if len(img_data['image']) > 0 else 0
            print(f"  画像{i+1} xref{xref}: {img_data['width']}x{img_data['height']} " +
                  f"extract:{len(img_data['image']):,}b stream:{stream_size:,}b ({expansion:.1f}倍)")
        except Exception as e:
            print(f"  画像{i+1} xref{xref}: エラー - {e}")
    
    doc2.close()
    doc.close()
    
    print(f"\\nテストファイル: {test_output}")

if __name__ == "__main__":
    test_complete_jpeg_smask()