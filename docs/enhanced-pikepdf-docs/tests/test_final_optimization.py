#!/usr/bin/env python3
"""
最終最適化テスト - デコード処理を含む完全版
"""
import io
import os
from PIL import Image
import pikepdf

def final_optimization_test():
    """最終的な安全な最適化テスト"""
    print("=== 最終最適化テスト ===")
    
    pdf = pikepdf.Pdf.open('smasked-image-sample.pdf')
    page = pdf.pages[0]
    xobjects = page['/Resources']['/XObject']
    
    processed = 0
    total_before = 0
    total_after = 0
    
    # 処理対象を特定（FlateDecodeかつ大きいサイズ）
    targets = []
    for name, obj in xobjects.items():
        if '/Subtype' in obj and obj['/Subtype'] == '/Image':
            filter_obj = obj.get('/Filter')
            if filter_obj and '/FlateDecode' in str(filter_obj):
                stream_size = len(obj.read_raw_bytes())
                if stream_size > 50000:  # 50KB以上の大きな画像のみ
                    targets.append((name, obj, stream_size))
    
    targets.sort(key=lambda x: x[2], reverse=True)  # サイズ順
    print(f"処理対象: {len(targets)}個の大きなFlateDecode画像")
    
    for name, obj, stream_size in targets:
        try:
            print(f"\n処理中: {name}")
            print(f"  元サイズ: {stream_size:,} bytes")
            
            width = int(obj['/Width'])
            height = int(obj['/Height'])
            print(f"  寸法: {width}x{height}")
            
            total_before += stream_size
            
            # デコードされたデータを取得
            try:
                decoded_data = obj.read_bytes()  # 自動デコード
                print(f"  デコード後: {len(decoded_data):,} bytes")
            except Exception as e:
                print(f"  デコードエラー: {e}")
                total_after += stream_size
                continue
            
            # 4成分（CMYK）として画像作成
            expected_cmyk_size = width * height * 4
            if len(decoded_data) >= expected_cmyk_size:
                try:
                    # CMYK画像として読み込み
                    cmyk_data = decoded_data[:expected_cmyk_size]
                    cmyk_image = Image.frombytes('CMYK', (width, height), cmyk_data)
                    print(f"  ✓ CMYK画像作成: {cmyk_image.size}")
                    
                    # RGB変換
                    rgb_image = cmyk_image.convert('RGB')
                    print(f"  ✓ RGB変換: {rgb_image.size}")
                    
                except Exception as e:
                    print(f"  CMYK処理エラー: {e}")
                    # 3成分（RGB）として試行
                    expected_rgb_size = width * height * 3
                    if len(decoded_data) >= expected_rgb_size:
                        rgb_data = decoded_data[:expected_rgb_size]
                        rgb_image = Image.frombytes('RGB', (width, height), rgb_data)
                        print(f"  ✓ RGB画像作成: {rgb_image.size}")
                    else:
                        print(f"  データ不足（RGB）")
                        total_after += stream_size
                        continue
            else:
                # 3成分（RGB）として試行
                expected_rgb_size = width * height * 3
                if len(decoded_data) >= expected_rgb_size:
                    try:
                        rgb_data = decoded_data[:expected_rgb_size]
                        rgb_image = Image.frombytes('RGB', (width, height), rgb_data)
                        print(f"  ✓ RGB画像作成: {rgb_image.size}")
                    except Exception as e:
                        print(f"  RGB処理エラー: {e}")
                        total_after += stream_size
                        continue
                else:
                    print(f"  データ不足（両方）")
                    total_after += stream_size
                    continue
            
            # JPEG変換
            jpeg_output = io.BytesIO()
            rgb_image.save(jpeg_output, format='JPEG', quality=75, optimize=True)
            jpeg_data = jpeg_output.getvalue()
            print(f"  JPEG変換: {len(jpeg_data):,} bytes")
            
            # SMask処理
            smask_data = None
            if '/SMask' in obj:
                try:
                    smask_obj = obj['/SMask']
                    
                    # SMaskデータを処理
                    try:
                        smask_decoded = smask_obj.read_bytes()
                        smask_expected_size = width * height
                        
                        if len(smask_decoded) >= smask_expected_size:
                            smask_gray_data = smask_decoded[:smask_expected_size]
                            smask_image = Image.frombytes('L', (width, height), smask_gray_data)
                            print(f"  ✓ SMask作成: {smask_image.size}")
                            
                            # サイズ調整
                            if smask_image.size != rgb_image.size:
                                smask_image = smask_image.resize(rgb_image.size, Image.Resampling.LANCZOS)
                            
                            # JPEG変換
                            smask_output = io.BytesIO()
                            smask_image.save(smask_output, format='JPEG', quality=75)
                            smask_data = smask_output.getvalue()
                            print(f"  SMask JPEG: {len(smask_data):,} bytes")
                            
                    except Exception as e:
                        print(f"  SMask処理エラー: {e}")
                        
                except Exception as e:
                    print(f"  SMask取得エラー: {e}")
            
            # PDF更新
            try:
                if smask_data and '/SMask' in obj:
                    # 新しいC++メソッドでSMask保持更新
                    obj._write_with_smask(
                        data=jpeg_data,
                        filter=pikepdf.Name('/DCTDecode'),
                        decode_parms=None,
                        smask=obj['/SMask']
                    )
                    
                    # SMask更新
                    smask_obj = obj['/SMask']
                    smask_obj.write(smask_data, filter=pikepdf.Name('/DCTDecode'))
                    print(f"  ✓ SMask付きPDF更新完了")
                    
                    total_after += len(jpeg_data) + len(smask_data)
                    
                else:
                    # 通常更新
                    obj.write(jpeg_data, filter=pikepdf.Name('/DCTDecode'))
                    print(f"  ✓ PDF更新完了")
                    
                    total_after += len(jpeg_data)
                
                # 寸法更新
                obj['/Width'] = rgb_image.width
                obj['/Height'] = rgb_image.height
                
                processed += 1
                
            except Exception as e:
                print(f"  PDF更新エラー: {e}")
                total_after += stream_size
                
        except Exception as e:
            print(f"画像処理エラー {name}: {e}")
            total_after += stream_size
            continue
    
    # 保存
    output_path = 'final-optimized.pdf'
    pdf.save(output_path)
    pdf.close()
    
    # 結果
    original_file_size = os.path.getsize('smasked-image-sample.pdf')
    optimized_file_size = os.path.getsize(output_path)
    file_reduction = (1 - optimized_file_size / original_file_size) * 100
    
    if total_before > 0:
        image_reduction = (1 - total_after / total_before) * 100
    else:
        image_reduction = 0
    
    print(f"\n{'='*60}")
    print("最終最適化結果")
    print(f"{'='*60}")
    print(f"処理成功: {processed}個")
    print(f"\nファイルサイズ:")
    print(f"  元ファイル: {original_file_size:,} bytes ({original_file_size/1024/1024:.1f}MB)")
    print(f"  最適化後: {optimized_file_size:,} bytes ({optimized_file_size/1024/1024:.1f}MB)")
    print(f"  削減率: {file_reduction:+.1f}%")
    print(f"\n画像データ:")
    print(f"  元サイズ: {total_before:,} bytes")
    print(f"  最適化後: {total_after:,} bytes")
    print(f"  画像削減率: {image_reduction:+.1f}%")
    print(f"\n出力ファイル: {output_path}")
    
    return output_path

if __name__ == '__main__':
    final_optimization_test()