#!/usr/bin/env python3

import fitz
from PIL import Image, ImageDraw
import io
import os

def test_png_compression_methods():
    """PNG圧縮方法をテスト"""
    
    # テスト用PDF作成
    doc = fitz.open()
    page = doc.new_page(width=600, height=400)
    
    # テスト用透明画像作成
    img = Image.new('RGBA', (300, 200), (255, 0, 0, 128))  # 半透明赤
    draw = ImageDraw.Draw(img)
    draw.ellipse([50, 50, 150, 150], fill=(0, 255, 0, 200))  # 半透明緑円
    draw.text((10, 10), "Test Image", fill=(255, 255, 255, 255))
    
    print("=== PNG圧縮方法テスト ===")
    
    # 1. 通常のPNG stream挿入
    png_stream = io.BytesIO()
    img.save(png_stream, format='PNG', optimize=True, compress_level=9)
    png_data = png_stream.getvalue()
    print(f"PNGストリームサイズ: {len(png_data):,} bytes")
    
    rect1 = fitz.Rect(50, 50, 350, 250)
    page.insert_image(rect1, stream=png_data)
    
    # 2. Pixmap経由挿入
    try:
        pix = fitz.Pixmap(png_data)
        rect2 = fitz.Rect(350, 50, 550, 200)
        page.insert_image(rect2, pixmap=pix)
        pix = None
        print("Pixmap挿入: 成功")
    except Exception as e:
        print(f"Pixmap挿入エラー: {e}")
    
    # 3. 色数削減PNG
    quantized = img.quantize(colors=16, method=Image.Quantize.FASTOCTREE)
    rgba_quantized = quantized.convert('RGBA')
    
    quantized_stream = io.BytesIO()
    rgba_quantized.save(quantized_stream, format='PNG', optimize=True, compress_level=9)
    quantized_data = quantized_stream.getvalue()
    print(f"16色PNGストリームサイズ: {len(quantized_data):,} bytes")
    
    rect3 = fitz.Rect(50, 250, 350, 400)
    page.insert_image(rect3, stream=quantized_data)
    
    # PDFとして保存
    test_pdf = "png_compression_test.pdf"
    doc.save(test_pdf)
    doc.close()
    
    # ファイルサイズ確認
    file_size = os.path.getsize(test_pdf)
    print(f"\nテストPDFサイズ: {file_size:,} bytes")
    
    # PDF内の画像サイズを分析
    doc2 = fitz.open(test_pdf)
    page2 = doc2[0]
    images = page2.get_images()
    
    print(f"\nPDF内画像分析:")
    for i, img_info in enumerate(images):
        xref = img_info[0]
        try:
            base_image = doc2.extract_image(xref)
            extracted_size = len(base_image['image'])
            width = base_image['width']
            height = base_image['height']
            format_type = base_image['ext']
            
            print(f"  画像{i+1} (xref{xref}): {width}x{height} {format_type} - {extracted_size:,} bytes")
            
            # PDF内ストリームサイズも確認
            try:
                stream_size = len(doc2.xref_stream(xref))
                print(f"    PDF内ストリーム: {stream_size:,} bytes")
                if extracted_size > 0:
                    expansion_ratio = stream_size / extracted_size
                    print(f"    膨張率: {expansion_ratio:.1f}倍")
            except:
                pass
                
        except Exception as e:
            print(f"  画像{i+1} (xref{xref}): エラー - {e}")
    
    doc2.close()
    print(f"\nテストファイル: {test_pdf}")

if __name__ == "__main__":
    test_png_compression_methods()