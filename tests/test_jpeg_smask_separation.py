#!/usr/bin/env python3

import fitz
from PIL import Image
import io
import os

def separate_jpeg_smask(doc, xref, quality=50, verbose=True):
    """
    JPEG+SMask画像を分離して、JPEG(RGB) + SMask(グレースケール)として保存
    """
    try:
        # 1. 元のJPEG+SMask情報取得
        smask_ref = doc.xref_get_key(xref, "SMask")
        if not smask_ref or smask_ref in [None, 'null', ('null', 'null')]:
            return False, "No SMask found"
            
        # 2. JPEG画像とSMaskを取得
        jpeg_dict = doc.extract_image(xref)
        if not jpeg_dict or jpeg_dict.get('ext') != 'jpeg':
            return False, "Not a JPEG image"
            
        # SMask画像取得
        smask_xref = None
        if isinstance(smask_ref, tuple) and len(smask_ref) >= 2:
            # ('xref', '449 0 R') 形式の処理
            smask_str = smask_ref[1]
            if ' 0 R' in smask_str:
                smask_xref = int(smask_str.split(' 0 R')[0])
        
        if not smask_xref:
            return False, "Invalid SMask reference"
            
        try:
            smask_dict = doc.extract_image(smask_xref)
            if not smask_dict:
                return False, "Could not extract SMask"
        except:
            return False, "SMask extraction failed"
            
        # 3. RGBA画像に合成（処理用）
        jpeg_img = Image.open(io.BytesIO(jpeg_dict['image']))
        smask_img = Image.open(io.BytesIO(smask_dict['image']))
        
        # サイズ調整
        if jpeg_img.size != smask_img.size:
            smask_img = smask_img.resize(jpeg_img.size, Image.Resampling.LANCZOS)
            
        # SMaskをグレースケールに変換
        if smask_img.mode != 'L':
            smask_img = smask_img.convert('L')
            
        # RGBA合成
        if jpeg_img.mode != 'RGB':
            jpeg_img = jpeg_img.convert('RGB')
            
        rgba_img = Image.new('RGBA', jpeg_img.size)
        rgba_img.paste(jpeg_img, (0, 0))
        
        # アルファチャンネル設定
        r, g, b = rgba_img.split()[:3]
        rgba_img = Image.merge('RGBA', (r, g, b, smask_img))
        
        # 4. 分離保存の準備
        # RGB部分をJPEGとして保存
        rgb_img = rgba_img.convert('RGB')
        jpeg_output = io.BytesIO()
        rgb_img.save(jpeg_output, format='JPEG', quality=quality, optimize=True)
        new_jpeg_data = jpeg_output.getvalue()
        
        # Alpha部分をグレースケール画像として保存
        alpha_channel = rgba_img.split()[3]  # A channel
        smask_output = io.BytesIO()
        alpha_channel.save(smask_output, format='PNG', optimize=True, compress_level=9)
        new_smask_data = smask_output.getvalue()
        
        if verbose:
            orig_jpeg_size = len(jpeg_dict['image'])
            orig_smask_size = len(smask_dict['image'])
            print(f"    分離結果:")
            print(f"      元JPEG: {orig_jpeg_size:,} bytes → 新JPEG: {len(new_jpeg_data):,} bytes")
            print(f"      元SMask: {orig_smask_size:,} bytes → 新SMask: {len(new_smask_data):,} bytes")
            
        return True, (new_jpeg_data, new_smask_data, smask_xref)
        
    except Exception as e:
        return False, f"Error: {e}"

def test_jpeg_smask_separation():
    """smasked-image-sample.pdfでJPEG+SMask分離テスト"""
    
    print("=== JPEG+SMask分離テスト ===")
    
    doc = fitz.open('smasked-image-sample.pdf')
    page = doc[0]
    images = page.get_images()
    
    # テスト対象画像を選択（最初の3つ）
    test_images = []
    for i, img_info in enumerate(images[:5]):
        xref = img_info[0]
        try:
            base_image = doc.extract_image(xref)
            if base_image.get('ext') == 'jpeg':
                # SMask確認
                smask_ref = doc.xref_get_key(xref, "SMask")
                if smask_ref and smask_ref not in [None, 'null', ('null', 'null')]:
                    test_images.append((xref, base_image))
                    if len(test_images) >= 3:  # 3つまで
                        break
        except:
            continue
    
    print(f"テスト対象: {len(test_images)}個の画像")
    
    successful_separations = 0
    total_savings = 0
    
    for i, (xref, base_image) in enumerate(test_images):
        print(f"\\n{i+1}. xref{xref} ({base_image['width']}x{base_image['height']})")
        
        # 元のPDF内サイズ
        try:
            original_stream_size = len(doc.xref_stream(xref))
            print(f"    元PDF内サイズ: {original_stream_size:,} bytes")
        except:
            original_stream_size = 0
            
        # JPEG+SMask分離実行
        success, result = separate_jpeg_smask(doc, xref, quality=70, verbose=True)
        
        if success:
            new_jpeg_data, new_smask_data, smask_xref = result
            
            # 分離後のサイズ計算
            separated_total_size = len(new_jpeg_data) + len(new_smask_data)
            
            if original_stream_size > 0:
                savings = original_stream_size - separated_total_size
                savings_percent = (savings / original_stream_size) * 100
                total_savings += savings
                
                print(f"    分離後合計: {separated_total_size:,} bytes")
                print(f"    削減量: {savings:,} bytes ({savings_percent:.1f}%)")
                
                if savings > 0:
                    successful_separations += 1
            
            # 実際にPDFに適用してテスト
            try:
                # 一時的なPDFで分離適用をテスト
                test_doc = fitz.open('smasked-image-sample.pdf')
                test_page = test_doc[0]
                
                # JPEG部分を置換
                test_page.replace_image(xref, stream=new_jpeg_data)
                
                # SMaskを新しいデータに置換（実験的）
                # 注意: この部分は複雑で、完全な実装には追加作業が必要
                
                test_doc.save(f"test_separated_{xref}.pdf", deflate=True)
                separated_pdf_size = os.path.getsize(f"test_separated_{xref}.pdf")
                
                print(f"    分離適用PDF: {separated_pdf_size:,} bytes")
                
                test_doc.close()
                
                # クリーンアップ
                try:
                    os.remove(f"test_separated_{xref}.pdf")
                except:
                    pass
                    
            except Exception as e:
                print(f"    分離適用エラー: {e}")
        else:
            print(f"    分離失敗: {result}")
    
    doc.close()
    
    # 結果サマリー
    print(f"\\n=== 結果サマリー ===")
    print(f"成功した分離: {successful_separations}/{len(test_images)}")
    if total_savings > 0:
        print(f"推定削減量: {total_savings:,} bytes ({total_savings/1024/1024:.1f} MB)")

if __name__ == "__main__":
    test_jpeg_smask_separation()