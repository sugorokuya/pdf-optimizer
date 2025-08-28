#!/usr/bin/env python3
"""
緊急診断 - 画像消失の正確な原因を特定
"""
import pikepdf
import io
from PIL import Image
import os

def emergency_diagnosis():
    """画像消失の緊急診断"""
    print("🚨 緊急診断: 画像消失問題")
    print("="*50)
    
    files_to_check = [
        ('元ファイル', 'smasked-image-sample.pdf'),
        ('safe版', 'safe-optimized.pdf'), 
        ('perfect版', 'perfect-optimized.pdf')
    ]
    
    for label, filename in files_to_check:
        if not os.path.exists(filename):
            print(f"{label} ({filename}): ファイルが見つかりません")
            continue
            
        print(f"\n--- {label} ({filename}) ---")
        
        try:
            pdf = pikepdf.Pdf.open(filename)
            page = pdf.pages[0]
            xobjects = page['/Resources']['/XObject']
            
            # 画像オブジェクトのみ抽出
            images = []
            for name, obj in xobjects.items():
                if '/Subtype' in obj and obj['/Subtype'] == '/Image':
                    images.append((name, obj))
            
            print(f"画像数: {len(images)}個")
            
            # 各画像の状態チェック
            for name, obj in images:
                try:
                    width = int(obj.get('/Width', 0))
                    height = int(obj.get('/Height', 0))
                    stream_size = len(obj.read_raw_bytes())
                    filter_type = str(obj.get('/Filter', 'None'))
                    
                    print(f"  {name}: {width}x{height}, {stream_size:,}bytes, {filter_type}")
                    
                    # 画像として読み込み可能かテスト
                    try:
                        if '/DCTDecode' in filter_type and stream_size > 0:
                            # JPEG画像として検証
                            raw_data = obj.read_raw_bytes()
                            test_img = Image.open(io.BytesIO(raw_data))
                            print(f"    ✓ JPEG読み込み成功: {test_img.mode} {test_img.size}")
                        else:
                            # 非JPEG画像
                            print(f"    ℹ 非JPEG画像")
                    except Exception as e:
                        print(f"    ❌ 画像読み込み失敗: {e}")
                        
                    # ストリームサイズが異常に小さい場合
                    if stream_size < 1000:
                        print(f"    ⚠️ ストリームサイズが小さすぎます（{stream_size} bytes）")
                    
                except Exception as e:
                    print(f"  {name}: ❌ エラー - {e}")
            
            pdf.close()
            
        except Exception as e:
            print(f"PDF読み込みエラー: {e}")

def compare_image_content():
    """画像の内容を実際に比較"""
    print(f"\n{'='*50}")
    print("🔍 画像内容の実比較")
    print("="*50)
    
    # safe版とperfect版の比較
    try:
        pdf_safe = pikepdf.Pdf.open('safe-optimized.pdf')
        pdf_perfect = pikepdf.Pdf.open('perfect-optimized.pdf')
        
        page_safe = pdf_safe.pages[0]
        page_perfect = pdf_perfect.pages[0]
        
        xobj_safe = page_safe['/Resources']['/XObject']
        xobj_perfect = page_perfect['/Resources']['/XObject']
        
        # 同じ名前の画像を比較
        common_images = set(xobj_safe.keys()) & set(xobj_perfect.keys())
        image_common = [name for name in common_images if '/Subtype' in xobj_safe.get(name, {}) and xobj_safe[name].get('/Subtype') == '/Image']
        
        print(f"共通画像: {len(image_common)}個")
        
        for name in sorted(image_common):
            print(f"\n--- {name} ---")
            
            obj_safe = xobj_safe[name]
            obj_perfect = xobj_perfect[name]
            
            safe_size = len(obj_safe.read_raw_bytes())
            perfect_size = len(obj_perfect.read_raw_bytes())
            
            safe_filter = str(obj_safe.get('/Filter', 'None'))
            perfect_filter = str(obj_perfect.get('/Filter', 'None'))
            
            print(f"safe版:    {safe_size:,} bytes, {safe_filter}")
            print(f"perfect版: {perfect_size:,} bytes, {perfect_filter}")
            
            # サイズ変化をチェック
            if perfect_size == 0:
                print("❌ perfect版で画像データが完全消失！")
            elif perfect_size < safe_size * 0.01:  # 1%未満
                print("⚠️ perfect版で画像データが異常に小さい（データ破損の可能性）")
                
                # 画像として読めるかテスト
                try:
                    perfect_data = obj_perfect.read_raw_bytes()
                    if perfect_size > 0:
                        test_img = Image.open(io.BytesIO(perfect_data))
                        print(f"  → でも画像としては読み込み可能: {test_img.size}")
                    else:
                        print("  → データが空のため読み込み不可")
                except Exception as e:
                    print(f"  → 画像として読み込み不可: {e}")
            else:
                change_pct = (perfect_size - safe_size) / safe_size * 100
                print(f"📊 サイズ変化: {change_pct:+.1f}%")
        
        pdf_safe.close()
        pdf_perfect.close()
        
    except Exception as e:
        print(f"比較エラー: {e}")

if __name__ == '__main__':
    emergency_diagnosis()
    compare_image_content()