#!/usr/bin/env python3

import pikepdf
from PIL import Image
import io
import os

def simple_jpeg_smask_optimization():
    """シンプルなJPEG+SMask最適化テスト"""
    
    print("=== pikepdf シンプル最適化テスト ===")
    
    pdf = pikepdf.Pdf.open('smasked-image-sample.pdf')
    page = pdf.pages[0]
    xobjects = page['/Resources']['/XObject']
    
    processed = 0
    
    # 小さめの画像のみ処理（テスト用）
    for name, obj in xobjects.items():
        if '/Subtype' in obj and obj['/Subtype'] == '/Image' and '/SMask' in obj:
            width = int(obj['/Width'])
            height = int(obj['/Height'])
            
            # 小さい画像のみ（500px以下）
            if width <= 500 and height <= 500:
                print(f"\n画像処理: {name} ({width}x{height})")
                
                try:
                    # ベース画像抽出
                    base_img = pikepdf.PdfImage(obj).as_pil_image()
                    if base_img.mode == 'CMYK':
                        base_img = base_img.convert('RGB')
                    
                    # SMask抽出
                    smask_obj = obj['/SMask']
                    smask_img = pikepdf.PdfImage(smask_obj).as_pil_image()
                    if smask_img.mode != 'L':
                        smask_img = smask_img.convert('L')
                    
                    # サイズ合わせ
                    if base_img.size != smask_img.size:
                        smask_img = smask_img.resize(base_img.size, Image.Resampling.LANCZOS)
                    
                    print(f"  抽出成功: RGB {base_img.size}, Alpha {smask_img.size}")
                    
                    # JPEGで保存
                    jpeg_output = io.BytesIO()
                    base_img.save(jpeg_output, format='JPEG', quality=70, optimize=True)
                    jpeg_data = jpeg_output.getvalue()
                    
                    # Alpha（SMask）をJPEGで保存
                    alpha_rgb = Image.merge('RGB', (smask_img, smask_img, smask_img))
                    alpha_output = io.BytesIO()
                    alpha_rgb.save(alpha_output, format='JPEG', quality=70, optimize=True)
                    alpha_data = alpha_output.getvalue()
                    
                    print(f"  JPEG変換: RGB {len(jpeg_data):,}bytes, Alpha {len(alpha_data):,}bytes")
                    
                    # 元のサイズ
                    try:
                        original_size = len(bytes(obj.read_raw_bytes()))
                        print(f"  元サイズ: {original_size:,}bytes")
                    except:
                        original_size = 0
                    
                    # PDFオブジェクトを更新
                    obj.write(jpeg_data, filter=pikepdf.Name.DCTDecode)
                    obj.Width = base_img.width
                    obj.Height = base_img.height
                    
                    # SMaskも更新
                    smask_obj.write(alpha_data, filter=pikepdf.Name.DCTDecode)
                    smask_obj.Width = smask_img.width
                    smask_obj.Height = smask_img.height
                    
                    print(f"  ✓ 更新完了")
                    processed += 1
                    
                    # 3個まで
                    if processed >= 3:
                        break
                        
                except Exception as e:
                    print(f"  エラー: {e}")
                    continue
    
    # 保存
    output_path = 'smasked-image-sample-pikepdf-simple.pdf'
    pdf.save(output_path)
    pdf.close()
    
    # 結果
    original_size = os.path.getsize('smasked-image-sample.pdf')
    optimized_size = os.path.getsize(output_path)
    reduction = (1 - optimized_size / original_size) * 100
    
    print(f"\n=== 結果 ===")
    print(f"処理成功: {processed}個")
    print(f"元ファイル: {original_size:,}bytes ({original_size/1024/1024:.1f}MB)")
    print(f"最適化後: {optimized_size:,}bytes ({optimized_size/1024/1024:.1f}MB)")
    print(f"削減率: {reduction:.1f}%")
    print(f"出力ファイル: {output_path}")
    
    return output_path

def verify_smask_preservation(pdf_path):
    """SMask参照の保持確認"""
    
    print(f"\n=== SMask保持確認: {pdf_path} ===")
    
    pdf = pikepdf.Pdf.open(pdf_path)
    page = pdf.pages[0]
    xobjects = page['/Resources']['/XObject']
    
    smask_count = 0
    
    for name, obj in xobjects.items():
        if '/Subtype' in obj and obj['/Subtype'] == '/Image':
            if '/SMask' in obj:
                smask_count += 1
                
                # SMask参照確認
                smask_ref = obj['/SMask']
                print(f"  {name}: SMask参照あり")
                
                # 3個まで詳細確認
                if smask_count <= 3:
                    try:
                        # Filter確認
                        img_filter = obj.get('/Filter', 'なし')
                        smask_filter = smask_ref.get('/Filter', 'なし')
                        
                        print(f"    画像Filter: {img_filter}")
                        print(f"    SMask Filter: {smask_filter}")
                        
                    except Exception as e:
                        print(f"    詳細確認エラー: {e}")
    
    pdf.close()
    
    print(f"SMask付き画像: {smask_count}個")
    return smask_count > 0

if __name__ == "__main__":
    # シンプル最適化実行
    output_file = simple_jpeg_smask_optimization()
    
    # SMask保持確認
    verify_smask_preservation(output_file)