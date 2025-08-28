#!/usr/bin/env python3

import fitz
from PIL import Image, ImageDraw
import io

def create_background_test_pdf(output_path):
    """背景画像テスト用PDFを作成"""
    doc = fitz.open()
    page = doc.new_page(width=600, height=800)
    
    # 1. ページ全体を覆う背景画像（透明度なし）
    bg_img = Image.new('RGB', (600, 800), (200, 220, 240))  # 薄い青背景
    draw = ImageDraw.Draw(bg_img)
    
    # グラデーション効果を追加
    for y in range(800):
        color = (
            200 + int(30 * y / 800),
            220 - int(20 * y / 800),
            240 - int(40 * y / 800)
        )
        draw.line([(0, y), (600, y)], fill=color)
    
    # JPEGとして保存
    bg_jpeg = io.BytesIO()
    bg_img.save(bg_jpeg, format='JPEG', quality=90)
    bg_jpeg.seek(0)
    
    # 背景画像をページ全体に配置（カバー率100%）
    rect_bg = fitz.Rect(0, 0, 600, 800)
    page.insert_image(rect_bg, stream=bg_jpeg.getvalue())
    
    # 2. 前面に小さな画像を追加
    small_img = Image.new('RGB', (200, 200), (255, 0, 0))  # 赤い四角
    small_jpeg = io.BytesIO()
    small_img.save(small_jpeg, format='JPEG', quality=90)
    small_jpeg.seek(0)
    
    rect_small = fitz.Rect(200, 300, 400, 500)
    page.insert_image(rect_small, stream=small_jpeg.getvalue())
    
    # 3. テキストを追加
    page.insert_text((100, 100), "背景画像テスト", fontsize=24)
    page.insert_text((100, 150), "青いグラデーションが背景", fontsize=14)
    page.insert_text((100, 200), "赤い四角が前面", fontsize=14)
    
    doc.save(output_path)
    doc.close()
    
    print(f"背景テスト用PDF作成: {output_path}")

if __name__ == "__main__":
    create_background_test_pdf("background_test.pdf")