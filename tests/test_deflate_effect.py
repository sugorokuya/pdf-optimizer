#!/usr/bin/env python3

import fitz
from PIL import Image, ImageDraw
import io
import os

def test_deflate_effect():
    """deflate=Trueの効果をテスト"""
    
    # テスト用透明画像作成
    img = Image.new('RGBA', (200, 200), (255, 0, 0, 128))  # 半透明赤
    draw = ImageDraw.Draw(img)
    draw.ellipse([50, 50, 150, 150], fill=(0, 255, 0, 200))  # 半透明緑円
    
    # PNG作成
    png_stream = io.BytesIO()
    img.save(png_stream, format='PNG', optimize=True, compress_level=9)
    png_data = png_stream.getvalue()
    
    print(f"=== deflate効果テスト ===")
    print(f"PNGデータサイズ: {len(png_data):,} bytes")
    
    # テストPDF作成
    doc = fitz.open()
    page = doc.new_page(width=400, height=300)
    
    rect = fitz.Rect(100, 50, 300, 250)
    page.insert_image(rect, stream=png_data)
    
    # 1. 通常保存
    doc.save("test_normal.pdf")
    size_normal = os.path.getsize("test_normal.pdf")
    print(f"\\n通常保存: {size_normal:,} bytes")
    
    # 2. deflate=True保存
    doc.save("test_deflate.pdf", deflate=True)
    size_deflate = os.path.getsize("test_deflate.pdf")
    print(f"deflate=True: {size_deflate:,} bytes ({size_deflate/size_normal*100:.1f}%)")
    
    # 3. 完全最適化保存
    save_options = {
        'garbage': 4,
        'deflate': True,
        'deflate_images': True,
        'deflate_fonts': True,
        'clean': True,
        'pretty': False,
        'preserve_metadata': False,
        'use_objstms': True
    }
    doc.save("test_optimized.pdf", **save_options)
    size_optimized = os.path.getsize("test_optimized.pdf")
    print(f"完全最適化: {size_optimized:,} bytes ({size_optimized/size_normal*100:.1f}%)")
    
    # 4. ez_save
    doc.ez_save("test_ez_save.pdf", compression_effort=100)
    size_ez = os.path.getsize("test_ez_save.pdf")
    print(f"ez_save: {size_ez:,} bytes ({size_ez/size_normal*100:.1f}%)")
    
    # 各PDFの内部構造を確認
    print(f"\\n=== 内部構造分析 ===")
    for filename, label in [
        ("test_normal.pdf", "通常"),
        ("test_deflate.pdf", "deflate"),
        ("test_optimized.pdf", "最適化"),
        ("test_ez_save.pdf", "ez_save")
    ]:
        doc2 = fitz.open(filename)
        page2 = doc2[0]
        images = page2.get_images()
        
        if images:
            xref = images[0][0]
            try:
                stream_size = len(doc2.xref_stream(xref))
                base_image = doc2.extract_image(xref)
                extracted_size = len(base_image['image'])
                
                print(f"{label}:")
                print(f"  PDF内ストリーム: {stream_size:,} bytes")
                print(f"  extract_image: {extracted_size:,} bytes")
                print(f"  膨張率: {stream_size / len(png_data):.1f}倍")
            except Exception as e:
                print(f"{label}: エラー - {e}")
        
        doc2.close()
    
    doc.close()
    
    # クリーンアップ
    for f in ["test_normal.pdf", "test_deflate.pdf", "test_optimized.pdf", "test_ez_save.pdf"]:
        try:
            os.remove(f)
        except:
            pass

if __name__ == "__main__":
    test_deflate_effect()