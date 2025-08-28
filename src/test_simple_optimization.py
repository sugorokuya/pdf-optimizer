#!/usr/bin/env python3
"""
Simple JPEG+SMask optimization test
Enhanced pikepdf機能の動作確認用
"""

import pikepdf
from PIL import Image
import io
import os
import sys

def simple_jpeg_smask_optimization(input_pdf, output_pdf):
    """シンプルなJPEG+SMask最適化テスト"""
    
    print("=== pikepdf シンプル最適化テスト ===")
    print(f"Input: {input_pdf}")
    print(f"Output: {output_pdf}")
    
    pdf = pikepdf.Pdf.open(input_pdf)
    initial_size = os.path.getsize(input_pdf)
    
    total_processed = 0
    total_pages = len(pdf.pages)
    
    for page_num, page in enumerate(pdf.pages):
        print(f"\nPage {page_num + 1}/{total_pages}")
        
        if '/Resources' not in page or '/XObject' not in page['/Resources']:
            continue
            
        xobjects = page['/Resources']['/XObject']
        
        for name, obj in xobjects.items():
            if '/Subtype' in obj and obj['/Subtype'] == '/Image':
                width = int(obj.get('/Width', 0))
                height = int(obj.get('/Height', 0))
                
                # SMask付き画像を処理
                if '/SMask' in obj:
                    print(f"  Processing SMask image: {name} ({width}x{height})")
                    
                    try:
                        # ベース画像抽出
                        base_img = pikepdf.PdfImage(obj).as_pil_image()
                        if base_img.mode == 'CMYK':
                            base_img = base_img.convert('RGB')
                        elif base_img.mode != 'RGB':
                            base_img = base_img.convert('RGB')
                        
                        # SMask抽出
                        smask_obj = obj['/SMask']
                        smask_img = pikepdf.PdfImage(smask_obj).as_pil_image()
                        if smask_img.mode != 'L':
                            smask_img = smask_img.convert('L')
                        
                        # サイズ合わせ
                        if base_img.size != smask_img.size:
                            smask_img = smask_img.resize(base_img.size, Image.Resampling.LANCZOS)
                        
                        # JPEGで保存（品質70）
                        jpeg_output = io.BytesIO()
                        base_img.save(jpeg_output, format='JPEG', quality=70, optimize=True)
                        jpeg_data = jpeg_output.getvalue()
                        
                        # Alpha（SMask）は生ピクセルデータとして保存（FlateDecode圧縮）
                        alpha_data = smask_img.tobytes()
                        
                        # PDFオブジェクトを更新
                        obj.write(jpeg_data, filter=pikepdf.Name.DCTDecode)
                        obj.Width = base_img.width
                        obj.Height = base_img.height
                        obj.ColorSpace = pikepdf.Name.DeviceRGB
                        obj.BitsPerComponent = 8
                        
                        # SMaskも更新（生ピクセルデータをFlateDecode圧縮）
                        smask_obj.write(alpha_data, filter=pikepdf.Name.FlateDecode)
                        smask_obj.Width = smask_img.width
                        smask_obj.Height = smask_img.height
                        smask_obj.ColorSpace = pikepdf.Name.DeviceGray
                        smask_obj.BitsPerComponent = 8
                        
                        print(f"    ✓ Updated: JPEG {len(jpeg_data):,} bytes, SMask {len(alpha_data):,} bytes")
                        total_processed += 1
                        
                    except Exception as e:
                        print(f"    ✗ Error: {e}")
                
                # SMaskなし画像も処理
                elif width > 100 and height > 100:  # 小さすぎる画像は除外
                    print(f"  Processing regular image: {name} ({width}x{height})")
                    
                    try:
                        img = pikepdf.PdfImage(obj).as_pil_image()
                        
                        # CMYK→RGB変換
                        if img.mode == 'CMYK':
                            img = img.convert('RGB')
                        elif img.mode != 'RGB' and img.mode != 'L':
                            img = img.convert('RGB')
                        
                        # JPEG圧縮
                        output = io.BytesIO()
                        img.save(output, format='JPEG', quality=70, optimize=True)
                        jpeg_data = output.getvalue()
                        
                        # 更新
                        obj.write(jpeg_data, filter=pikepdf.Name.DCTDecode)
                        obj.Width = img.width
                        obj.Height = img.height
                        if img.mode == 'RGB':
                            obj.ColorSpace = pikepdf.Name.DeviceRGB
                        elif img.mode == 'L':
                            obj.ColorSpace = pikepdf.Name.DeviceGray
                        obj.BitsPerComponent = 8
                        
                        print(f"    ✓ Updated: JPEG {len(jpeg_data):,} bytes")
                        total_processed += 1
                        
                    except Exception as e:
                        print(f"    ✗ Error: {e}")
    
    # 保存
    pdf.save(output_pdf, compress_streams=True)
    pdf.close()
    
    # 結果表示
    final_size = os.path.getsize(output_pdf)
    reduction = (1 - final_size / initial_size) * 100
    
    print(f"\n=== 最適化結果 ===")
    print(f"処理画像数: {total_processed}")
    print(f"元のサイズ: {initial_size:,} bytes")
    print(f"最適化後: {final_size:,} bytes")
    print(f"削減率: {reduction:.1f}%")
    
    return reduction

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python test_simple_optimization.py input.pdf [output.pdf]")
        sys.exit(1)
    
    input_pdf = sys.argv[1]
    output_pdf = sys.argv[2] if len(sys.argv) > 2 else input_pdf.replace('.pdf', '_optimized.pdf')
    
    try:
        reduction = simple_jpeg_smask_optimization(input_pdf, output_pdf)
        if reduction > 0:
            print(f"\n✓ 最適化成功: {output_pdf}")
        else:
            print(f"\n△ サイズ削減なし: {output_pdf}")
    except Exception as e:
        print(f"\n✗ エラー: {e}")
        sys.exit(1)