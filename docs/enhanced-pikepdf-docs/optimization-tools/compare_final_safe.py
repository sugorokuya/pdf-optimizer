#!/usr/bin/env python3
"""
final-optimized.pdfとsafe-optimized.pdfを比較
"""
import pikepdf

def compare_pdfs():
    """2つのPDFを詳細比較"""
    print("=== PDF比較: final-optimized.pdf vs safe-optimized.pdf ===")
    
    # 両方のPDFを開く
    pdf_final = pikepdf.Pdf.open('final-optimized.pdf')
    pdf_safe = pikepdf.Pdf.open('safe-optimized.pdf')
    
    page_final = pdf_final.pages[0]
    page_safe = pdf_safe.pages[0]
    
    xobj_final = page_final['/Resources']['/XObject']
    xobj_safe = page_safe['/Resources']['/XObject']
    
    print(f"\nfinal-optimized.pdf: {len(xobj_final)}個の画像")
    print(f"safe-optimized.pdf: {len(xobj_safe)}個の画像")
    
    # 各画像を比較
    all_images = set(xobj_final.keys()) | set(xobj_safe.keys())
    
    for name in sorted(all_images):
        print(f"\n--- {name} ---")
        
        if name in xobj_final and name in xobj_safe:
            obj_final = xobj_final[name]
            obj_safe = xobj_safe[name]
            
            # 基本情報比較
            final_size = len(obj_final.read_raw_bytes()) if hasattr(obj_final, 'read_raw_bytes') else 0
            safe_size = len(obj_safe.read_raw_bytes()) if hasattr(obj_safe, 'read_raw_bytes') else 0
            
            final_width = obj_final.get('/Width', 0)
            final_height = obj_final.get('/Height', 0)
            safe_width = obj_safe.get('/Width', 0)
            safe_height = obj_safe.get('/Height', 0)
            
            final_filter = str(obj_final.get('/Filter', 'None'))
            safe_filter = str(obj_safe.get('/Filter', 'None'))
            
            print(f"  final: {final_width}x{final_height}, {final_size:,}bytes, {final_filter}")
            print(f"  safe:  {safe_width}x{safe_height}, {safe_size:,}bytes, {safe_filter}")
            
            # サイズが0の場合は問題
            if final_size == 0:
                print(f"  ⚠️ final版でストリームが空！")
            if safe_size == 0:
                print(f"  ⚠️ safe版でストリームが空！")
                
            # サイズ変化
            if final_size != safe_size:
                if final_size == 0:
                    print(f"  🚨 final版で画像データが消失！")
                else:
                    change = (final_size - safe_size) / safe_size * 100 if safe_size > 0 else 0
                    print(f"  📊 サイズ変化: {change:+.1f}%")
        
        elif name in xobj_final:
            print(f"  final版のみに存在")
        elif name in xobj_safe:
            print(f"  safe版のみに存在")
    
    pdf_final.close()
    pdf_safe.close()

def check_processing_logs():
    """処理ログを分析"""
    print(f"\n{'='*60}")
    print("処理ログ分析")
    print(f"{'='*60}")
    
    print("\nfinal_optimization.py では:")
    print("- 50KB以上の大きなFlateDecode画像のみ処理")
    print("- /Im4のみが処理対象となった")
    print("- 他の画像は未処理のまま残った")
    
    print("\nsafe_optimization.py では:")
    print("- 画像消失を回避するため、より保守的なアプローチ")
    print("- 全ての画像を保持")
    
    print("\n🔍 推測される原因:")
    print("- final版は1つの画像のみを最適化し、他は放置")
    print("- safe版は全画像を保持（処理はしていない可能性）")
    print("- final版で他の画像データが破損している可能性")

if __name__ == '__main__':
    compare_pdfs()
    check_processing_logs()