#!/usr/bin/env python3
"""
安全なpikepdf最適化テスト - 画像消失を回避
"""
import pikepdf
import io
import os
from PIL import Image

def safe_jpeg_smask_optimization():
    """安全なJPEG+SMask最適化"""
    print("=== 安全なpikepdf最適化テスト ===")
    
    # PDFを開く
    pdf = pikepdf.Pdf.open('smasked-image-sample.pdf')
    page = pdf.pages[0]
    
    if '/Resources' not in page or '/XObject' not in page['/Resources']:
        print("XObjectが見つかりません")
        return None
    
    xobjects = page['/Resources']['/XObject']
    processed = 0
    
    for name, obj in xobjects.items():
        if processed >= 2:  # 2つまでテスト
            break
            
        if '/Subtype' in obj and obj['/Subtype'] == '/Image' and '/SMask' in obj:
            try:
                print(f"\n画像処理: {name} ({obj.get('/Width', 0)}x{obj.get('/Height', 0)})")
                
                # フィルタ確認
                filter_obj = obj.get('/Filter')
                if filter_obj is None:
                    print("  フィルタが見つかりません、スキップ")
                    continue
                    
                # FlateDecode（非JPEG）の画像のみ処理
                is_flate = False
                if isinstance(filter_obj, list) or hasattr(filter_obj, '__iter__'):
                    if '/FlateDecode' in str(filter_obj):
                        is_flate = True
                elif '/FlateDecode' in str(filter_obj):
                    is_flate = True
                
                if not is_flate:
                    print("  既にJPEG、スキップ")
                    continue
                
                # 画像を抽出
                try:
                    pil_image = obj.as_pil_image()
                    if pil_image is None:
                        print("  画像抽出に失敗、スキップ")
                        continue
                        
                    print(f"  抽出成功: モード={pil_image.mode}, サイズ={pil_image.size}")
                    
                except Exception as e:
                    print(f"  画像抽出エラー: {e}, スキップ")
                    continue
                
                # SMask画像も抽出
                smask_obj = obj['/SMask']
                try:
                    smask_image = smask_obj.as_pil_image()
                    if smask_image is None:
                        print("  SMask抽出に失敗、スキップ")
                        continue
                        
                    print(f"  SMask抽出成功: モード={smask_image.mode}, サイズ={smask_image.size}")
                    
                except Exception as e:
                    print(f"  SMask抽出エラー: {e}, スキップ")
                    continue
                
                # 元サイズ記録
                try:
                    original_size = len(bytes(obj.read_raw_bytes()))
                    smask_original_size = len(bytes(smask_obj.read_raw_bytes()))
                    print(f"  元サイズ: 主画像={original_size:,}bytes, SMask={smask_original_size:,}bytes")
                except:
                    print("  元サイズ取得不可")
                    continue
                
                # 慎重に変換 - 色空間を保持
                try:
                    # 主画像をRGBに変換（透明度を除去）
                    if pil_image.mode in ('RGBA', 'LA'):
                        # 白背景で合成
                        rgb_image = Image.new('RGB', pil_image.size, (255, 255, 255))
                        if pil_image.mode == 'RGBA':
                            rgb_image.paste(pil_image, mask=pil_image.split()[-1])
                        else:  # LA
                            rgb_image.paste(pil_image.convert('RGB'), mask=pil_image.split()[-1])
                    elif pil_image.mode == 'CMYK':
                        rgb_image = pil_image.convert('RGB')
                    else:
                        rgb_image = pil_image.convert('RGB')
                    
                    # JPEGで保存（品質を高めに設定）
                    jpeg_output = io.BytesIO()
                    rgb_image.save(jpeg_output, format='JPEG', quality=85, optimize=True)
                    jpeg_data = jpeg_output.getvalue()
                    
                    # SMaskをグレースケールJPEGで保存
                    if smask_image.mode != 'L':
                        smask_gray = smask_image.convert('L')
                    else:
                        smask_gray = smask_image
                    
                    smask_output = io.BytesIO()
                    smask_gray.save(smask_output, format='JPEG', quality=85, optimize=True)
                    smask_data = smask_output.getvalue()
                    
                    print(f"  JPEG変換: 主画像={len(jpeg_data):,}bytes, SMask={len(smask_data):,}bytes")
                    
                except Exception as e:
                    print(f"  変換エラー: {e}, スキップ")
                    continue
                
                # 安全にオブジェクトを更新
                try:
                    # 新しいwrite_with_smaskメソッドを使用
                    obj._write_with_smask(
                        data=jpeg_data,
                        filter=pikepdf.Name('/DCTDecode'),
                        decode_parms=None,
                        smask=smask_obj
                    )
                    
                    # 寸法を更新
                    obj['/Width'] = rgb_image.width
                    obj['/Height'] = rgb_image.height
                    
                    # SMaskも更新
                    smask_obj.write(smask_data, filter=pikepdf.Name('/DCTDecode'))
                    smask_obj['/Width'] = smask_gray.width
                    smask_obj['/Height'] = smask_gray.height
                    
                    print(f"  ✓ 更新完了")
                    processed += 1
                    
                except Exception as e:
                    print(f"  更新エラー: {e}")
                    continue
                    
            except Exception as e:
                print(f"  処理エラー: {e}")
                continue
    
    # 保存
    output_path = 'smasked-image-sample-safe.pdf'
    pdf.save(output_path)
    pdf.close()
    
    # 結果
    original_size = os.path.getsize('smasked-image-sample.pdf')
    optimized_size = os.path.getsize(output_path)
    reduction = (1 - optimized_size / original_size) * 100
    
    print(f"\n=== 結果 ===")
    print(f"処理成功: {processed}個")
    print(f"元ファイル: {original_size:,}bytes ({original_size/1024/1024:.1f}MB)")
    print(f"最適化後: {optimized_size:,}bytes ({optimized_size/1024/1024:.1f}MB)")
    print(f"削減率: {reduction:.1f}%")
    print(f"出力ファイル: {output_path}")
    
    return output_path

if __name__ == '__main__':
    safe_jpeg_smask_optimization()