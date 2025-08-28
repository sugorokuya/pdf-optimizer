#!/usr/bin/env python3
"""
Enhanced PDF Optimizer - 正しいSMask処理実装
Enhanced pikepdfのC++拡張メソッドを活用した正しい実装
"""

import pikepdf
from PIL import Image
import io
import os
import sys

def optimize_pdf_with_correct_smask(input_pdf, output_pdf):
    """正しいSMask処理によるPDF最適化"""
    
    print("=== Enhanced PDF Optimization with Correct SMask Handling ===")
    print(f"Input: {input_pdf}")
    print(f"Output: {output_pdf}")
    
    # 拡張メソッドの確認
    test_stream = pikepdf.Stream(pikepdf.Pdf.new(), b"test")
    if hasattr(test_stream, '_write_with_smask'):
        print("✅ _write_with_smask method available")
    else:
        print("❌ _write_with_smask method NOT available - using standard method")
    
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
                
                # 小さすぎる画像は除外
                if width < 50 or height < 50:
                    continue
                
                print(f"  Processing: {name} ({width}x{height})")
                
                try:
                    # SMask付き画像の処理
                    if '/SMask' in obj:
                        print(f"    Has SMask - using enhanced method")
                        
                        # ベース画像抽出
                        base_img = pikepdf.PdfImage(obj).as_pil_image()
                        
                        # CMYK→RGB変換
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
                        if base_img.size != (width, height):
                            base_img = base_img.resize((width, height), Image.Resampling.LANCZOS)
                        if smask_img.size != (width, height):
                            smask_img = smask_img.resize((width, height), Image.Resampling.LANCZOS)
                        
                        # ベース画像をJPEG圧縮（品質70）
                        jpeg_output = io.BytesIO()
                        base_img.save(jpeg_output, format='JPEG', quality=70, optimize=True)
                        jpeg_data = jpeg_output.getvalue()
                        
                        # SMaskは生ピクセルデータとして保持（ロスレス）
                        smask_raw_data = smask_img.tobytes()
                        
                        # _write_with_smaskメソッドを使用してベース画像を更新
                        if hasattr(obj, '_write_with_smask'):
                            # Enhanced pikepdf method
                            obj._write_with_smask(
                                data=jpeg_data,
                                filter=pikepdf.Name('/DCTDecode'),
                                decode_parms=None,
                                smask=smask_obj  # SMask参照を保持
                            )
                        else:
                            # Fallback to standard method
                            obj.write(jpeg_data, filter=pikepdf.Name.DCTDecode)
                        
                        # 画像プロパティ更新
                        obj.Width = base_img.width
                        obj.Height = base_img.height
                        obj.ColorSpace = pikepdf.Name.DeviceRGB
                        obj.BitsPerComponent = 8
                        
                        # SMaskを生ピクセルデータで更新（FlateDecode圧縮）
                        smask_obj.write(smask_raw_data, filter=pikepdf.Name.FlateDecode)
                        smask_obj.Width = smask_img.width
                        smask_obj.Height = smask_img.height
                        smask_obj.ColorSpace = pikepdf.Name.DeviceGray
                        smask_obj.BitsPerComponent = 8
                        
                        print(f"    ✓ Updated: JPEG {len(jpeg_data):,} bytes, SMask {len(smask_raw_data):,} bytes (raw)")
                        total_processed += 1
                    
                    # SMaskなし画像の処理
                    else:
                        print(f"    No SMask - standard processing")
                        
                        img = pikepdf.PdfImage(obj).as_pil_image()
                        
                        # CMYK→RGB変換
                        if img.mode == 'CMYK':
                            img = img.convert('RGB')
                        elif img.mode != 'RGB' and img.mode != 'L':
                            img = img.convert('RGB')
                        
                        # サイズ調整
                        if img.size != (width, height):
                            img = img.resize((width, height), Image.Resampling.LANCZOS)
                        
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
    
    # 保存（ストリーム圧縮付き）
    pdf.save(output_pdf, compress_streams=True)
    pdf.close()
    
    # 結果表示
    final_size = os.path.getsize(output_pdf)
    reduction = (1 - final_size / initial_size) * 100
    
    print(f"\n=== Optimization Results ===")
    print(f"Processed images: {total_processed}")
    print(f"Original size: {initial_size:,} bytes")
    print(f"Optimized size: {final_size:,} bytes")
    print(f"Reduction: {reduction:.1f}%")
    
    return reduction

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python enhanced_optimizer_correct.py input.pdf [output.pdf]")
        sys.exit(1)
    
    input_pdf = sys.argv[1]
    output_pdf = sys.argv[2] if len(sys.argv) > 2 else input_pdf.replace('.pdf', '_optimized.pdf')
    
    try:
        reduction = optimize_pdf_with_correct_smask(input_pdf, output_pdf)
        if reduction > 0:
            print(f"\n✓ Optimization successful: {output_pdf}")
        else:
            print(f"\n△ No size reduction: {output_pdf}")
    except Exception as e:
        print(f"\n✗ Error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)