#!/usr/bin/env python3

import argparse
import os
import sys
import io
from pathlib import Path
from PIL import Image

try:
    import fitz  # PyMuPDF
    pymupdf = fitz
except ImportError:
    try:
        import pymupdf
        fitz = pymupdf
    except ImportError:
        print("Error: PyMuPDF is not installed.")
        print("Please install it with: pip install PyMuPDF")
        sys.exit(1)

try:
    import pikepdf
    PIKEPDF_AVAILABLE = True
except ImportError:
    print("Warning: pikepdf is not available. Advanced SMask processing will be limited.")
    PIKEPDF_AVAILABLE = False


def should_preserve_transparency(doc, xref, verbose=False):
    """
    Simple check: only preserve PNG images with actual transparency.
    Process all JPEG images regardless of SMask.
    """
    try:
        img_dict = doc.extract_image(xref)
        if not img_dict:
            return False, "No data"
        
        img_format = img_dict.get('ext', 'unknown')
        
        # Only preserve PNG with real transparency
        if img_format == 'png':
            try:
                img = Image.open(io.BytesIO(img_dict['image']))
                
                if img.mode in ('RGBA', 'LA'):
                    if img.mode == 'RGBA':
                        alpha = img.split()[3]
                    else:
                        alpha = img.split()[1]
                    
                    alpha_min, alpha_max = alpha.getextrema()
                    
                    if alpha_min < 255:  # Has actual transparency
                        if verbose:
                            print(f"        PNG with transparency (alpha: {alpha_min}-{alpha_max})")
                        return True, "PNG transparency"
                
                if 'transparency' in img.info:
                    if verbose:
                        print(f"        PNG with transparency info")
                    return True, "PNG transparency info"
                        
            except Exception as e:
                if verbose:
                    print(f"        PNG analysis error: {e}")
        
        # Process all JPEG images, even with SMask
        if verbose and img_format in ('jpeg', 'jpg'):
            smask = doc.xref_get_key(xref, "SMask")
            if smask and smask not in [None, 'null', ('null', 'null')]:
                print(f"        JPEG with SMask - will process and preserve SMask")
        
        return False, f"{img_format} (processable)"
        
    except Exception as e:
        if verbose:
            print(f"        Error: {e}")
        return False, "Error"


def extract_smask_data(doc, smask_ref):
    """SMask（透明度マスク）データを抽出"""
    try:
        if isinstance(smask_ref, tuple) and smask_ref[0] == 'xref':
            smask_xref = int(smask_ref[1].split()[0])
            smask_dict = doc.extract_image(smask_xref)
            if smask_dict:
                smask_img = Image.open(io.BytesIO(smask_dict['image']))
                return smask_img
    except Exception as e:
        pass
    return None


def complete_jpeg_smask_separation_pikepdf(pdf_path, page_index, quality=70, image_dpi=150, preserve_background=False, verbose=True):
    """
    pikepdfを使った完全なJPEG+SMask分離処理
    PyMuPDFの制限を回避してSMask参照を維持
    
    Returns:
        success (bool): 処理成功フラグ
        processed_count (int): 処理した画像数
        result_message (str): 結果メッセージ
    """
    if not PIKEPDF_AVAILABLE:
        return False, 0, "pikepdf not available"
        
    try:
        pdf = pikepdf.Pdf.open(pdf_path)
        page = pdf.pages[page_index]
        
        if '/Resources' not in page or '/XObject' not in page['/Resources']:
            pdf.close()
            return False, 0, "No images found"
            
        xobjects = page['/Resources']['/XObject']
        processed_count = 0
        total_savings = 0
        
        for name, obj in xobjects.items():
            if '/Subtype' in obj and obj['/Subtype'] == '/Image' and '/SMask' in obj:
                try:
                    width = int(obj['/Width'])
                    height = int(obj['/Height'])
                    
                    if verbose:
                        print(f"    pikepdf処理: {name} ({width}x{height})")
                    
                    # 元サイズ取得
                    try:
                        original_size = len(bytes(obj.read_raw_bytes()))
                    except:
                        original_size = 0
                    
                    # ベース画像抽出
                    base_img = pikepdf.PdfImage(obj).as_pil_image()
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
                    if base_img.size != smask_img.size:
                        smask_img = smask_img.resize(base_img.size, Image.Resampling.LANCZOS)
                    
                    # DPI最適化（解像度ダウン）
                    original_width, original_height = base_img.size
                    
                    # 実効DPIを推定（ピクセル数ベース）
                    # 一般的なPDFでは72 DPI基準で計算
                    estimated_dpi = max(width, height) / 10  # 簡易推定
                    dpi_threshold = image_dpi * 1.5
                    
                    if estimated_dpi > dpi_threshold:
                        scale = image_dpi / estimated_dpi
                        new_width = max(int(width * scale), 32)
                        new_height = max(int(height * scale), 32)
                        
                        if verbose:
                            print(f"      DPI最適化: {width}x{height} → {new_width}x{new_height}")
                        
                        # 画像リサイズ
                        base_img = base_img.resize((new_width, new_height), Image.Resampling.LANCZOS)
                        smask_img = smask_img.resize((new_width, new_height), Image.Resampling.LANCZOS)
                    
                    # 背景画像判定（PyMuPDF版のロジックを再実装）
                    is_background = False
                    if not preserve_background:
                        # 簡易背景判定：大きい画像は背景の可能性が高い
                        img_area = base_img.width * base_img.height
                        if img_area > 1000000:  # 100万ピクセル以上は背景候補
                            is_background = True
                            if verbose:
                                print(f"      背景画像判定: {base_img.width}x{base_img.height} ({img_area:,}px)")
                    
                    # JPEG品質調整と極端劣化
                    current_quality = quality
                    if is_background:
                        current_quality = 1  # 背景画像は品質1
                        
                        # さらに極端な劣化：解像度を大幅に下げる
                        ultra_width = max(base_img.width // 4, 32)
                        ultra_height = max(base_img.height // 4, 32)
                        base_img = base_img.resize((ultra_width, ultra_height), Image.Resampling.LANCZOS)
                        smask_img = smask_img.resize((ultra_width, ultra_height), Image.Resampling.LANCZOS)
                        
                        if verbose:
                            print(f"      背景画像: 超劣化適用 → {ultra_width}x{ultra_height}, JPEG品質1")
                    
                    # JPEGで保存
                    jpeg_output = io.BytesIO()
                    base_img.save(jpeg_output, format='JPEG', quality=current_quality, optimize=True)
                    jpeg_data = jpeg_output.getvalue()
                    
                    # Alpha（SMask）をJPEGで保存
                    alpha_rgb = Image.merge('RGB', (smask_img, smask_img, smask_img))
                    alpha_output = io.BytesIO()
                    alpha_rgb.save(alpha_output, format='JPEG', quality=current_quality, optimize=True)
                    alpha_data = alpha_output.getvalue()
                    
                    # PDFオブジェクトを更新（正しい方法）
                    try:
                        # 新しいXObjectを作成
                        new_img_obj = pdf.make_stream(jpeg_data)
                        new_img_obj.Width = base_img.width
                        new_img_obj.Height = base_img.height
                        new_img_obj.Filter = pikepdf.Name.DCTDecode
                        new_img_obj.ColorSpace = obj.ColorSpace  # 元のColorSpaceを保持
                        new_img_obj.BitsPerComponent = obj.get('/BitsPerComponent', 8)
                        
                        # 新しいSMaskオブジェクトを作成
                        new_smask_obj = pdf.make_stream(alpha_data)
                        new_smask_obj.Width = smask_img.width
                        new_smask_obj.Height = smask_img.height
                        new_smask_obj.Filter = pikepdf.Name.DCTDecode
                        new_smask_obj.ColorSpace = pikepdf.Name.DeviceGray
                        new_smask_obj.BitsPerComponent = 8
                        
                        # SMask参照を設定
                        new_img_obj.SMask = new_smask_obj
                        
                        # Resources辞書で参照を更新
                        xobjects[name] = new_img_obj
                        
                        if verbose:
                            print(f"      XObject置換完了: {base_img.width}x{base_img.height}")
                            
                    except Exception as write_error:
                        if verbose:
                            print(f"      XObject置換エラー: {write_error}")
                        # エラー時は処理をスキップ
                        continue
                    
                    new_total_size = len(jpeg_data) + len(alpha_data)
                    if original_size > 0:
                        savings = original_size - new_total_size
                        total_savings += savings
                        if verbose:
                            reduction = (savings / original_size) * 100
                            print(f"      {len(jpeg_data):,}+{len(alpha_data):,}bytes, {reduction:.1f}%削減")
                    
                    processed_count += 1
                    
                except Exception as e:
                    if verbose:
                        print(f"      画像処理エラー: {e}")
                    continue
        
        # 保存（最大圧縮オプション）
        pdf.save(pdf_path, 
                 compress_streams=True,      # ストリーム再圧縮を有効
                 recompress_flate=True,     # Flateストリーム再圧縮
                 normalize_content=True,    # コンテンツストリーム最適化
                 )
        pdf.close()
        
        return True, processed_count, f"pikepdf: {processed_count}個処理, {total_savings:,}bytes削減"
        
    except Exception as e:
        if 'pdf' in locals():
            pdf.close()
        return False, 0, f"pikepdf処理エラー: {e}"


def complete_jpeg_smask_separation(doc, page, xref, img, quality=70, grayscale=False, verbose=True):
    """
    完全なJPEG+SMask分離処理 - PNG膨張問題を根本的に解決
    JPEG画像とSMaskの両方をJPEG形式で保存
    
    Returns:
        success (bool): 分離成功フラグ
        result_message (str): 結果メッセージ
    """
    try:
        if img.mode not in ('RGBA', 'LA'):
            return False, "Not RGBA/LA image"
            
        # SMask参照を取得
        smask_ref = doc.xref_get_key(xref, "SMask")
        if not smask_ref or smask_ref in [None, 'null', ('null', 'null')]:
            return False, "No SMask found"
            
        # SMask xrefを抽出
        smask_xref = None
        if isinstance(smask_ref, tuple) and len(smask_ref) >= 2:
            smask_str = smask_ref[1]
            if ' 0 R' in smask_str:
                smask_xref = int(smask_str.split(' 0 R')[0])
                
        if not smask_xref:
            return False, "Invalid SMask xref"
            
        # RGBA分離
        if img.mode == 'RGBA':
            r, g, b, a = img.split()
            rgb_img = Image.merge('RGB', (r, g, b))
            alpha_img = a
        elif img.mode == 'LA':
            l, a = img.split()
            rgb_img = Image.merge('RGB', (l, l, l))
            alpha_img = a
            
        # グレースケール変換
        if grayscale:
            rgb_img = rgb_img.convert('L')
            
        # 1. RGB部分をJPEGで保存
        jpeg_output = io.BytesIO()
        if grayscale and rgb_img.mode == 'L':
            rgb_img.save(jpeg_output, format='JPEG', quality=quality, optimize=True)
        else:
            rgb_img.save(jpeg_output, format='JPEG', quality=quality, optimize=True, progressive=True)
        new_jpeg_data = jpeg_output.getvalue()
        
        # 2. Alpha部分もJPEGで保存（グレースケール）
        alpha_rgb = Image.merge('RGB', (alpha_img, alpha_img, alpha_img))
        alpha_jpeg_output = io.BytesIO()
        alpha_rgb.save(alpha_jpeg_output, format='JPEG', quality=quality, optimize=True)
        new_alpha_data = alpha_jpeg_output.getvalue()
        
        # 3. 元画像をJPEGで置換
        page.replace_image(xref, stream=new_jpeg_data)
        
        # 4. SMaskをJPEGで置換
        page.replace_image(smask_xref, stream=new_alpha_data)
        
        # 5. オブジェクト属性を更新（サイズのみ、SMask参照は保持）
        doc.xref_set_key(xref, "Width", str(rgb_img.width))
        doc.xref_set_key(xref, "Height", str(rgb_img.height))
        # SMask参照を再設定（重要！）
        doc.xref_set_key(xref, "SMask", smask_ref)
        
        doc.xref_set_key(smask_xref, "Width", str(alpha_img.width))
        doc.xref_set_key(smask_xref, "Height", str(alpha_img.height))
        
        if verbose:
            print(f"        完全JPEG分離: RGB {len(new_jpeg_data):,}b + Alpha {len(new_alpha_data):,}b")
            
        return True, f"Success: {len(new_jpeg_data)} + {len(new_alpha_data)} bytes"
        
    except Exception as e:
        if verbose:
            print(f"        JPEG完全分離エラー: {e}")
        return False, f"Error: {e}"


def save_as_jpeg_smask_separated(img, quality=70, grayscale=False, verbose=True):
    """
    旧版：RGBA画像をJPEG(RGB) + SMask(Alpha)に分離保存
    PNG膨張問題を回避するための関数（非推奨、complete_jpeg_smask_separationを使用）
    """
    try:
        if img.mode not in ('RGBA', 'LA'):
            return False, None, None
            
        # RGB部分とアルファ部分を分離
        if img.mode == 'RGBA':
            r, g, b, a = img.split()
            rgb_img = Image.merge('RGB', (r, g, b))
            alpha_img = a
        elif img.mode == 'LA':
            l, a = img.split()
            rgb_img = Image.merge('RGB', (l, l, l))  # グレースケールをRGBに
            alpha_img = a
        
        # グレースケール変換
        if grayscale:
            rgb_img = rgb_img.convert('L')
            
        # JPEG部分の保存
        jpeg_output = io.BytesIO()
        if grayscale and rgb_img.mode == 'L':
            rgb_img.save(jpeg_output, format='JPEG', quality=quality, optimize=True)
        else:
            rgb_img.save(jpeg_output, format='JPEG', quality=quality, optimize=True, progressive=True)
        jpeg_data = jpeg_output.getvalue()
        
        # SMask部分の保存（グレースケールPNG、最大圧縮）
        smask_output = io.BytesIO()
        alpha_img.save(smask_output, format='PNG', optimize=True, compress_level=9)
        smask_data = smask_output.getvalue()
        
        if verbose:
            print(f"          RGB部分: {len(jpeg_data):,}bytes, Alpha部分: {len(smask_data):,}bytes")
            
        return True, jpeg_data, smask_data
        
    except Exception as e:
        if verbose:
            print(f"          JPEG+SMask分離エラー: {e}")
        return False, None, None


def combine_jpeg_with_smask(doc, img_dict, xref):
    """JPEG画像とSMaskを合成してRGBA画像を作成"""
    try:
        jpeg_img = Image.open(io.BytesIO(img_dict['image']))
        
        # SMask取得
        smask_ref = doc.xref_get_key(xref, "SMask")
        if not smask_ref or smask_ref in [None, 'null', ('null', 'null')]:
            return jpeg_img
        
        smask_img = extract_smask_data(doc, smask_ref)
        if smask_img:
            # RGBをRGBAに変換
            if jpeg_img.mode != 'RGB':
                jpeg_img = jpeg_img.convert('RGB')
            
            # SMaskをアルファチャンネルとしてサイズ調整
            if smask_img.size != jpeg_img.size:
                smask_img = smask_img.resize(jpeg_img.size, Image.Resampling.LANCZOS)
            
            # グレースケールのSMaskをアルファチャンネルとして使用
            if smask_img.mode != 'L':
                smask_img = smask_img.convert('L')
            
            # RGBA画像を作成
            rgba_img = Image.merge('RGBA', (*jpeg_img.split(), smask_img))
            return rgba_img
        
        return jpeg_img
        
    except Exception as e:
        return Image.open(io.BytesIO(img_dict['image']))


def png_quality_to_colors(quality):
    """
    品質レベル（0-30）をPILの色数にマッピング
    pngquantの品質設定に対応
    """
    if quality <= 5:
        return 16   # 最低品質
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


def optimize_png_with_quantization(img, png_quality=20, verbose=True):
    """色数削減でPNG最適化"""
    if img.mode not in ('RGBA', 'LA'):
        if verbose:
            print(f"        透明度なし（{img.mode}）- 色数削減不要")
        return img
    
    colors = png_quality_to_colors(png_quality)
    
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
            result = img
            
        if verbose:
            print(f"        色数削減: {colors}色")
        return result
        
    except Exception as e:
        if verbose:
            print(f"        色数削減エラー: {e}")
        return img


def has_actual_transparency(doc, xref, verbose=False):
    """
    画像が実質的に透明度を使っているかチェック
    SMaskがあっても、全体が不透明（アルファ値255）なら透明度なしと判定
    """
    try:
        # SMaskの確認
        smask_ref = doc.xref_get_key(xref, "SMask")
        if not smask_ref or smask_ref in [None, 'null', ('null', 'null')]:
            # SMaskなし
            return False
            
        # SMaskデータを抽出
        smask_img = extract_smask_data(doc, smask_ref)
        if not smask_img:
            return False
            
        # SMaskの透明度範囲を分析
        if smask_img.mode != 'L':
            smask_img = smask_img.convert('L')
            
        # アルファ値の最小値と最大値を取得
        alpha_min, alpha_max = smask_img.getextrema()
        
        # 実質的に透明度があるかの判定
        # alpha_min が 250 以上なら、ほぼ不透明と判定
        has_transparency = alpha_min < 250
        
        if verbose:
            if has_transparency:
                print(f"        実質的な透明度あり (alpha: {alpha_min}-{alpha_max})")
            else:
                print(f"        実質的な透明度なし (alpha: {alpha_min}-{alpha_max})")
                
        return has_transparency
        
    except Exception as e:
        if verbose:
            print(f"        透明度分析エラー: {e}")
        return False


def is_background_image(page, img_info, xref, doc, verbose=False):
    """
    背景画像かどうかを判定
    - ページの90%以上を覆う
    - 実質的な透明度なし（SMaskがあっても全体が不透明ならOK）
    """
    try:
        # 画像の表示領域を取得
        img_rects = page.get_image_rects(img_info)
        if not img_rects:
            return False
            
        img_rect = img_rects[0]
        
        # ページサイズを取得（アートボックス優先）
        try:
            page_rect = page.artbox
        except:
            page_rect = page.rect
            
        # 画像がページの何%を覆うか計算
        img_area = img_rect.width * img_rect.height
        page_area = page_rect.width * page_rect.height
        coverage = (img_area / page_area) * 100
        
        if coverage < 90:
            return False
            
        # 実質的な透明度チェック
        if has_actual_transparency(doc, xref, verbose):
            return False
            
        # 画像形式チェック（PNG/GIFなどの透明度チェック）
        img_dict = doc.extract_image(xref)
        if img_dict:
            img = Image.open(io.BytesIO(img_dict['image']))
            if img.mode in ('RGBA', 'LA'):
                # RGBAやLAでも実際の透明度をチェック
                if img.mode == 'RGBA':
                    alpha = img.split()[3]
                elif img.mode == 'LA':
                    alpha = img.split()[1]
                    
                alpha_min, alpha_max = alpha.getextrema()
                if alpha_min < 250:  # 実質的な透明度あり
                    return False
                    
            elif 'transparency' in img.info:
                return False
                
        if verbose:
            print(f"        背景画像検出: カバー率 {coverage:.1f}%")
            
        return True
        
    except Exception as e:
        if verbose:
            print(f"        背景判定エラー: {e}")
        return False


def apply_extreme_degradation(img, verbose=False):
    """
    背景画像に究極の劣化を適用
    - JPEG品質1
    - 最大ぼかし
    """
    try:
        # ガウシアンぼかしを最大適用
        from PIL import ImageFilter
        
        # 複数回ぼかしを適用して効果を強める
        for _ in range(3):
            img = img.filter(ImageFilter.GaussianBlur(radius=5))
        
        if verbose:
            print(f"        ぼかし適用: ガウシアンブラー x3 (radius=5)")
            
        return img
        
    except Exception as e:
        if verbose:
            print(f"        ぼかしエラー: {e}")
        return img


def process_image_with_smask_preservation(doc, page, img_info, xref, image_dpi=150, quality=70, 
                                          grayscale=False, png_quality=20, preserve_background=False, verbose=True):
    """
    Process image while preserving SMask relationship.
    """
    try:
        # Check transparency
        preserve, reason = should_preserve_transparency(doc, xref, verbose)
        
        if preserve:
            try:
                img_dict = doc.extract_image(xref)
                if img_dict:
                    return False, len(img_dict["image"]), len(img_dict["image"]), f"Preserved: {reason}"
            except:
                pass
            return False, 0, 0, f"Preserved: {reason}"
        
        # Extract image
        img_dict = doc.extract_image(xref)
        if not img_dict:
            return False, 0, 0, "No data"
        
        img_data = img_dict["image"]
        width = img_dict["width"]
        height = img_dict["height"]
        original_size = len(img_data)
        
        # Skip tiny images
        if width < 50 or height < 50 or original_size < 1024:
            return False, original_size, original_size, f"Too small: {width}x{height}"
        
        # Calculate DPI
        actual_dpi = 150
        try:
            img_rects = page.get_image_rects(img_info)
            if img_rects and len(img_rects) > 0:
                rect = img_rects[0]
                if rect.width > 0 and rect.height > 0:
                    dpi_x = width / (rect.width / 72)
                    dpi_y = height / (rect.height / 72)
                    actual_dpi = max(dpi_x, dpi_y)
        except:
            pass
        
        dpi_threshold = image_dpi * 1.5
        needs_processing = (actual_dpi > dpi_threshold) or (quality < 85 and original_size > 10240)
        
        if not needs_processing:
            if verbose:
                print(f"      Image {xref}: {width}x{height} @ {actual_dpi:.0f} DPI - optimal")
            return False, original_size, original_size, "Already optimal"
        
        # Check if this is a background image
        is_background = False
        if not preserve_background:
            is_background = is_background_image(page, img_info, xref, doc, verbose)
        
        # Process image
        try:
            # Store SMask info BEFORE processing
            original_smask = None
            try:
                original_smask = doc.xref_get_key(xref, "SMask")
                if original_smask and original_smask in [None, 'null', ('null', 'null')]:
                    original_smask = None
            except:
                pass
            
            # Get original format
            img_format = img_dict.get('ext', 'unknown')
            
            # Process with PIL - combine with SMask if present
            img = combine_jpeg_with_smask(doc, img_dict, xref)
            
            # Background images get extreme treatment
            if is_background:
                # 32 DPI固定でリサイズ
                background_dpi = 32
                scale = background_dpi / actual_dpi
                new_width = max(int(width * scale), 64)
                new_height = max(int(height * scale), 64)
                img = img.resize((new_width, new_height), Image.Resampling.LANCZOS)
                if verbose:
                    print(f"      背景画像リサイズ {xref}: {width}x{height} → {new_width}x{new_height} @ 32 DPI")
                
                # 最大ぼかし適用
                img = apply_extreme_degradation(img, verbose)
                
            # Normal resize if needed
            elif actual_dpi > dpi_threshold:
                scale = image_dpi / actual_dpi
                new_width = max(int(width * scale), 64)
                new_height = max(int(height * scale), 64)
                img = img.resize((new_width, new_height), Image.Resampling.LANCZOS)
                if verbose:
                    print(f"      Resizing {xref}: {width}x{height} @ {actual_dpi:.0f} DPI → {new_width}x{new_height} @ {image_dpi} DPI")
            
            # Determine output format and process accordingly
            output = io.BytesIO()
            saved_as_png = False
            
            # Check if image has actual transparency
            has_transparency = has_actual_transparency(doc, xref, verbose)
            
            # Check mode-based transparency
            mode_has_transparency = False
            if img.mode in ('RGBA', 'LA'):
                if img.mode == 'RGBA':
                    alpha = img.split()[3]
                else:
                    alpha = img.split()[1]
                alpha_min, alpha_max = alpha.getextrema()
                mode_has_transparency = alpha_min < 250
            elif 'transparency' in img.info:
                mode_has_transparency = True
                
            # Determine if we really need transparency
            needs_transparency = has_transparency or mode_has_transparency
            
            # Background images always become JPEG with quality 1
            if is_background:
                # Force RGB mode for JPEG
                if img.mode != 'RGB':
                    if img.mode == 'RGBA':
                        background = Image.new('RGB', img.size, (255, 255, 255))
                        background.paste(img, mask=img.split()[3])
                        img = background
                    else:
                        img = img.convert('RGB')
                
                # Save with ultimate compression
                img.save(output, format='JPEG', quality=1, optimize=True, progressive=True)
                if verbose:
                    print(f"        背景画像: JPEG品質1で保存")
                    
            # For images with ACTUAL transparency, use PNG with aggressive compression
            elif needs_transparency:
                # JPEG+SMask分離は現在無効化（SMask更新処理が未完成のため）
                # TODO: JPEG+SMask完全分離処理の実装
                
                if True:  # 完全JPEG+SMask分離を有効化
                    # 完全JPEG+SMask分離処理を実行
                    success, result = complete_jpeg_smask_separation(
                        doc, page, xref, img, quality, grayscale, verbose
                    )
                    
                    if success:
                        # 分離成功時は処理済み（replace_imageが内部で実行されている）
                        return True, original_size, 0, "Complete JPEG+SMask separation"
                else:
                    # 分離失敗時はPNGフォールバック（最小限に）
                    if img.mode == 'CMYK':
                        img = img.convert('RGB')
                    elif img.mode == 'P' and 'transparency' not in img.info:
                        img = img.convert('RGB')
                    
                    if grayscale and img.mode not in ('LA', 'L'):
                        if img.mode == 'RGBA':
                            # Convert RGBA to LA
                            rgb = img.convert('RGB').convert('L')
                            alpha = img.split()[3]
                            img = Image.merge('LA', (rgb, alpha))
                        else:
                            img = img.convert('L')
                    
                    # PNG色数削減適用（極限設定）
                    img = optimize_png_with_quantization(img, 1, verbose)  # 品質1で最小化
                    
                    # Save as PNG with compression
                    img.save(output, format='PNG', optimize=True, compress_level=9)
                    saved_as_png = True
                    if verbose:
                        print(f"        PNG保存（極限圧縮、色数8）")
                    
            else:
                # No transparency needed - convert to JPEG for ALL opaque images
                if verbose:
                    if original_smask:
                        print(f"        実質透明度なし - JPEGに変換")
                    else:
                        print(f"        透明度なし - JPEGに変換")
                        
                # Force RGB mode for JPEG
                if img.mode != 'RGB':
                    if img.mode == 'RGBA':
                        # RGBAの場合、アルファチャンネルを白背景で合成
                        background = Image.new('RGB', img.size, (255, 255, 255))
                        background.paste(img, mask=img.split()[3])
                        img = background
                    elif img.mode == 'LA':
                        # LAの場合も同様に処理
                        background = Image.new('RGB', img.size, (255, 255, 255))
                        rgb_img = img.convert('RGB')
                        background.paste(rgb_img, mask=img.split()[1])
                        img = background
                    elif img.mode in ('CMYK', 'P'):
                        img = img.convert('RGB')
                    elif img.mode == 'L':
                        # グレースケールはそのまま使用可能
                        pass
                    else:
                        img = img.convert('RGB')
                
                if grayscale and img.mode != 'L':
                    img = img.convert('L')
                
                # Save as JPEG with appropriate quality
                img.save(output, format='JPEG', quality=quality, optimize=True, progressive=True)
                if verbose:
                    print(f"        JPEG保存: 品質{quality}")
            
            new_img_data = output.getvalue()
            new_size = len(new_img_data)
            
            if new_size >= original_size * 0.95:
                return False, original_size, original_size, "Not beneficial"
            
            # Replace image with SMask preservation
            try:
                page.replace_image(xref, stream=new_img_data)
                
                # Restore SMask if it existed and we're using JPEG format
                if original_smask:
                    # PNG images don't need SMask restoration as they have built-in transparency
                    if saved_as_png:
                        if verbose:
                            print(f"        PNG format - SMask not needed")
                    else:
                        # For JPEG, try to restore SMask
                        try:
                            doc.xref_set_key(xref, "SMask", original_smask)
                            if verbose:
                                print(f"        SMask preserved")
                        except Exception as smask_error:
                            if verbose:
                                print(f"        SMask restore failed: {smask_error}")
                
                # Verify success
                replaced = doc.extract_image(xref)
                if replaced and replaced['width'] == img.size[0]:
                    reduction = (1 - new_size / original_size) * 100
                    if verbose:
                        print(f"      Compressed {xref}: {original_size:,} → {new_size:,} bytes ({reduction:.1f}% reduction)")
                    return True, original_size, new_size, None
                    
            except Exception as e:
                if verbose:
                    print(f"        Replacement failed: {e}")
                
            return False, original_size, original_size, "Replacement failed"
                
        except Exception as e:
            return False, original_size, original_size, f"Processing error: {e}"
            
    except Exception as e:
        return False, 0, 0, f"Error: {e}"


def optimize_pdf_simple_smask(input_path, output_path, optimization_level=4, image_dpi=150, 
                              trim_to_artbox=True, grayscale=False, png_quality=20, 
                              preserve_background=False, verbose=True):
    """
    Simple PDF optimization with SMask-aware processing.
    """
    try:
        doc = pymupdf.open(input_path)
        
        if doc.needs_pass:
            raise ValueError("Password protected PDFs not supported")
        
        original_size = os.path.getsize(input_path)
        
        if verbose:
            print(f"Processing: {input_path}")
            print(f"Original size: {original_size:,} bytes")
            print(f"Level: {optimization_level}, DPI: {image_dpi}")
        
        # Art box trimming
        if trim_to_artbox:
            trimmed = 0
            for page_num in range(len(doc)):
                page = doc[page_num]
                try:
                    artbox = page.artbox
                    if artbox and artbox != page.rect:
                        page.set_cropbox(artbox)
                        trimmed += 1
                except:
                    pass
            if verbose and trimmed > 0:
                print(f"  Trimmed {trimmed} page(s)")
        
        # Basic cleanup
        if optimization_level >= 1:
            try:
                doc.scrub(
                    attached_files=False,
                    clean_pages=True,
                    embedded_files=False,
                    hidden_text=False,
                    javascript=True,
                    metadata=True,
                    redactions=True,
                    redact_images=0,
                    remove_links=False,
                    reset_fields=True,
                    reset_responses=True,
                    thumbnails=True,
                    xml_metadata=True
                )
                if verbose:
                    print("  Level 1: Cleanup")
            except:
                pass
        
        if optimization_level >= 2:
            try:
                doc.subset_fonts()
                if verbose:
                    print("  Level 2: Font subsetting")
            except:
                pass
        
        # Image optimization
        if optimization_level >= 3:
            quality = 50 if optimization_level == 3 else 30
            
            # pikepdf高度処理（SMask付き画像）
            if PIKEPDF_AVAILABLE:
                if verbose:
                    print(f"  pikepdf高度処理を実行中...")
                
                # 一旦保存してpikepdfで処理
                temp_path = output_path + '.temp'
                doc.save(temp_path, garbage=1, deflate=True)
                doc.close()
                
                total_pikepdf_processed = 0
                
                # 各ページをpikepdfで処理
                for page_num in range(len(pymupdf.open(temp_path))):
                    success, processed_count, result_msg = complete_jpeg_smask_separation_pikepdf(
                        temp_path, page_num, quality, image_dpi, preserve_background, verbose
                    )
                    if success:
                        total_pikepdf_processed += processed_count
                        if verbose and processed_count > 0:
                            print(f"    ページ{page_num+1}: {result_msg}")
                
                if total_pikepdf_processed > 0:
                    if verbose:
                        print(f"  pikepdf処理完了: {total_pikepdf_processed}個のSMask画像を最適化")
                
                # 処理済みファイルを再オープン
                doc = pymupdf.open(temp_path)
                
                # pikepdf処理を行った場合、PyMuPDF後処理はスキップ
                if verbose:
                    print(f"  PyMuPDF後処理をスキップ（pikepdf処理済み）")
                
                all_images = {}  # 空にしてPyMuPDF処理をスキップ
                
            else:
                # pikepdf非対応時は従来処理
                all_images = {}
                for page_num in range(len(doc)):
                    page = doc[page_num]
                    for img in page.get_images():
                        xref = img[0]
                        if xref not in all_images:
                            all_images[xref] = (page, img)
                
                if verbose:
                    print(f"  Found {len(all_images)} image(s), quality: {quality}")
            
            # 残りの画像を従来方式で処理
            processed = 0
            preserved = 0
            skipped = 0
            total_orig = 0
            total_new = 0
            
            for xref, (page, img) in all_images.items():
                success, orig, new, msg = process_image_with_smask_preservation(
                    doc, page, img, xref, image_dpi, quality, grayscale, png_quality, 
                    preserve_background, verbose
                )
                
                if success:
                    processed += 1
                    total_orig += orig
                    total_new += new
                elif msg and "Preserved" in msg:
                    preserved += 1
                else:
                    skipped += 1
            
            if verbose:
                if processed > 0:
                    reduction = (1 - total_new / total_orig) * 100
                    print(f"  PyMuPDF処理: {processed} images ({reduction:.1f}% reduction)")
                if preserved > 0:
                    print(f"  Preserved: {preserved} images")
                if skipped > 0:
                    print(f"  Skipped: {skipped} images")
            
            # 最終保存処理の判定
            if PIKEPDF_AVAILABLE and 'temp_path' in locals() and os.path.exists(temp_path):
                # pikepdf処理を行った場合：temp_pathが最新版
                if verbose:
                    print(f"  pikepdf処理版を最終出力として使用")
                
                doc.close()  # PyMuPDF docを閉じる
                
                # pikepdf処理済みファイルを最終出力にコピー
                import shutil
                shutil.move(temp_path, output_path)
                
                if verbose:
                    print(f"  pikepdf処理版を保存: {output_path}")
                    
            else:
                # pikepdf非対応または処理なしの場合：従来通りPyMuPDF保存
                save_options = {
                    'garbage': min(optimization_level, 4),
                    'deflate': True,
                    'deflate_images': True,
                    'deflate_fonts': True,
                    'clean': True,
                    'pretty': False,
                    'preserve_metadata': False,
                }
                
                if optimization_level >= 3:
                    save_options['use_objstms'] = True
                
                doc.save(output_path, **save_options)
                doc.close()
                
                if verbose:
                    print(f"  PyMuPDF版を保存: {output_path}")
        
        # Stats
        optimized_size = os.path.getsize(output_path)
        compression = (1 - optimized_size / original_size) * 100
        
        if verbose:
            print(f"Final size: {optimized_size:,} bytes ({compression:.1f}% reduction)")
        
        return {
            'success': True,
            'original_size': original_size,
            'optimized_size': optimized_size,
            'compression_ratio': compression,
            'output_path': output_path
        }
        
    except Exception as e:
        if verbose:
            print(f"Error: {e}")
        return {'success': False, 'error': str(e)}
    finally:
        if 'doc' in locals() and not doc.is_closed:
            doc.close()


def main():
    parser = argparse.ArgumentParser(description='Simple PDF optimization with SMask support')
    parser.add_argument('pdf_files', nargs='+', help='PDF files')
    parser.add_argument('-l', '--level', type=int, choices=[1,2,3,4], default=4)
    parser.add_argument('-d', '--dpi', type=int, default=150)
    parser.add_argument('-o', '--output', help='Output directory')
    parser.add_argument('-s', '--suffix', default='-smask')
    parser.add_argument('--no-trim', action='store_true')
    parser.add_argument('--grayscale', action='store_true')
    parser.add_argument('--png-quality', type=int, default=20, choices=range(1,31), 
                        help='PNG quality for transparency images (1-30, like pngquant)')
    parser.add_argument('--preserve-background', action='store_true',
                        help='Preserve background images without extreme degradation')
    parser.add_argument('-v', '--verbose', action='store_true')
    
    args = parser.parse_args()
    
    for pdf_file in args.pdf_files:
        if not os.path.exists(pdf_file):
            print(f"Error: '{pdf_file}' not found")
            continue
        
        if args.output:
            output_dir = Path(args.output)
            output_dir.mkdir(parents=True, exist_ok=True)
            output_path = output_dir / (Path(pdf_file).stem + args.suffix + '.pdf')
        else:
            output_path = Path(pdf_file).parent / (Path(pdf_file).stem + args.suffix + '.pdf')
        
        result = optimize_pdf_simple_smask(
            pdf_file, 
            str(output_path),
            optimization_level=args.level,
            image_dpi=args.dpi,
            trim_to_artbox=not args.no_trim,
            grayscale=args.grayscale,
            png_quality=args.png_quality,
            preserve_background=args.preserve_background,
            verbose=args.verbose
        )
        
        if result['success']:
            print(f"✓ {Path(pdf_file).name}: {result['compression_ratio']:.1f}% reduced")
        else:
            print(f"✗ {Path(pdf_file).name}: {result.get('error', 'Error')}")


if __name__ == '__main__':
    main()