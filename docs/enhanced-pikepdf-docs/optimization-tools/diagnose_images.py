#!/usr/bin/env python3
"""
PDF内の画像を診断してどの画像が問題を起こしているか確認する
"""
import pikepdf
import io
from PIL import Image

def diagnose_pdf_images(pdf_path):
    """PDF内の全画像を診断"""
    print(f"\n=== {pdf_path} の画像診断 ===")
    
    pdf = pikepdf.Pdf.open(pdf_path)
    page = pdf.pages[0]
    xobjects = page['/Resources']['/XObject']
    
    image_info = []
    
    for name, obj in xobjects.items():
        if '/Subtype' in obj and obj['/Subtype'] == '/Image':
            info = {
                'name': name,
                'width': obj.get('/Width', 0),
                'height': obj.get('/Height', 0),
                'has_smask': '/SMask' in obj,
                'filter': obj.get('/Filter', None),
                'colorspace': obj.get('/ColorSpace', None),
                'bits': obj.get('/BitsPerComponent', None)
            }
            
            # ストリームサイズを取得
            try:
                stream_data = obj.read_raw_bytes()
                info['stream_size'] = len(stream_data)
            except:
                info['stream_size'] = 0
            
            # SMask情報
            if info['has_smask']:
                try:
                    smask_obj = obj['/SMask']
                    info['smask_type'] = type(smask_obj).__name__
                    if hasattr(smask_obj, 'stream_dict'):
                        info['smask_width'] = smask_obj.get('/Width', 0)
                        info['smask_height'] = smask_obj.get('/Height', 0)
                    else:
                        info['smask_width'] = 0
                        info['smask_height'] = 0
                except:
                    info['smask_type'] = 'error'
                    info['smask_width'] = 0
                    info['smask_height'] = 0
            
            image_info.append(info)
    
    # 結果表示
    print(f"画像数: {len(image_info)}個")
    print("\n詳細情報:")
    for i, info in enumerate(image_info):
        print(f"\n[{i+1}] {info['name']}:")
        print(f"  サイズ: {info['width']}x{info['height']}")
        print(f"  ストリーム: {info['stream_size']:,} bytes")
        print(f"  フィルタ: {info['filter']}")
        print(f"  色空間: {info['colorspace']}")
        print(f"  ビット深度: {info['bits']}")
        if info['has_smask']:
            print(f"  SMask: あり (type={info['smask_type']}, {info['smask_width']}x{info['smask_height']})")
        else:
            print(f"  SMask: なし")
        
        # 画像サイズが0の場合警告
        if info['width'] == 0 or info['height'] == 0:
            print("  ⚠️ 警告: 画像サイズが0です！")
        
        # ストリームサイズが0の場合警告
        if info['stream_size'] == 0:
            print("  ⚠️ 警告: ストリームデータが空です！")
    
    pdf.close()
    return image_info

def compare_pdfs(original_path, optimized_path):
    """元PDFと最適化PDFを比較"""
    print("\n" + "="*60)
    print("PDFの比較診断")
    print("="*60)
    
    print(f"\n元PDF: {original_path}")
    original_info = diagnose_pdf_images(original_path)
    
    print(f"\n最適化後PDF: {optimized_path}")
    optimized_info = diagnose_pdf_images(optimized_path)
    
    # 変化を確認
    print("\n" + "="*60)
    print("変化の分析")
    print("="*60)
    
    if len(original_info) != len(optimized_info):
        print(f"⚠️ 画像数が変化: {len(original_info)} → {len(optimized_info)}")
    
    for i in range(min(len(original_info), len(optimized_info))):
        orig = original_info[i]
        opt = optimized_info[i]
        
        if orig['width'] != opt['width'] or orig['height'] != opt['height']:
            print(f"\n{orig['name']}: サイズ変化 {orig['width']}x{orig['height']} → {opt['width']}x{opt['height']}")
        
        if orig['stream_size'] > 0 and opt['stream_size'] == 0:
            print(f"\n{orig['name']}: ⚠️ ストリームデータが消失！")
        
        if orig['has_smask'] and not opt['has_smask']:
            print(f"\n{orig['name']}: ⚠️ SMask参照が消失！")

if __name__ == '__main__':
    # 元のPDFと最適化されたPDFを比較
    compare_pdfs('smasked-image-sample.pdf', 'smasked-image-sample-pikepdf-simple.pdf')