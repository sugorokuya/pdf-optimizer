#!/usr/bin/env python3

import fitz
from PIL import Image, ImageChops, ImageStat
import io
import os
import math

def pdf_to_image(pdf_path, page_num=0, dpi=150):
    """PDFページを画像に変換"""
    doc = fitz.open(pdf_path)
    page = doc[page_num]
    mat = fitz.Matrix(dpi/72, dpi/72)
    pix = page.get_pixmap(matrix=mat, alpha=True)
    img_data = pix.tobytes("png")
    doc.close()
    
    img = Image.open(io.BytesIO(img_data))
    return img

def calculate_metrics(img1, img2):
    """画像品質メトリクスを計算（PIL only版）"""
    
    # サイズを合わせる
    if img1.size != img2.size:
        # 小さい方のサイズに合わせる
        min_width = min(img1.width, img2.width)
        min_height = min(img1.height, img2.height)
        img1 = img1.crop((0, 0, min_width, min_height))
        img2 = img2.crop((0, 0, min_width, min_height))
    
    # RGBに変換
    if img1.mode != 'RGB':
        img1 = img1.convert('RGB')
    if img2.mode != 'RGB':
        img2 = img2.convert('RGB')
    
    # 差分画像を作成
    diff = ImageChops.difference(img1, img2)
    
    # 統計情報取得
    stat = ImageStat.Stat(diff)
    
    # RMS (Root Mean Square) エラー計算
    rms = math.sqrt(sum([s**2 for s in stat.rms]) / len(stat.rms))
    
    # 正規化MSE（0-1の範囲）
    mse = (rms / 255.0) ** 2
    
    # PSNR計算
    if mse == 0:
        psnr = 100
    else:
        psnr = 20 * math.log10(1.0 / math.sqrt(mse))
    
    # 簡易SSIM（相関係数ベース）
    # 完全一致=1.0、全く異なる=0.0
    similarity = 1.0 - (rms / 255.0)
    
    # 黒画像検出（グレースケール変換して判定）
    gray1 = img1.convert('L')
    gray2 = img2.convert('L')
    
    # 黒画素率計算（10未満を黒とする）
    black_pixels1 = sum(1 for pixel in gray1.getdata() if pixel < 10)
    black_pixels2 = sum(1 for pixel in gray2.getdata() if pixel < 10)
    
    total_pixels = gray1.width * gray1.height
    black_ratio1 = black_pixels1 / total_pixels
    black_ratio2 = black_pixels2 / total_pixels
    
    return {
        'mse': mse * 10000,  # 見やすくするため10000倍
        'similarity': similarity,
        'psnr': psnr,
        'black_ratio_1': black_ratio1,
        'black_ratio_2': black_ratio2,
        'rms': rms
    }

def validate_pdf_quality(original_pdf, optimized_pdf, reference_pdf=None):
    """PDF最適化品質を検証"""
    print("=== PDF品質自動検証 ===")
    
    # PDF画像変換
    print("PDF画像変換中...")
    original_img = pdf_to_image(original_pdf)
    optimized_img = pdf_to_image(optimized_pdf)
    
    # サイズ情報
    print(f"\n元画像サイズ: {original_img.size}")
    print(f"最適化画像サイズ: {optimized_img.size}")
    
    # 品質メトリクス計算
    print("\n品質メトリクス計算中...")
    metrics = calculate_metrics(original_img, optimized_img)
    
    print(f"\n=== 最適化品質スコア ===")
    print(f"MSE (Mean Squared Error): {metrics['mse']:.2f} (低いほど良い)")
    print(f"Similarity: {metrics['similarity']:.4f} (高いほど良い、1.0が完全一致)")
    print(f"PSNR (Peak SNR): {metrics['psnr']:.2f} dB (高いほど良い)")
    print(f"黒画素率（元）: {metrics['black_ratio_1']*100:.1f}%")
    print(f"黒画素率（最適化）: {metrics['black_ratio_2']*100:.1f}%")
    
    # 問題判定
    print(f"\n=== 問題診断 ===")
    
    if metrics['black_ratio_2'] > 0.5 and metrics['black_ratio_1'] < 0.2:
        print("❌ 真っ黒問題検出！最適化版の50%以上が黒画素です。")
    elif metrics['similarity'] < 0.5:
        print("⚠️ 品質低下警告：Similarity < 0.5")
    elif metrics['psnr'] < 20:
        print("⚠️ 品質低下警告：PSNR < 20dB")
    else:
        print("✓ 品質は許容範囲内です。")
    
    # 参照PDF（Adobe版など）との比較
    if reference_pdf and os.path.exists(reference_pdf):
        print(f"\n=== 参照PDFとの比較 ===")
        ref_img = pdf_to_image(reference_pdf)
        ref_metrics = calculate_metrics(original_img, ref_img)
        
        print(f"参照版Similarity: {ref_metrics['similarity']:.4f}")
        print(f"最適化版Similarity: {metrics['similarity']:.4f}")
        
        if metrics['similarity'] > ref_metrics['similarity']:
            print("✓ 最適化版の方が元画像に近い")
        else:
            print(f"⚠️ 参照版の方が良好 (差: {ref_metrics['similarity'] - metrics['similarity']:.4f})")
    
    # 画像保存（デバッグ用）
    if metrics['black_ratio_2'] > 0.5:
        print("\nデバッグ画像保存中...")
        original_img.save("debug_original.png")
        optimized_img.save("debug_optimized.png")
        print("debug_original.png と debug_optimized.png を保存しました。")
    
    return metrics

if __name__ == "__main__":
    # テスト実行
    print("PDFファイル検証を開始します...")
    
    metrics = validate_pdf_quality(
        "smasked-image-sample.pdf",
        "smasked-image-sample-smask.pdf",
        "smasked-image-sample-acrobat.pdf"
    )
    
    # ファイルサイズ比較
    print(f"\n=== ファイルサイズ ===")
    original_size = os.path.getsize("smasked-image-sample.pdf")
    optimized_size = os.path.getsize("smasked-image-sample-smask.pdf")
    reduction = (1 - optimized_size / original_size) * 100
    
    print(f"元: {original_size:,} bytes")
    print(f"最適化: {optimized_size:,} bytes ({reduction:.1f}% 削減)")
    
    # 総合判定
    print(f"\n=== 総合判定 ===")
    if metrics['black_ratio_2'] > 0.5:
        print("❌ 失敗：真っ黒問題が発生しています")
    elif metrics['similarity'] > 0.8 and reduction > 50:
        print(f"✓ 成功：品質維持（Similarity={metrics['similarity']:.3f}）で{reduction:.1f}%削減")
    elif metrics['similarity'] > 0.7:
        print(f"△ 部分的成功：許容品質（Similarity={metrics['similarity']:.3f}）で{reduction:.1f}%削減")
    else:
        print(f"⚠️ 品質問題：Similarity={metrics['similarity']:.3f}")