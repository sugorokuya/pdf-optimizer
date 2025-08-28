#!/usr/bin/env python3

import fitz
from PIL import Image, ImageDraw
import io
import numpy as np

def create_transparency_test_pdf(output_path):
    """透明度テスト用PDFを作成"""
    doc = fitz.open()
    page = doc.new_page(width=600, height=400)
    
    # 1. 半透明の赤い円を作成
    red_circle = Image.new('RGBA', (200, 200), (0, 0, 0, 0))
    draw = ImageDraw.Draw(red_circle)
    draw.ellipse([20, 20, 180, 180], fill=(255, 0, 0, 128))  # 半透明の赤
    
    # JPEGとしてPDFに埋め込み（透明度情報は失われる）
    red_jpeg = io.BytesIO()
    red_circle.convert('RGB').save(red_jpeg, format='JPEG', quality=90)
    red_jpeg.seek(0)
    
    # 透明度マスク（SMask）を別途作成
    alpha_mask = red_circle.split()[3]  # アルファチャンネル
    mask_bytes = io.BytesIO()
    alpha_mask.save(mask_bytes, format='PNG')
    mask_bytes.seek(0)
    
    # PDFに画像を配置
    rect = fitz.Rect(50, 50, 250, 250)
    page.insert_image(rect, stream=red_jpeg.getvalue())
    
    # 2. 背景パターンを追加（透明度の効果を確認するため）
    for i in range(0, 600, 40):
        for j in range(0, 400, 40):
            if (i//40 + j//40) % 2 == 0:
                page.draw_rect(fitz.Rect(i, j, i+40, j+40), color=(0.9, 0.9, 0.9), fill=(0.9, 0.9, 0.9))
    
    # テキスト追加
    page.insert_text((300, 100), "透明度テスト", fontsize=20)
    page.insert_text((300, 130), "赤い円は半透明であるべき", fontsize=12)
    
    doc.save(output_path)
    doc.close()
    
    print(f"透明度テスト用PDF作成: {output_path}")

if __name__ == "__main__":
    create_transparency_test_pdf("transparency_test.pdf")