#!/usr/bin/env python3

import fitz
from PIL import Image
import io
import os
import zlib

def test_direct_stream_injection():
    """PNGデータを直接PDFストリームに注入するテスト"""
    
    # 小さなRGBA画像作成
    img = Image.new('RGBA', (64, 64), (255, 0, 0, 128))  # 半透明赤
    
    print("=== 直接ストリーム注入テスト ===")
    
    # 1. 通常のPNG埋め込み（参照用）
    doc1 = fitz.open()
    page1 = doc1.new_page(width=200, height=200)
    
    png_stream = io.BytesIO()
    img.save(png_stream, format='PNG', optimize=True, compress_level=9)
    png_data = png_stream.getvalue()
    
    rect = fitz.Rect(50, 50, 114, 114)
    page1.insert_image(rect, stream=png_data)
    doc1.save("test_normal_png.pdf", deflate=True)
    size1 = os.path.getsize("test_normal_png.pdf")
    print(f"通常PNG埋め込み: {size1:,} bytes")
    doc1.close()
    
    # 2. 生RGBA データを直接FlateDecode ストリームとして作成
    doc2 = fitz.open()
    page2 = doc2.new_page(width=200, height=200)
    
    # RGBA生データ取得
    rgba_data = img.tobytes()  # Raw RGBA data
    print(f"RGBA生データ: {len(rgba_data):,} bytes")
    
    # zlib圧縮
    compressed_rgba = zlib.compress(rgba_data, level=9)
    print(f"圧縮RGBA: {len(compressed_rgba):,} bytes")
    
    # 手動でPDFオブジェクトを構築
    try:
        # 新しいページに一時的な画像を挿入（xref番号を取得するため）
        temp_img = Image.new('RGB', (64, 64), (0, 255, 0))
        temp_stream = io.BytesIO()
        temp_img.save(temp_stream, format='JPEG', quality=50)
        
        page2.insert_image(rect, stream=temp_stream.getvalue())
        
        # 画像のxrefを取得
        images = page2.get_images()
        if images:
            xref = images[0][0]
            print(f"画像xref: {xref}")
            
            # 手動でxrefオブジェクトを再構築
            # 警告: この方法は実験的で不安定です
            try:
                # 現在のオブジェクト情報を取得
                obj_dict = {
                    'Type': ('name', '/XObject'),
                    'Subtype': ('name', '/Image'),
                    'Width': ('int', '64'),
                    'Height': ('int', '64'),
                    'ColorSpace': ('name', '/DeviceRGB'), 
                    'BitsPerComponent': ('int', '8'),
                    'Filter': ('name', '/FlateDecode'),
                    'Length': ('int', str(len(compressed_rgba)))
                }
                
                # xrefオブジェクトを更新
                for key, value in obj_dict.items():
                    doc2.xref_set_key(xref, key, value)
                
                print("xrefオブジェクト更新完了")
                
            except Exception as e:
                print(f"xref更新エラー: {e}")
        
    except Exception as e:
        print(f"手動構築エラー: {e}")
    
    doc2.save("test_direct_stream.pdf", deflate=True)
    size2 = os.path.getsize("test_direct_stream.pdf")
    print(f"直接ストリーム: {size2:,} bytes")
    doc2.close()
    
    # 3. 結果比較
    print(f"\\n=== 結果比較 ===")
    print(f"PNG生データ: {len(png_data):,} bytes")
    print(f"RGBA生データ: {len(rgba_data):,} bytes")  
    print(f"圧縮RGBA: {len(compressed_rgba):,} bytes")
    print(f"通常埋め込み: {size1:,} bytes")
    print(f"直接ストリーム: {size2:,} bytes")
    
    # PDF内部確認
    print(f"\\n=== PDF内部確認 ===")
    for filename, label in [("test_normal_png.pdf", "通常PNG"), ("test_direct_stream.pdf", "直接")]:
        if os.path.exists(filename):
            doc = fitz.open(filename)
            page = doc[0]
            images = page.get_images()
            if images:
                xref = images[0][0]
                try:
                    stream_size = len(doc.xref_stream(xref))
                    print(f"{label}: PDF内ストリーム {stream_size:,} bytes")
                except:
                    print(f"{label}: ストリーム取得エラー")
            doc.close()
    
    # クリーンアップ
    for f in ["test_normal_png.pdf", "test_direct_stream.pdf"]:
        try:
            os.remove(f)
        except:
            pass

if __name__ == "__main__":
    test_direct_stream_injection()