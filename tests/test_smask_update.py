#!/usr/bin/env python3

import fitz
from PIL import Image
import io
import os

def test_smask_update_methods():
    """SMaskオブジェクトの更新方法をテスト"""
    
    print("=== SMask更新方法テスト ===")
    
    doc = fitz.open('smasked-image-sample.pdf')
    page = doc[0]
    images = page.get_images()
    
    # 最初のSMask付き画像を選択
    test_xref = None
    test_smask_xref = None
    
    for img_info in images[:5]:
        xref = img_info[0]
        try:
            smask_ref = doc.xref_get_key(xref, "SMask")
            if smask_ref and smask_ref not in [None, 'null', ('null', 'null')]:
                test_xref = xref
                # SMask xref を抽出
                if isinstance(smask_ref, tuple) and len(smask_ref) >= 2:
                    smask_str = smask_ref[1]
                    if ' 0 R' in smask_str:
                        test_smask_xref = int(smask_str.split(' 0 R')[0])
                        break
        except:
            continue
    
    if not test_xref or not test_smask_xref:
        print("SMask付き画像が見つかりません")
        doc.close()
        return
        
    print(f"テスト対象: xref{test_xref}, SMask: xref{test_smask_xref}")
    
    try:
        # 1. 元画像とSMaskの情報取得
        base_image = doc.extract_image(test_xref)
        smask_image = doc.extract_image(test_smask_xref)
        
        print(f"元画像: {base_image['width']}x{base_image['height']} {base_image['ext']}")
        print(f"SMask: {smask_image['width']}x{smask_image['height']} {smask_image['ext']}")
        
        # 2. RGBA画像に合成
        jpeg_img = Image.open(io.BytesIO(base_image['image']))
        smask_img = Image.open(io.BytesIO(smask_image['image']))
        
        # サイズ調整
        if jpeg_img.size != smask_img.size:
            smask_img = smask_img.resize(jpeg_img.size, Image.Resampling.LANCZOS)
            
        # SMaskをグレースケールに変換
        if smask_img.mode != 'L':
            smask_img = smask_img.convert('L')
            
        # RGBA合成
        if jpeg_img.mode != 'RGB':
            jpeg_img = jpeg_img.convert('RGB')
            
        r, g, b = jpeg_img.split()
        rgba_img = Image.merge('RGBA', (r, g, b, smask_img))
        
        # 3. 64x64にリサイズ（テスト用）
        small_img = rgba_img.resize((64, 64), Image.Resampling.LANCZOS)
        
        # 4. JPEG+SMask分離
        r, g, b, a = small_img.split()
        new_jpeg_img = Image.merge('RGB', (r, g, b))
        new_alpha_img = a
        
        # JPEG保存
        jpeg_output = io.BytesIO()
        new_jpeg_img.save(jpeg_output, format='JPEG', quality=70, optimize=True)
        new_jpeg_data = jpeg_output.getvalue()
        
        # Alpha保存（グレースケール画像として）
        alpha_output = io.BytesIO()
        new_alpha_img.save(alpha_output, format='PNG', optimize=True, compress_level=9)
        new_alpha_data = alpha_output.getvalue()
        
        print(f"分離結果: JPEG {len(new_jpeg_data):,}bytes, Alpha {len(new_alpha_data):,}bytes")
        
        # 5. PDF更新テスト
        print(f"\\n=== PDF更新テスト ===")
        
        # Method 1: 元画像をJPEGで置換
        try:
            page.replace_image(test_xref, stream=new_jpeg_data)
            print("✓ JPEG画像置換成功")
        except Exception as e:
            print(f"✗ JPEG画像置換失敗: {e}")
            
        # Method 2: SMaskを新しいアルファデータで置換
        try:
            # SMask画像を直接置換
            # 注意: この方法は実験的です
            page.replace_image(test_smask_xref, stream=new_alpha_data)
            print("✓ SMask置換成功")
        except Exception as e:
            print(f"✗ SMask置換失敗: {e}")
            
        # Method 3: xrefオブジェクトレベルでの更新
        try:
            # 新しいSMaskオブジェクトの情報を設定
            doc.xref_set_key(test_xref, "Width", "64")
            doc.xref_set_key(test_xref, "Height", "64")
            doc.xref_set_key(test_smask_xref, "Width", "64") 
            doc.xref_set_key(test_smask_xref, "Height", "64")
            print("✓ xrefサイズ更新成功")
        except Exception as e:
            print(f"✗ xrefサイズ更新失敗: {e}")
        
        # 6. テスト結果保存
        test_output = "smask_update_test.pdf"
        doc.save(test_output, deflate=True)
        
        # サイズ確認
        test_size = os.path.getsize(test_output)
        original_size = os.path.getsize('smasked-image-sample.pdf')
        
        print(f"\\n=== 結果 ===")
        print(f"元サイズ: {original_size:,} bytes")
        print(f"テスト結果: {test_size:,} bytes")
        print(f"変化: {((test_size - original_size) / original_size * 100):+.1f}%")
        
        # 7. PDF内部確認
        doc2 = fitz.open(test_output)
        page2 = doc2[0]
        images2 = page2.get_images()
        
        print(f"\\n=== 内部検証 ===")
        for i, img_info in enumerate(images2[:3]):
            xref = img_info[0]
            try:
                img_data = doc2.extract_image(xref)
                stream_size = len(doc2.xref_stream(xref))
                print(f"画像{i+1} xref{xref}: {img_data['width']}x{img_data['height']} " +
                      f"{img_data['ext']} extract:{len(img_data['image']):,}b stream:{stream_size:,}b")
            except Exception as e:
                print(f"画像{i+1} xref{xref}: エラー - {e}")
        
        doc2.close()
        
        # クリーンアップ
        try:
            os.remove(test_output)
        except:
            pass
            
    except Exception as e:
        print(f"テストエラー: {e}")
    
    doc.close()

if __name__ == "__main__":
    test_smask_update_methods()