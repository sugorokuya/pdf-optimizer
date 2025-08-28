#!/usr/bin/env python3

import fitz
from PIL import Image, ImageDraw
import io
import os

def test_replace_image_compression():
    """replace_imageでのPNG圧縮テスト"""
    
    # 元画像を含むテストPDF作成
    doc = fitz.open()
    page = doc.new_page(width=400, height=400)
    
    # 元画像として大きなJPEG挿入
    orig_img = Image.new('RGB', (300, 300), (255, 255, 0))  # 黄色
    draw = ImageDraw.Draw(orig_img)
    draw.rectangle([50, 50, 250, 250], fill=(0, 0, 255))  # 青い四角
    
    orig_jpeg = io.BytesIO()
    orig_img.save(orig_jpeg, format='JPEG', quality=90)
    orig_data = orig_jpeg.getvalue()
    
    rect = fitz.Rect(50, 50, 350, 350)
    page.insert_image(rect, stream=orig_data)
    
    temp_pdf = "temp_replace_test.pdf"
    doc.save(temp_pdf)
    doc.close()
    
    print("=== replace_image PNG圧縮テスト ===")
    
    # 置換用透明画像作成
    replacement_img = Image.new('RGBA', (200, 200), (255, 0, 0, 128))  # 半透明赤
    draw2 = ImageDraw.Draw(replacement_img)
    draw2.ellipse([30, 30, 170, 170], fill=(0, 255, 0, 200))  # 半透明緑円
    
    # PNG作成
    png_stream = io.BytesIO()
    replacement_img.save(png_stream, format='PNG', optimize=True, compress_level=9)
    png_data = png_stream.getvalue()
    print(f"置換PNG サイズ: {len(png_data):,} bytes")
    
    # 色数削減版
    quantized = replacement_img.quantize(colors=8, method=Image.Quantize.FASTOCTREE)
    rgba_quantized = quantized.convert('RGBA')
    
    quantized_stream = io.BytesIO()
    rgba_quantized.save(quantized_stream, format='PNG', optimize=True, compress_level=9)
    quantized_data = quantized_stream.getvalue()
    print(f"8色PNG サイズ: {len(quantized_data):,} bytes")
    
    # PDFを開いて置換テスト
    doc2 = fitz.open(temp_pdf)
    page2 = doc2[0]
    images = page2.get_images()
    xref = images[0][0]
    
    print(f"\n元画像 xref: {xref}")
    
    # 元のサイズ確認
    try:
        orig_stream_size = len(doc2.xref_stream(xref))
        print(f"元画像PDF内サイズ: {orig_stream_size:,} bytes")
    except:
        pass
    
    # 1. 通常PNGで置換
    print(f"\n1. 通常PNGで置換:")
    page2.replace_image(xref, stream=png_data)
    
    doc2.save("replaced_normal_png.pdf")
    size1 = os.path.getsize("replaced_normal_png.pdf")
    print(f"  ファイルサイズ: {size1:,} bytes")
    
    # PDF内のサイズ確認
    try:
        new_stream_size = len(doc2.xref_stream(xref))
        print(f"  PDF内ストリーム: {new_stream_size:,} bytes")
        print(f"  膨張率: {new_stream_size / len(png_data):.1f}倍")
    except:
        pass
    
    # 2. 8色PNGで置換
    print(f"\n2. 8色PNGで置換:")
    page2.replace_image(xref, stream=quantized_data)
    
    doc2.save("replaced_quantized_png.pdf")
    size2 = os.path.getsize("replaced_quantized_png.pdf")
    print(f"  ファイルサイズ: {size2:,} bytes")
    
    try:
        new_stream_size2 = len(doc2.xref_stream(xref))
        print(f"  PDF内ストリーム: {new_stream_size2:,} bytes")
        print(f"  膨張率: {new_stream_size2 / len(quantized_data):.1f}倍")
    except:
        pass
    
    # 3. Pixmapで置換テスト
    print(f"\n3. Pixmapで置換:")
    try:
        pix = fitz.Pixmap(quantized_data)
        page2.replace_image(xref, pixmap=pix)
        pix = None
        
        doc2.save("replaced_pixmap.pdf")
        size3 = os.path.getsize("replaced_pixmap.pdf")
        print(f"  ファイルサイズ: {size3:,} bytes")
        
        try:
            new_stream_size3 = len(doc2.xref_stream(xref))
            print(f"  PDF内ストリーム: {new_stream_size3:,} bytes")
        except:
            pass
            
    except Exception as e:
        print(f"  Pixmap置換エラー: {e}")
    
    doc2.close()
    
    # クリーンアップ
    for f in [temp_pdf, "replaced_normal_png.pdf", "replaced_quantized_png.pdf", "replaced_pixmap.pdf"]:
        try:
            os.remove(f)
        except:
            pass

if __name__ == "__main__":
    test_replace_image_compression()