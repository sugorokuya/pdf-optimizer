#!/usr/bin/env python3

import fitz
from PIL import Image, ImageDraw
import io
import os
import zlib

def test_xref_bypass():
    """xrefレベルでのPNG膨張バイパステスト"""
    
    # 元画像を含むテストPDF作成
    doc = fitz.open()
    page = doc.new_page(width=400, height=400)
    
    # 元画像として大きなJPEG挿入
    orig_img = Image.new('RGB', (200, 200), (255, 255, 0))  # 黄色
    orig_jpeg = io.BytesIO()
    orig_img.save(orig_jpeg, format='JPEG', quality=90)
    
    rect = fitz.Rect(50, 50, 250, 250)
    page.insert_image(rect, stream=orig_jpeg.getvalue())
    
    temp_pdf = "temp_xref_test.pdf"
    doc.save(temp_pdf)
    doc.close()
    
    print("=== xrefバイパステスト ===")
    
    # 置換用PNG作成
    replacement_img = Image.new('RGBA', (100, 100), (255, 0, 0, 200))  # 半透明赤
    png_stream = io.BytesIO()
    replacement_img.save(png_stream, format='PNG', optimize=True, compress_level=9)
    png_data = png_stream.getvalue()
    
    print(f"PNGデータサイズ: {len(png_data):,} bytes")
    
    # PDFを開いて画像xref特定
    doc2 = fitz.open(temp_pdf)
    page2 = doc2[0]
    images = page2.get_images()
    xref = images[0][0]
    
    print(f"画像xref: {xref}")
    
    # 1. 現在の方法での置換（参照用）
    print(f"\\n1. 通常のreplace_image:")
    page2.replace_image(xref, stream=png_data)
    doc2.save("test_normal_replace.pdf", deflate=True)
    size_normal = os.path.getsize("test_normal_replace.pdf")
    print(f"  ファイルサイズ: {size_normal:,} bytes")
    
    # 元の状態に戻す
    doc2.close()
    doc2 = fitz.open(temp_pdf)
    page2 = doc2[0]
    
    # 2. 低レベルxref操作を試す
    print(f"\\n2. 低レベルxref操作:")
    try:
        # 元のxref情報取得
        old_width = doc2.xref_get_key(xref, "Width")
        old_height = doc2.xref_get_key(xref, "Height")
        old_filter = doc2.xref_get_key(xref, "Filter")
        old_colorspace = doc2.xref_get_key(xref, "ColorSpace")
        
        print(f"  元画像: {old_width}x{old_height}, Filter: {old_filter}")
        
        # PNGデータを直接FlateDecode圧縮してみる
        compressed_png = zlib.compress(png_data, level=9)
        print(f"  zlib圧縮PNG: {len(compressed_png):,} bytes")
        
        # xrefに直接セット
        doc2.xref_set_key(xref, "Width", "100")
        doc2.xref_set_key(xref, "Height", "100")
        doc2.xref_set_key(xref, "Filter", "('name', '/FlateDecode')")
        doc2.xref_set_key(xref, "ColorSpace", "('name', '/DeviceRGB')")
        
        # ストリーム置換を試す
        # 注意: この部分は実験的で、動作しない可能性があります
        print("  xref直接操作を試行中...")
        
    except Exception as e:
        print(f"  xref操作エラー: {e}")
    
    # 3. _getXrefStreamを使った方法
    print(f"\\n3. _getXrefStream使用:")
    try:
        # 他の画像からストリームをコピーする方法をテスト
        # 新しい小さなJPEG画像を作成
        small_img = Image.new('RGB', (100, 100), (0, 255, 0))  # 緑
        small_jpeg = io.BytesIO()
        small_img.save(small_jpeg, format='JPEG', quality=50)
        
        # 一時的に新しい画像を挿入
        temp_rect = fitz.Rect(300, 300, 350, 350)
        page2.insert_image(temp_rect, stream=small_jpeg.getvalue())
        
        # 新しい画像のxrefを取得
        new_images = page2.get_images()
        new_xref = None
        for img in new_images:
            if img[0] != xref:
                new_xref = img[0]
                break
        
        if new_xref:
            print(f"  新画像xref: {new_xref}")
            # ストリームを直接コピー
            if hasattr(doc2, '_getXrefStream'):
                stream_data = doc2._getXrefStream(new_xref)
                print(f"  ストリームサイズ: {len(stream_data):,} bytes")
                
                # 元の画像位置に新しいストリームを適用
                # この部分も実験的です
                
    except Exception as e:
        print(f"  _getXrefStream エラー: {e}")
    
    # 4. 結果確認
    doc2.save("test_xref_bypass.pdf", deflate=True)
    size_bypass = os.path.getsize("test_xref_bypass.pdf")
    print(f"\\n結果:")
    print(f"  通常置換: {size_normal:,} bytes")
    print(f"  xrefバイパス: {size_bypass:,} bytes")
    
    doc2.close()
    
    # クリーンアップ
    for f in [temp_pdf, "test_normal_replace.pdf", "test_xref_bypass.pdf"]:
        try:
            os.remove(f)
        except:
            pass

if __name__ == "__main__":
    test_xref_bypass()