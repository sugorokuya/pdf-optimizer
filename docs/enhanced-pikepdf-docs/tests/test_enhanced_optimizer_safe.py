#!/usr/bin/env python3
"""
安全な最適化テスト - CMYK画像を適切に処理
"""
import io
import os
import logging
from PIL import Image
import pikepdf
import numpy as np
from enhanced_pdf_optimizer import EnhancedPDFOptimizer, OptimizationConfig

# ログレベルをDEBUGに
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def test_cmyk_image_processing():
    """CMYK画像処理のテスト"""
    print("=== CMYK画像処理テスト ===")
    
    pdf = pikepdf.Pdf.open('smasked-image-sample.pdf')
    page = pdf.pages[0]
    xobjects = page['/Resources']['/XObject']
    
    # /Im4を詳細テスト
    test_obj = xobjects['/Im4']
    print(f"\nテスト対象: /Im4")
    print(f"  サイズ: {test_obj['/Width']}x{test_obj['/Height']}")
    print(f"  フィルタ: {test_obj.get('/Filter')}")
    print(f"  色空間: {test_obj.get('/ColorSpace')}")
    
    # 既にデコードされたデータを取得
    try:
        # read_bytes()が使えない場合の回避策
        raw_data = test_obj.read_raw_bytes()
        print(f"  生データサイズ: {len(raw_data):,} bytes")
        
        # FlateDecode済みなので直接Pillow処理
        width = int(test_obj['/Width'])
        height = int(test_obj['/Height'])
        
        # 4成分（CMYK）として解釈
        expected_size = width * height * 4
        if len(raw_data) >= expected_size:
            # 4成分データからCMYK画像作成
            cmyk_data = raw_data[:expected_size]
            cmyk_image = Image.frombytes('CMYK', (width, height), cmyk_data)
            print(f"  ✓ CMYK画像作成成功: {cmyk_image.mode} {cmyk_image.size}")
            
            # RGB変換テスト
            rgb_image = cmyk_image.convert('RGB')
            print(f"  ✓ RGB変換成功: {rgb_image.size}")
            
            # JPEG保存テスト
            jpeg_output = io.BytesIO()
            rgb_image.save(jpeg_output, format='JPEG', quality=75)
            jpeg_data = jpeg_output.getvalue()
            print(f"  ✓ JPEG変換成功: {len(jpeg_data):,} bytes")
            
        else:
            print(f"  ⚠️ データサイズ不足: 期待{expected_size:,} vs 実際{len(raw_data):,}")
            
    except Exception as e:
        print(f"  ✗ 処理エラー: {e}")
    
    pdf.close()

def test_safe_optimizer():
    """安全な最適化テスト"""
    print("\n=== 安全な最適化テスト ===")
    
    # より緩い設定
    config = OptimizationConfig(
        enable_cmyk_conversion=True,
        enable_background_degradation=False,  # 背景劣化は無効
        jpeg_quality=85,  # 高品質
        min_similarity=0.90,  # 緩い品質基準
        skip_small_images=False,  # 小さい画像もテスト
        min_image_size=32
    )
    
    optimizer = EnhancedPDFOptimizer(config)
    
    # 特定の画像のみを処理するカスタム版
    pdf = pikepdf.Pdf.open('smasked-image-sample.pdf')
    page = pdf.pages[0]
    xobjects = page['/Resources']['/XObject']
    
    processed = 0
    
    for name in ['/Im4']:  # テスト対象を限定
        if name not in xobjects:
            continue
            
        obj = xobjects[name]
        print(f"\n処理中: {name}")
        
        try:
            # 手動でCMYK処理
            width = int(obj['/Width'])
            height = int(obj['/Height'])
            
            # 生データから直接処理
            raw_data = obj.read_raw_bytes()
            
            # CMYK (4成分) として処理
            expected_size = width * height * 4
            if len(raw_data) >= expected_size:
                cmyk_data = raw_data[:expected_size]
                cmyk_image = Image.frombytes('CMYK', (width, height), cmyk_data)
                rgb_image = cmyk_image.convert('RGB')
                
                # JPEG変換
                jpeg_output = io.BytesIO()
                rgb_image.save(jpeg_output, format='JPEG', quality=85, optimize=True)
                jpeg_data = jpeg_output.getvalue()
                
                print(f"  変換: {len(raw_data):,} -> {len(jpeg_data):,} bytes")
                
                # 新しいC++メソッドでPDF更新
                if '/SMask' in obj:
                    # SMask付き更新
                    smask_obj = obj['/SMask']
                    
                    # SMaskデータも処理
                    try:
                        smask_raw = smask_obj.read_raw_bytes()
                        # グレースケール画像として処理
                        smask_image = Image.frombytes('L', (width, height), smask_raw[:width*height])
                        
                        # SMask JPEG変換
                        smask_output = io.BytesIO()
                        smask_image.save(smask_output, format='JPEG', quality=85)
                        smask_data = smask_output.getvalue()
                        
                        # 拡張メソッドで更新
                        obj._write_with_smask(
                            data=jpeg_data,
                            filter=pikepdf.Name('/DCTDecode'),
                            decode_parms=None,
                            smask=smask_obj
                        )
                        
                        # SMask更新
                        smask_obj.write(smask_data, filter=pikepdf.Name('/DCTDecode'))
                        
                        print(f"  ✓ SMask付き更新完了")
                        
                    except Exception as e:
                        print(f"  SMask処理エラー: {e}")
                        # 通常更新にフォールバック
                        obj.write(jpeg_data, filter=pikepdf.Name('/DCTDecode'))
                        print(f"  ✓ 通常更新完了")
                else:
                    # 通常更新
                    obj.write(jpeg_data, filter=pikepdf.Name('/DCTDecode'))
                    print(f"  ✓ 通常更新完了")
                
                # サイズ更新
                obj['/Width'] = rgb_image.width
                obj['/Height'] = rgb_image.height
                
                processed += 1
                
            else:
                print(f"  ⚠️ データサイズ不足")
                
        except Exception as e:
            print(f"  ✗ エラー: {e}")
    
    # PDF保存
    output_path = 'safe-optimized.pdf'
    pdf.save(output_path)
    pdf.close()
    
    # 結果
    original_size = os.path.getsize('smasked-image-sample.pdf')
    optimized_size = os.path.getsize(output_path)
    reduction = (1 - optimized_size / original_size) * 100
    
    print(f"\n=== 結果 ===")
    print(f"処理成功: {processed}個")
    print(f"元ファイル: {original_size:,} bytes ({original_size/1024/1024:.1f}MB)")
    print(f"最適化後: {optimized_size:,} bytes ({optimized_size/1024/1024:.1f}MB)")
    print(f"削減率: {reduction:+.1f}%")
    print(f"出力: {output_path}")

if __name__ == '__main__':
    test_cmyk_image_processing()
    test_safe_optimizer()