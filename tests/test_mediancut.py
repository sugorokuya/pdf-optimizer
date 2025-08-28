#!/usr/bin/env python3

from PIL import Image
import io

def png_quality_to_colors(quality):
    """
    pngquantの品質レベル（0-30）をPILの色数にマッピング
    より積極的な色数削減でファイルサイズを縮小
    """
    if quality <= 5:
        return 16   # 最低品質 - より積極的
    elif quality <= 10:
        return 32
    elif quality <= 15:
        return 64
    elif quality <= 20:
        return 128
    elif quality <= 25:
        return 192
    else:  # 26-30
        return 256  # 最高品質

def optimize_png_with_mediancut(img, quality=20, verbose=True):
    """メディアンカットでPNG最適化"""
    if img.mode not in ('RGBA', 'LA'):
        if verbose:
            print(f"  透明度なし（{img.mode}）- メディアンカット不要")
        return img
    
    colors = png_quality_to_colors(quality)
    
    if verbose:
        print(f"  メディアンカット: 品質{quality} -> {colors}色")
    
    try:
        # RGBAの場合はFast Octreeを使用
        if img.mode == 'RGBA':
            quantized = img.quantize(colors=colors, method=Image.Quantize.FASTOCTREE)
            result = quantized.convert('RGBA')
        elif img.mode == 'LA':
            # LAの場合はRGBAに変換してから処理
            rgba_img = img.convert('RGBA')
            quantized = rgba_img.quantize(colors=colors, method=Image.Quantize.FASTOCTREE)
            result = quantized.convert('RGBA')
        else:
            quantized = img.quantize(colors=colors, method=Image.Quantize.MEDIANCUT)
            result = quantized
            
        return result
        
    except Exception as e:
        if verbose:
            print(f"  メディアンカットエラー: {e}")
        return img

def test_mediancut_compression():
    """メディアンカット圧縮テスト"""
    
    # テスト用RGBA画像作成（グラデーション）
    from PIL import ImageDraw
    
    img = Image.new('RGBA', (200, 200), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)
    
    # カラフルなグラデーション円を描画
    for i in range(50):
        color = (
            int(255 * i / 50),      # Red
            int(255 * (50-i) / 50), # Green  
            128,                    # Blue
            200                     # Alpha
        )
        draw.ellipse([i, i, 200-i, 200-i], fill=color)
    
    print("=== メディアンカット圧縮テスト ===")
    print(f"元画像: {img.mode}, {img.size}")
    
    # 元画像サイズ
    original_png = io.BytesIO()
    img.save(original_png, format='PNG', optimize=True, compress_level=9)
    original_size = len(original_png.getvalue())
    print(f"元PNGサイズ: {original_size:,} bytes")
    
    # 各品質レベルでテスト
    for quality in [5, 10, 15, 20, 25, 30]:
        optimized = optimize_png_with_mediancut(img, quality)
        
        # 圧縮後サイズ測定
        output = io.BytesIO()
        optimized.save(output, format='PNG', optimize=True, compress_level=9)
        new_size = len(output.getvalue())
        
        reduction = (1 - new_size / original_size) * 100
        colors = png_quality_to_colors(quality)
        
        print(f"品質{quality:2d} ({colors:3d}色): {new_size:,} bytes ({reduction:.1f}% 削減)")

if __name__ == "__main__":
    test_mediancut_compression()