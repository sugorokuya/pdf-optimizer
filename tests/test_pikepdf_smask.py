#!/usr/bin/env python3

import pikepdf
from PIL import Image, ImageChops, ImageStat
import io
import os
import math

def analyze_pdf_images_with_pikepdf(pdf_path):
    """pikepdfを使ってPDF内の画像とSMaskを解析"""
    
    print(f"=== pikepdf画像解析: {pdf_path} ===")
    
    pdf = pikepdf.Pdf.open(pdf_path)
    
    images_with_smask = []
    
    for page_num, page in enumerate(pdf.pages):
        print(f"\nページ {page_num + 1}:")
        
        if '/Resources' not in page:
            continue
            
        resources = page['/Resources']
        if '/XObject' not in resources:
            continue
            
        xobjects = resources['/XObject']
        
        for name, obj in xobjects.items():
            if '/Subtype' in obj and obj['/Subtype'] == '/Image':
                width = int(obj['/Width'])
                height = int(obj['/Height'])
                
                # SMask確認
                has_smask = '/SMask' in obj
                smask_ref = None
                if has_smask:
                    smask_ref = obj['/SMask']
                
                print(f"  画像 {name}: {width}x{height}, SMask: {has_smask}")
                
                if has_smask:
                    images_with_smask.append({
                        'page': page_num,
                        'name': name,
                        'obj': obj,
                        'smask_ref': smask_ref,
                        'width': width,
                        'height': height
                    })
                    
                    # SMask詳細情報
                    try:
                        smask_obj = smask_ref
                        if hasattr(smask_obj, '__getitem__'):
                            smask_width = int(smask_obj.get('/Width', 0))
                            smask_height = int(smask_obj.get('/Height', 0))
                            print(f"    SMask: {smask_width}x{smask_height}")
                    except Exception as e:
                        print(f"    SMask解析エラー: {e}")
    
    pdf.close()
    return images_with_smask

def extract_image_with_transparency_pikepdf(pdf_obj, image_info):
    """pikepdfで透明度付き画像を正しく抽出"""
    
    try:
        # ベース画像を抽出
        base_img_obj = image_info['obj']
        
        # PdfImageとして抽出可能かチェック
        try:
            base_pil = pikepdf.PdfImage(base_img_obj).as_pil_image()
        except Exception as e:
            return None, f"ベース画像抽出エラー: {e}"
        
        # SMaskを抽出
        smask_obj = image_info['smask_ref']
        try:
            smask_pil = pikepdf.PdfImage(smask_obj).as_pil_image()
        except Exception as e:
            return None, f"SMask抽出エラー: {e}"
        
        # サイズを合わせる
        if base_pil.size != smask_pil.size:
            smask_pil = smask_pil.resize(base_pil.size, Image.Resampling.LANCZOS)
        
        # CMYK対応：RGBに変換
        if base_pil.mode == 'CMYK':
            base_pil = base_pil.convert('RGB')
        elif base_pil.mode != 'RGB':
            base_pil = base_pil.convert('RGB')
        if smask_pil.mode != 'L':
            smask_pil = smask_pil.convert('L')
            
        # RGBA合成
        r, g, b = base_pil.split()
        rgba_img = Image.merge('RGBA', (r, g, b, smask_pil))
        
        return rgba_img, True
        
    except Exception as e:
        return None, f"抽出エラー: {e}"

def optimize_image_with_jpeg_smask_pikepdf(pdf_path, output_path, quality=70):
    """pikepdfでJPEG+SMask最適化を実行"""
    
    print(f"=== pikepdf JPEG+SMask最適化 ===")
    print(f"入力: {pdf_path}")
    print(f"出力: {output_path}")
    
    # 1. 画像解析
    images_with_smask = analyze_pdf_images_with_pikepdf(pdf_path)
    
    if not images_with_smask:
        print("SMask付き画像が見つかりませんでした。")
        return False
        
    print(f"\n{len(images_with_smask)}個のSMask付き画像を発見")
    
    # 2. PDFを開いて編集
    pdf = pikepdf.Pdf.open(pdf_path)
    
    processed_count = 0
    total_size_reduction = 0
    
    for i, img_info in enumerate(images_with_smask[:3]):  # テスト用に3個まで
        print(f"\n{i+1}. 画像処理: {img_info['name']} ({img_info['width']}x{img_info['height']})")
        
        try:
            # 透明度付き画像を抽出
            rgba_img, success = extract_image_with_transparency_pikepdf(pdf, img_info)
            if not success:
                print(f"  抽出失敗: {rgba_img}")
                continue
                
            # RGBA分離
            r, g, b, a = rgba_img.split()
            rgb_img = Image.merge('RGB', (r, g, b))
            alpha_img = a
            
            # JPEGで保存
            jpeg_output = io.BytesIO()
            rgb_img.save(jpeg_output, format='JPEG', quality=quality, optimize=True)
            jpeg_data = jpeg_output.getvalue()
            
            # Alpha（SMask）をJPEGで保存（グレースケール→RGB変換）
            alpha_rgb = Image.merge('RGB', (alpha_img, alpha_img, alpha_img))
            alpha_output = io.BytesIO()
            alpha_rgb.save(alpha_output, format='JPEG', quality=quality, optimize=True)
            alpha_data = alpha_output.getvalue()
            
            print(f"  JPEG変換: RGB {len(jpeg_data):,}bytes, Alpha {len(alpha_data):,}bytes")
            
            # 3. pikepdfでPDFオブジェクトを直接編集
            page = pdf.pages[img_info['page']]
            xobjects = page['/Resources']['/XObject']
            
            # ベース画像を置換
            img_obj = xobjects[img_info['name']]
            
            # 元のストリームサイズ取得
            try:
                original_size = len(bytes(img_obj.read_raw_bytes()))
                print(f"  元サイズ: {original_size:,}bytes")
            except:
                original_size = 0
            
            # 新しいJPEG画像ストリームを設定
            img_obj.write(jpeg_data, filter=pikepdf.Name.DCTDecode)
            img_obj.Width = rgb_img.width
            img_obj.Height = rgb_img.height
            
            # SMaskオブジェクトも更新
            smask_obj = img_info['smask_ref']
            smask_obj.write(alpha_data, filter=pikepdf.Name.DCTDecode)
            smask_obj.Width = alpha_img.width
            smask_obj.Height = alpha_img.height
            
            # SMask参照を維持（pikepdfでは自動的に保持される）
            print(f"  SMask参照: {img_obj.get('/SMask', 'なし')}")
            
            processed_count += 1
            
            # サイズ削減計算
            new_total_size = len(jpeg_data) + len(alpha_data)
            if original_size > 0:
                reduction = original_size - new_total_size
                reduction_pct = (reduction / original_size) * 100
                total_size_reduction += reduction
                print(f"  削減: {reduction:,}bytes ({reduction_pct:.1f}%)")
            
        except Exception as e:
            print(f"  処理エラー: {e}")
            continue
    
    # 4. 最適化PDFを保存
    pdf.save(output_path)
    pdf.close()
    
    # 5. 結果表示
    original_size = os.path.getsize(pdf_path)
    optimized_size = os.path.getsize(output_path)
    total_reduction_pct = (1 - optimized_size / original_size) * 100
    
    print(f"\n=== 最適化結果 ===")
    print(f"処理成功: {processed_count}/{len(images_with_smask)}")
    print(f"元ファイル: {original_size:,}bytes ({original_size/1024/1024:.1f}MB)")
    print(f"最適化後: {optimized_size:,}bytes ({optimized_size/1024/1024:.1f}MB)")
    print(f"総削減率: {total_reduction_pct:.1f}%")
    
    return True

def compare_transparency_preservation():
    """透明度保持の比較テスト"""
    
    print("=== 透明度保持比較テスト ===")
    
    # pikepdf版で最適化
    success = optimize_image_with_jpeg_smask_pikepdf(
        'smasked-image-sample.pdf',
        'smasked-image-sample-pikepdf.pdf',
        quality=70
    )
    
    if not success:
        print("pikepdf最適化が失敗しました。")
        return
        
    # 品質比較を実行
    print("\n品質検証を実行中...")
    
    # 既存のテストスクリプトを活用
    os.system('source venv/bin/activate && python3 test_quality_validation.py')

if __name__ == "__main__":
    compare_transparency_preservation()