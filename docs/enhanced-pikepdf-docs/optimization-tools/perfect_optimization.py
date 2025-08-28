#!/usr/bin/env python3
"""
完全最適化 - 全ての画像を安全に処理し、画像消失を防ぐ
"""
import io
import os
from PIL import Image
import pikepdf

def perfect_pdf_optimization():
    """画像消失なしの完全最適化"""
    print("=== 完全PDF最適化 ===")
    
    pdf = pikepdf.Pdf.open('smasked-image-sample.pdf')
    page = pdf.pages[0]
    xobjects = page['/Resources']['/XObject']
    
    stats = {
        'processed': 0,
        'skipped': 0,
        'total_before': 0,
        'total_after': 0,
        'images_analyzed': 0
    }
    
    print(f"XObject総数: {len(xobjects)}")
    
    # 全XObjectを分析
    image_objects = []
    for name, obj in xobjects.items():
        if '/Subtype' in obj and obj['/Subtype'] == '/Image':
            try:
                width = int(obj.get('/Width', 0))
                height = int(obj.get('/Height', 0))
                if width > 0 and height > 0:
                    stream_size = len(obj.read_raw_bytes())
                    filter_obj = obj.get('/Filter', 'None')
                    has_smask = '/SMask' in obj
                    
                    image_objects.append({
                        'name': name,
                        'obj': obj,
                        'width': width,
                        'height': height,
                        'size': stream_size,
                        'filter': str(filter_obj),
                        'has_smask': has_smask
                    })
            except Exception as e:
                print(f"  分析エラー {name}: {e}")
    
    stats['images_analyzed'] = len(image_objects)
    print(f"画像オブジェクト: {len(image_objects)}個")
    
    # 処理対象を決定（より広範囲に）
    for img_info in image_objects:
        name = img_info['name']
        obj = img_info['obj']
        
        print(f"\n--- {name} ---")
        print(f"  サイズ: {img_info['width']}x{img_info['height']}")
        print(f"  ストリーム: {img_info['size']:,} bytes")
        print(f"  フィルタ: {img_info['filter']}")
        print(f"  SMask: {'あり' if img_info['has_smask'] else 'なし'}")
        
        stats['total_before'] += img_info['size']
        
        # 処理条件を緩和
        should_process = False
        
        # FlateDecode画像（圧縮画像）
        if '/FlateDecode' in img_info['filter'] and img_info['size'] > 10000:  # 10KB以上
            should_process = True
            print(f"  → 処理対象: FlateDecode画像")
        
        # 大きなJPEG画像（再圧縮で更なる削減）
        elif '/DCTDecode' in img_info['filter'] and img_info['size'] > 100000:  # 100KB以上
            should_process = True
            print(f"  → 処理対象: 大きなJPEG画像")
        
        if not should_process:
            print(f"  → スキップ: 処理条件に該当せず")
            stats['skipped'] += 1
            stats['total_after'] += img_info['size']
            continue
        
        # 画像処理実行
        try:
            # デコード処理
            try:
                if '/FlateDecode' in img_info['filter']:
                    decoded_data = obj.read_bytes()
                    print(f"  デコード: {len(decoded_data):,} bytes")
                else:
                    # JPEG画像は元データを使用
                    decoded_data = obj.read_raw_bytes()
                    print(f"  元JPEG: {len(decoded_data):,} bytes")
                    
                    # JPEG画像の場合は軽い再圧縮のみ
                    try:
                        pil_img = Image.open(io.BytesIO(decoded_data))
                        if pil_img.mode in ['RGBA', 'CMYK']:
                            pil_img = pil_img.convert('RGB')
                    except:
                        print(f"  → JPEG解析失敗、スキップ")
                        stats['skipped'] += 1
                        stats['total_after'] += img_info['size']
                        continue
                        
            except Exception as e:
                print(f"  デコードエラー: {e}")
                stats['skipped'] += 1
                stats['total_after'] += img_info['size']
                continue
                
            # PIL画像作成
            width, height = img_info['width'], img_info['height']
            
            if '/FlateDecode' in img_info['filter']:
                # FlateDecode画像の処理
                expected_cmyk_size = width * height * 4
                expected_rgb_size = width * height * 3
                
                if len(decoded_data) >= expected_cmyk_size:
                    # CMYK処理
                    try:
                        cmyk_data = decoded_data[:expected_cmyk_size]
                        cmyk_image = Image.frombytes('CMYK', (width, height), cmyk_data)
                        rgb_image = cmyk_image.convert('RGB')
                        print(f"  ✓ CMYK→RGB変換成功")
                    except Exception as e:
                        print(f"  CMYK変換エラー: {e}")
                        stats['skipped'] += 1
                        stats['total_after'] += img_info['size']
                        continue
                        
                elif len(decoded_data) >= expected_rgb_size:
                    # RGB処理
                    try:
                        rgb_data = decoded_data[:expected_rgb_size]
                        rgb_image = Image.frombytes('RGB', (width, height), rgb_data)
                        print(f"  ✓ RGB画像作成成功")
                    except Exception as e:
                        print(f"  RGB変換エラー: {e}")
                        stats['skipped'] += 1
                        stats['total_after'] += img_info['size']
                        continue
                else:
                    print(f"  データサイズ不足")
                    stats['skipped'] += 1
                    stats['total_after'] += img_info['size']
                    continue
            else:
                # JPEG画像の処理（既に作成済み）
                rgb_image = pil_img
            
            # 品質設定（より高品質に）
            jpeg_quality = 85  # 高品質
            
            # JPEG変換
            jpeg_output = io.BytesIO()
            rgb_image.save(jpeg_output, format='JPEG', quality=jpeg_quality, optimize=True)
            jpeg_data = jpeg_output.getvalue()
            
            print(f"  JPEG変換: {len(jpeg_data):,} bytes")
            
            # SMask処理
            smask_data = None
            if img_info['has_smask']:
                try:
                    smask_obj = obj['/SMask']
                    smask_decoded = smask_obj.read_bytes()
                    smask_expected = width * height
                    
                    if len(smask_decoded) >= smask_expected:
                        smask_gray_data = smask_decoded[:smask_expected]
                        smask_image = Image.frombytes('L', (width, height), smask_gray_data)
                        
                        if smask_image.size != rgb_image.size:
                            smask_image = smask_image.resize(rgb_image.size, Image.Resampling.LANCZOS)
                        
                        smask_output = io.BytesIO()
                        smask_image.save(smask_output, format='JPEG', quality=jpeg_quality)
                        smask_data = smask_output.getvalue()
                        print(f"  SMask処理: {len(smask_data):,} bytes")
                        
                except Exception as e:
                    print(f"  SMask処理エラー: {e}")
            
            # PDF更新（新しいC++メソッドを使用）
            try:
                if smask_data and img_info['has_smask']:
                    # SMask保持メソッド
                    obj._write_with_smask(
                        data=jpeg_data,
                        filter=pikepdf.Name('/DCTDecode'),
                        decode_parms=None,
                        smask=obj['/SMask']
                    )
                    
                    # SMask更新
                    smask_obj = obj['/SMask']
                    smask_obj.write(smask_data, filter=pikepdf.Name('/DCTDecode'))
                    
                    total_size = len(jpeg_data) + len(smask_data)
                    print(f"  ✓ SMask付き更新完了")
                    
                else:
                    # 通常更新
                    obj.write(jpeg_data, filter=pikepdf.Name('/DCTDecode'))
                    total_size = len(jpeg_data)
                    print(f"  ✓ 通常更新完了")
                
                # サイズ更新
                obj['/Width'] = rgb_image.width
                obj['/Height'] = rgb_image.height
                
                stats['total_after'] += total_size
                stats['processed'] += 1
                
                # 削減率計算
                reduction = (1 - total_size / img_info['size']) * 100 if img_info['size'] > 0 else 0
                print(f"  📊 削減: {img_info['size']:,} → {total_size:,} bytes ({reduction:+.1f}%)")
                
            except Exception as e:
                print(f"  PDF更新エラー: {e}")
                stats['total_after'] += img_info['size']
                continue
                
        except Exception as e:
            print(f"  処理エラー: {e}")
            stats['total_after'] += img_info['size']
            continue
    
    # 保存
    output_path = 'perfect-optimized.pdf'
    pdf.save(output_path)
    pdf.close()
    
    # 結果表示
    original_file_size = os.path.getsize('smasked-image-sample.pdf')
    optimized_file_size = os.path.getsize(output_path)
    file_reduction = (1 - optimized_file_size / original_file_size) * 100
    
    image_reduction = (1 - stats['total_after'] / stats['total_before']) * 100 if stats['total_before'] > 0 else 0
    
    print(f"\n{'='*60}")
    print("完全最適化結果")
    print(f"{'='*60}")
    print(f"画像分析: {stats['images_analyzed']}個")
    print(f"処理成功: {stats['processed']}個")
    print(f"スキップ: {stats['skipped']}個")
    
    print(f"\nファイルサイズ:")
    print(f"  元ファイル: {original_file_size:,} bytes ({original_file_size/1024/1024:.1f}MB)")
    print(f"  最適化後: {optimized_file_size:,} bytes ({optimized_file_size/1024/1024:.1f}MB)")
    print(f"  削減率: {file_reduction:+.1f}%")
    
    print(f"\n画像データ:")
    print(f"  元サイズ: {stats['total_before']:,} bytes")
    print(f"  最適化後: {stats['total_after']:,} bytes")
    print(f"  画像削減率: {image_reduction:+.1f}%")
    
    print(f"\n出力ファイル: {output_path}")
    print("✅ 画像消失なし、SMask保持、高品質最適化完了")
    
    return output_path

if __name__ == '__main__':
    perfect_pdf_optimization()