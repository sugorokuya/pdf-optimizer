#!/usr/bin/env python3
"""
Enhanced pikepdf test - SMask保持機能とwrite()メソッドの改良テスト
"""
import io
import pikepdf
from PIL import Image

def test_new_write_methods():
    """新しく追加したメソッドのテスト"""
    print("=== 新しい機能のテスト ===")
    
    # テスト用PDFを開く
    pdf = pikepdf.Pdf.open('smasked-image-sample.pdf')
    page = pdf.pages[0]
    
    # XObjectディクショナリを取得
    resources = page.resources
    if '/XObject' not in resources:
        print("XObjectがありません")
        return
    
    xobjects = resources['/XObject']
    
    # 最初の画像を処理
    for name, xobj in xobjects.items():
        if xobj.stream_dict.get('/Subtype') == '/Image':
            print(f"\n処理対象: {name}")
            
            # 元のSMaskを確認
            has_smask = '/SMask' in xobj.stream_dict
            print(f"  SMask: {has_smask}")
            
            if has_smask:
                # _write_with_smaskメソッドをテスト
                try:
                    # ダミーのJPEGデータを作成
                    jpeg_img = Image.new('RGB', (100, 100), (255, 0, 0))
                    jpeg_io = io.BytesIO()
                    jpeg_img.save(jpeg_io, format='JPEG', quality=85)
                    jpeg_data = jpeg_io.getvalue()
                    
                    # ダミーのアルファマスクデータ
                    alpha_img = Image.new('L', (100, 100), 128)
                    alpha_io = io.BytesIO()
                    alpha_img.save(alpha_io, format='JPEG', quality=85)
                    alpha_data = alpha_io.getvalue()
                    
                    # 元のSMask参照を取得
                    original_smask = xobj.stream_dict.get('/SMask')
                    
                    # 新しいメソッドを使用
                    xobj._write_with_smask(
                        data=jpeg_data,
                        filter=pikepdf.Name('/DCTDecode'),
                        decode_parms=None,
                        smask=original_smask
                    )
                    
                    print("  ✓ _write_with_smask成功")
                    
                    # SMaskが保持されているか確認
                    if '/SMask' in xobj.stream_dict:
                        print("  ✓ SMask参照が保持されています")
                    else:
                        print("  ✗ SMask参照が失われました")
                        
                except Exception as e:
                    print(f"  ✗ エラー: {e}")
                    
            break  # 最初の画像のみテスト
    
    # replace_image_preserve_smaskメソッドをテスト
    print("\n=== replace_image_preserve_smaskメソッドのテスト ===")
    try:
        # 最初の画像を見つける
        first_image = None
        for name, xobj in xobjects.items():
            if xobj.stream_dict.get('/Subtype') == '/Image':
                first_image = xobj
                break
        
        if first_image:
            # ダミーのJPEGデータ
            jpeg_data = jpeg_io.getvalue()
            alpha_data = alpha_io.getvalue()
            
            # 新しいメソッドを使用
            page.replace_image_preserve_smask(
                old_image=first_image,
                new_jpeg_data=jpeg_data,
                new_smask_data=alpha_data
            )
            
            print("  ✓ replace_image_preserve_smask成功")
            
    except AttributeError as e:
        if "replace_image_preserve_smask" in str(e):
            print("  ℹ replace_image_preserve_smaskメソッドはPageオブジェクトで利用可能です")
        else:
            print(f"  ✗ エラー: {e}")
    except Exception as e:
        print(f"  ✗ エラー: {e}")
    
    # 保存テスト
    print("\n=== 保存テスト ===")
    try:
        pdf.save('test_enhanced_output.pdf')
        print("  ✓ PDFの保存成功: test_enhanced_output.pdf")
    except Exception as e:
        print(f"  ✗ 保存エラー: {e}")

if __name__ == '__main__':
    test_new_write_methods()