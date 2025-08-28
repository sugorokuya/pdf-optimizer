#!/usr/bin/env python3
"""
画像抽出テスト - /Im4と/Im5の問題を特定
"""
import pikepdf
import io
from PIL import Image

def test_image_extraction():
    """問題の画像(/Im4, /Im5)を詳細テスト"""
    print("=== 画像抽出詳細テスト ===")
    
    pdf = pikepdf.Pdf.open('smasked-image-sample.pdf')
    page = pdf.pages[0]
    xobjects = page['/Resources']['/XObject']
    
    target_images = ['/Im4', '/Im5']
    
    for img_name in target_images:
        if img_name not in xobjects:
            print(f"{img_name}: 見つかりません")
            continue
            
        obj = xobjects[img_name]
        print(f"\n=== {img_name} ===")
        print(f"  サイズ: {obj.get('/Width', 0)}x{obj.get('/Height', 0)}")
        print(f"  フィルタ: {obj.get('/Filter')}")
        print(f"  色空間: {obj.get('/ColorSpace')}")
        print(f"  ビット深度: {obj.get('/BitsPerComponent')}")
        
        # 生データ取得テスト
        try:
            raw_data = obj.read_raw_bytes()
            print(f"  生データ: {len(raw_data):,} bytes")
        except Exception as e:
            print(f"  生データ取得エラー: {e}")
            continue
        
        # デコードテスト
        try:
            decoded_data = obj.read_bytes()
            print(f"  デコード済み: {len(decoded_data):,} bytes")
        except Exception as e:
            print(f"  デコードエラー: {e}")
            continue
        
        # SMask確認
        if '/SMask' in obj:
            smask_obj = obj['/SMask']
            print(f"  SMask: {smask_obj.get('/Width', 0)}x{smask_obj.get('/Height', 0)}")
            try:
                smask_raw = smask_obj.read_raw_bytes()
                smask_decoded = smask_obj.read_bytes()
                print(f"  SMask生データ: {len(smask_raw):,} bytes")
                print(f"  SMaskデコード: {len(smask_decoded):,} bytes")
            except Exception as e:
                print(f"  SMaskデータエラー: {e}")
        
        # PIL変換テスト（手動）
        try:
            width = int(obj['/Width'])
            height = int(obj['/Height'])
            bits = int(obj.get('/BitsPerComponent', 8))
            
            # 色空間から予想されるチャンネル数
            colorspace = obj.get('/ColorSpace')
            if isinstance(colorspace, list) and len(colorspace) > 1:
                if colorspace[0] == '/ICCBased':
                    # ICCプロファイルから判断
                    icc_stream = colorspace[1]
                    n_components = icc_stream.get('/N', 4)  # デフォルト4 (CMYK)
                    print(f"  推定色成分数: {n_components} (ICC)")
                else:
                    n_components = 3  # RGB系と仮定
                    print(f"  推定色成分数: {n_components}")
            else:
                n_components = 3  # デフォルト
                print(f"  推定色成分数: {n_components} (デフォルト)")
            
            expected_size = width * height * n_components * (bits // 8)
            print(f"  期待サイズ: {expected_size:,} bytes")
            
            if len(decoded_data) == expected_size:
                print("  ✓ サイズ一致")
                # PIL画像として構築
                if n_components == 4:
                    mode = 'CMYK'
                elif n_components == 3:
                    mode = 'RGB'
                else:
                    mode = 'L'
                
                img = Image.frombytes(mode, (width, height), decoded_data)
                print(f"  ✓ PIL画像作成成功: {img.mode} {img.size}")
                
                # RGB変換テスト
                if img.mode != 'RGB':
                    rgb_img = img.convert('RGB')
                    print(f"  ✓ RGB変換成功: {rgb_img.size}")
                
            else:
                print(f"  ⚠️ サイズ不一致: 期待{expected_size:,} vs 実際{len(decoded_data):,}")
                
        except Exception as e:
            print(f"  PIL変換エラー: {e}")
        
        print("")
    
    pdf.close()

if __name__ == '__main__':
    test_image_extraction()