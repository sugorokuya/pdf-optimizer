#!/usr/bin/env python3

import argparse
import os
import sys
from pathlib import Path

try:
    import fitz  # PyMuPDF
    pymupdf = fitz
except ImportError:
    try:
        import pymupdf
        fitz = pymupdf
    except ImportError:
        print("Error: PyMuPDF is not installed.")
        print("Please install it with: pip install PyMuPDF")
        sys.exit(1)


def optimize_pdf_final(input_path, output_path, optimization_level=4, image_dpi=150, 
                       trim_to_artbox=True, grayscale=False, verbose=True):
    """
    Final PDF optimization - conservative but effective approach.
    
    Args:
        input_path: Input PDF file path
        output_path: Output PDF file path
        optimization_level: Optimization level (1-4, default: 4)
        image_dpi: Target DPI for images (default: 150)
        trim_to_artbox: Whether to trim to art box (default: True)
        grayscale: Convert color images to grayscale (default: False)
        verbose: Print progress messages
    
    Returns:
        dict: Optimization results including file sizes and compression ratio
    """
    try:
        # Open the PDF document
        doc = pymupdf.open(input_path)
        
        # Check if password protected
        if doc.needs_pass:
            raise ValueError("Password protected PDFs are not supported")
        
        # Get original file size
        original_size = os.path.getsize(input_path)
        
        if verbose:
            print(f"Processing: {input_path}")
            print(f"Original size: {original_size:,} bytes")
            print(f"Optimization level: {optimization_level}")
            print(f"Image DPI: {image_dpi}")
            print(f"Trim to art box: {trim_to_artbox}")
            print(f"Grayscale conversion: {grayscale}")
        
        # Trim to art box if requested
        if trim_to_artbox:
            trimmed_count = 0
            for page_num in range(len(doc)):
                page = doc[page_num]
                try:
                    artbox = page.artbox
                    if artbox and artbox != page.rect:
                        page.set_cropbox(artbox)
                        trimmed_count += 1
                except:
                    pass
            if verbose and trimmed_count > 0:
                print(f"  Trimmed {trimmed_count} page(s) to art box")
        
        # Level 1: Basic cleaning
        if optimization_level >= 1:
            try:
                doc.scrub(
                    attached_files=False,
                    clean_pages=True,
                    embedded_files=False,
                    hidden_text=False,
                    javascript=True,
                    metadata=True,
                    redactions=True,
                    redact_images=0,
                    remove_links=False,
                    reset_fields=True,
                    reset_responses=True,
                    thumbnails=True,
                    xml_metadata=True
                )
                if verbose:
                    print("  Applied document cleaning")
            except Exception as e:
                if verbose:
                    print(f"  Warning: Document cleaning failed: {e}")
        
        # Level 2: Font optimization
        if optimization_level >= 2:
            try:
                doc.subset_fonts()
                if verbose:
                    print("  Applied font subsetting")
            except Exception as e:
                if verbose:
                    print(f"  Warning: Font subsetting failed: {e}")
        
        # Level 3+: Image optimization with conservative settings
        if optimization_level >= 3:
            # Only attempt image optimization with very conservative settings
            try:
                # Conservative quality settings to avoid destroying images
                if optimization_level == 3:
                    quality = 85  # High quality
                    dpi_threshold = image_dpi * 3  # Only very high DPI images
                else:  # level 4
                    quality = 75  # Good quality
                    dpi_threshold = image_dpi * 2  # Moderate threshold
                
                if verbose:
                    print(f"  Attempting conservative image optimization (quality={quality}, threshold={dpi_threshold} DPI)")
                
                # Try image optimization with safe parameters
                rewrite_params = {
                    'dpi_threshold': int(dpi_threshold),
                    'dpi_target': int(image_dpi),
                    'quality': quality,
                    'lossy': True,
                    'lossless': True,  # Allow lossless for small improvements
                    'set_to_gray': grayscale
                }
                
                doc.rewrite_images(**rewrite_params)
                if verbose:
                    print("  Applied image optimization")
                    
            except Exception as e:
                if verbose:
                    print(f"  Note: Image optimization skipped: {e}")
        
        # Save with appropriate compression settings
        save_options = {
            'garbage': min(optimization_level, 4),
            'deflate': True,
            'deflate_images': True,
            'deflate_fonts': True,
            'clean': True,
            'pretty': False,
            'preserve_metadata': False,
        }
        
        # Add advanced options for higher levels
        if optimization_level >= 3:
            save_options['use_objstms'] = True
        
        if optimization_level >= 4:
            try:
                # Try compression_effort if available
                save_options['compression_effort'] = 50  # Moderate effort
            except:
                pass
        
        # Save the optimized document
        try:
            doc.save(output_path, **save_options)
        except TypeError:
            # Remove unsupported options and retry
            if 'compression_effort' in save_options:
                del save_options['compression_effort']
                if verbose:
                    print("  Note: Advanced compression options not available")
            doc.save(output_path, **save_options)
        
        doc.close()
        
        # Calculate results
        optimized_size = os.path.getsize(output_path)
        compression_ratio = (1 - optimized_size / original_size) * 100
        
        if verbose:
            print(f"Optimized size: {optimized_size:,} bytes")
            print(f"Compression ratio: {compression_ratio:.1f}%")
            print(f"Saved to: {output_path}")
        
        return {
            'success': True,
            'original_size': original_size,
            'optimized_size': optimized_size,
            'compression_ratio': compression_ratio,
            'output_path': output_path
        }
        
    except Exception as e:
        if verbose:
            print(f"Error: {e}")
        return {
            'success': False,
            'error': str(e)
        }
    finally:
        if 'doc' in locals() and not doc.is_closed:
            doc.close()


def process_batch(pdf_files, output_dir=None, optimization_level=4, 
                 image_dpi=150, trim_to_artbox=True, grayscale=False, suffix='-optimized'):
    """Process multiple PDF files in batch."""
    results = []
    
    for pdf_path in pdf_files:
        pdf_path = Path(pdf_path)
        
        # Determine output path
        if output_dir:
            out_dir = Path(output_dir)
            out_dir.mkdir(parents=True, exist_ok=True)
            output_filename = pdf_path.stem + suffix + '.pdf'
            output_path = out_dir / output_filename
        else:
            output_filename = pdf_path.stem + suffix + '.pdf'
            output_path = pdf_path.parent / output_filename
        
        print(f"\nProcessing {pdf_path.name}...")
        result = optimize_pdf_final(
            str(pdf_path), 
            str(output_path),
            optimization_level=optimization_level,
            image_dpi=image_dpi,
            trim_to_artbox=trim_to_artbox,
            grayscale=grayscale,
            verbose=True
        )
        
        results.append({
            'input': str(pdf_path),
            'output': str(output_path) if result['success'] else None,
            'result': result
        })
    
    return results


def main():
    parser = argparse.ArgumentParser(
        description='Final PDF optimizer - reliable compression with quality preservation',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Optimization levels:
  1: Document cleanup - Remove metadata, thumbnails, etc. (10-20%% reduction)
  2: Font optimization - Level 1 + font subsetting (20-40%% reduction)
  3: Conservative - Level 2 + high-quality image compression (30-60%% reduction)
  4: Balanced - Level 3 + moderate image compression (40-70%% reduction)

This tool preserves text searchability and image quality while reducing file size.

Examples:
  %(prog)s document.pdf                    # Default: level 4, 150 DPI
  %(prog)s document.pdf -l 3               # Conservative optimization
  %(prog)s document.pdf -d 100 -l 4        # Target 100 DPI with balanced compression
  %(prog)s *.pdf -o compressed/            # Batch process to directory
  %(prog)s document.pdf --no-trim          # Don't trim to art box
  %(prog)s document.pdf --grayscale        # Convert images to grayscale
        """
    )
    
    parser.add_argument('pdf_files', nargs='+', help='PDF file(s) to optimize')
    parser.add_argument('-l', '--level', type=int, choices=[1, 2, 3, 4], default=4,
                        help='Optimization level 1-4 (default: 4)')
    parser.add_argument('-d', '--dpi', type=int, default=150,
                        help='Target DPI for images (default: 150)')
    parser.add_argument('-o', '--output',
                        help='Output directory (default: same as source file)')
    parser.add_argument('-s', '--suffix', default='-optimized',
                        help='Suffix for output files (default: -optimized)')
    parser.add_argument('--no-trim', action='store_true',
                        help='Do not trim to art box (default: trim enabled)')
    parser.add_argument('--grayscale', action='store_true',
                        help='Convert color images to grayscale')
    parser.add_argument('-v', '--verbose', action='store_true',
                        help='Show detailed progress')
    
    args = parser.parse_args()
    
    # Validate input files
    valid_files = []
    for pdf_file in args.pdf_files:
        if os.path.exists(pdf_file) and pdf_file.lower().endswith('.pdf'):
            valid_files.append(pdf_file)
        else:
            print(f"Warning: Skipping '{pdf_file}' (not found or not a PDF)")
    
    if not valid_files:
        print("Error: No valid PDF files found")
        sys.exit(1)
    
    # Process files
    print(f"Processing {len(valid_files)} PDF file(s)...")
    print(f"Settings: Level={args.level}, DPI={args.dpi}, Trim={'ON' if not args.no_trim else 'OFF'}, Grayscale={'ON' if args.grayscale else 'OFF'}")
    
    results = process_batch(
        valid_files,
        output_dir=args.output,
        optimization_level=args.level,
        image_dpi=args.dpi,
        trim_to_artbox=not args.no_trim,
        grayscale=args.grayscale,
        suffix=args.suffix
    )
    
    # Summary
    print("\n" + "="*60)
    print("OPTIMIZATION SUMMARY")
    print("="*60)
    
    successful = 0
    total_original = 0
    total_optimized = 0
    
    for item in results:
        result = item['result']
        if result['success']:
            successful += 1
            total_original += result['original_size']
            total_optimized += result['optimized_size']
            print(f"✓ {Path(item['input']).name}: {result['compression_ratio']:.1f}% reduced")
        else:
            print(f"✗ {Path(item['input']).name}: {result.get('error', 'Unknown error')}")
    
    if successful > 0:
        overall_ratio = (1 - total_optimized / total_original) * 100
        print(f"\nTotal: {successful}/{len(results)} files optimized")
        print(f"Overall compression: {overall_ratio:.1f}%")
        print(f"Space saved: {(total_original - total_optimized):,} bytes")
    else:
        print("\nNo files were successfully optimized")
        sys.exit(1)


if __name__ == '__main__':
    main()