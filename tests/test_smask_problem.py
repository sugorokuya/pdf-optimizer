#!/usr/bin/env python3

import fitz
from PIL import Image
import io

def compare_smask_methods():
    """SMask処理方法の比較テスト"""
    
    print("=== SMask処理方法比較 ===")
    
    # 1. 我々のバージョンの問題調査
    our_doc = fitz.open('smasked-image-sample-smask.pdf')
    our_page = our_doc[0]
    our_images = our_page.get_images()
    
    print("我々のバージョン:")
    for i, img_info in enumerate(our_images[:3]):
        xref = img_info[0]
        try:
            base_image = our_doc.extract_image(xref)
            width = base_image['width'] 
            height = base_image['height']
            
            # SMask確認
            smask_ref = our_doc.xref_get_key(xref, 'SMask')
            colorspace = our_doc.xref_get_key(xref, 'ColorSpace')
            filter_type = our_doc.xref_get_key(xref, 'Filter')
            
            print(f"  画像{i+1} xref{xref}: {width}x{height}")
            print(f"    ColorSpace: {colorspace}")
            print(f"    Filter: {filter_type}")
            print(f"    SMask: {smask_ref}")
            
            if smask_ref and smask_ref not in [None, 'null', ('null', 'null')]:
                if isinstance(smask_ref, tuple) and len(smask_ref) >= 2:
                    smask_str = smask_ref[1]
                    if ' 0 R' in smask_str:
                        smask_xref = int(smask_str.split(' 0 R')[0])
                        try:
                            smask_colorspace = our_doc.xref_get_key(smask_xref, 'ColorSpace')
                            smask_filter = our_doc.xref_get_key(smask_xref, 'Filter')
                            print(f"    SMask {smask_xref}: CS={smask_colorspace}, Filter={smask_filter}")
                        except Exception as e:
                            print(f"    SMask {smask_xref}: エラー - {e}")
            
        except Exception as e:
            print(f"  画像{i+1}: エラー - {e}")
    
    our_doc.close()
    
    # 2. Adobe版の成功例
    print(f"\\nAdobe Acrobat版:")
    acrobat_doc = fitz.open('smasked-image-sample-acrobat.pdf')
    acrobat_page = acrobat_doc[0]
    acrobat_images = acrobat_page.get_images()
    
    for i, img_info in enumerate(acrobat_images[:3]):
        xref = img_info[0]
        try:
            base_image = acrobat_doc.extract_image(xref)
            width = base_image['width']
            height = base_image['height']
            
            # SMask確認
            smask_ref = acrobat_doc.xref_get_key(xref, 'SMask')
            colorspace = acrobat_doc.xref_get_key(xref, 'ColorSpace')
            filter_type = acrobat_doc.xref_get_key(xref, 'Filter')
            
            print(f"  画像{i+1} xref{xref}: {width}x{height}")
            print(f"    ColorSpace: {colorspace}")
            print(f"    Filter: {filter_type}")
            print(f"    SMask: {smask_ref}")
            
            if smask_ref and smask_ref not in [None, 'null', ('null', 'null')]:
                if isinstance(smask_ref, tuple) and len(smask_ref) >= 2:
                    smask_str = smask_ref[1]
                    if ' 0 R' in smask_str:
                        smask_xref = int(smask_str.split(' 0 R')[0])
                        try:
                            smask_colorspace = acrobat_doc.xref_get_key(smask_xref, 'ColorSpace')
                            smask_filter = acrobat_doc.xref_get_key(smask_xref, 'Filter')
                            print(f"    SMask {smask_xref}: CS={smask_colorspace}, Filter={smask_filter}")
                        except Exception as e:
                            print(f"    SMask {smask_xref}: エラー - {e}")
                            
        except Exception as e:
            print(f"  画像{i+1}: エラー - {e}")
    
    acrobat_doc.close()
    
    # 3. 具体的な問題の特定
    print(f"\\n=== 問題分析 ===")
    print("Adobe版の特徴:")
    print("- ColorSpace: ('xref', '540 0 R') - 参照形式")
    print("- SMaskも同様の参照形式使用")
    print("- JPEG+JPEG構成で適切に動作")
    print()
    print("我々の版の問題（推測）:")
    print("- ColorSpace設定が不適切")
    print("- SMask参照が破損している可能性")
    print("- JPEG化の際の属性設定エラー")

if __name__ == "__main__":
    compare_smask_methods()