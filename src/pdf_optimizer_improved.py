#!/usr/bin/env python3

import argparse
import os
import sys
import io
from pathlib import Path
from PIL import Image

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


def process_image_safely(doc, page, img_info, xref, image_dpi=150, quality=70, grayscale=False, verbose=True):
    """
    Process a single image in the PDF with improved error handling and multiple fallback methods.
    
    Returns:
        tuple: (success, original_size, new_size, error_message)
    """
    try:
        # Check if image has transparency/mask BEFORE extracting
        has_transparency = False
        try:
            smask = doc.xref_get_key(xref, "SMask")
            mask = doc.xref_get_key(xref, "Mask")
            
            # Check if image has soft mask (alpha channel)
            if smask and smask not in [None, 'null', ('null', 'null')]:
                has_transparency = True
                if verbose:
                    print(f"      Image {xref} has SMask (transparency) - will preserve")
            
            # Check if image has hard mask
            if mask and mask not in [None, 'null', ('null', 'null')]:
                # Check if it's a real mask (not just null)
                if isinstance(mask, tuple) and mask[0] != 'null':
                    has_transparency = True
                    if verbose:
                        print(f"      Image {xref} has Mask - will preserve")
        except:
            pass
        
        # If image has transparency, skip processing to preserve it
        if has_transparency:
            # Get basic info for reporting
            try:
                img_dict = doc.extract_image(xref)
                if img_dict:
                    original_size = len(img_dict["image"])
                    return False, original_size, original_size, "Has transparency - preserving original"
            except:
                pass
            return False, 0, 0, "Has transparency - preserving original"
        
        # Extract the image
        img_dict = doc.extract_image(xref)
        if not img_dict:
            return False, 0, 0, "Could not extract image data"
        
        img_data = img_dict["image"]
        img_ext = img_dict["ext"]
        width = img_dict["width"]
        height = img_dict["height"]
        
        original_size = len(img_data)
        
        # Skip very small images to avoid artifacts
        if width < 50 or height < 50 or original_size < 1024:
            return False, original_size, original_size, f"Image too small: {width}x{height}"
        
        # Calculate actual DPI more robustly
        actual_dpi = 150  # Default fallback
        try:
            # Try multiple methods to get image placement
            img_rects = page.get_image_rects(img_info)
            if img_rects and len(img_rects) > 0:
                rect = img_rects[0]
                if rect.width > 0 and rect.height > 0:
                    # Calculate DPI based on display size vs actual size
                    display_width_inches = rect.width / 72  # 72 points per inch
                    display_height_inches = rect.height / 72
                    
                    if display_width_inches > 0 and display_height_inches > 0:
                        dpi_x = width / display_width_inches
                        dpi_y = height / display_height_inches
                        actual_dpi = max(dpi_x, dpi_y)
                        
        except Exception as dpi_error:
            if verbose:
                print(f"      Warning: DPI calculation failed for {xref}: {dpi_error}")
        
        # Determine if processing is needed
        dpi_threshold = image_dpi * 1.5  # More conservative threshold
        needs_processing = (actual_dpi > dpi_threshold) or (quality < 85 and original_size > 10240)
        
        if not needs_processing:
            if verbose:
                print(f"      Skipping {xref}: {width}x{height} ({actual_dpi:.0f} DPI) - already optimal")
            return False, original_size, original_size, "Already optimal"
        
        # Process the image
        try:
            # Load image with PIL
            img = Image.open(io.BytesIO(img_data))
            original_mode = img.mode
            
            # Calculate new dimensions if DPI reduction needed
            if actual_dpi > dpi_threshold:
                scale = image_dpi / actual_dpi
                new_width = max(int(width * scale), 64)  # Ensure minimum size
                new_height = max(int(height * scale), 64)
                
                # Use high-quality resampling
                img = img.resize((new_width, new_height), Image.Resampling.LANCZOS)
                if verbose:
                    print(f"      Resizing {xref}: {width}x{height} ({actual_dpi:.0f} DPI) → {new_width}x{new_height} ({image_dpi} DPI)")
            
            # Handle different color modes properly - avoid unnecessary background creation
            if img.mode == 'CMYK':
                # CMYK requires special handling
                img = img.convert('RGB')
            elif img.mode == 'RGBA':
                # Check if image actually has transparency
                alpha_channel = img.split()[3]
                alpha_min, alpha_max = alpha_channel.getextrema()
                
                if alpha_min == 255 and alpha_max == 255:
                    # No transparency - just convert to RGB
                    img = img.convert('RGB')
                else:
                    # Has transparency - composite with white background only if needed
                    background = Image.new('RGB', img.size, (255, 255, 255))
                    background.paste(img, mask=alpha_channel)
                    img = background
            elif img.mode == 'LA':
                # Grayscale with alpha - check if actually has transparency
                alpha_channel = img.split()[1]
                alpha_min, alpha_max = alpha_channel.getextrema()
                
                if alpha_min == 255 and alpha_max == 255:
                    # No transparency - just convert to L
                    img = img.convert('L')
                else:
                    # Has transparency - convert to RGB with white background
                    background = Image.new('RGB', img.size, (255, 255, 255))
                    rgb_img = img.convert('RGB')
                    background.paste(rgb_img, mask=alpha_channel)
                    img = background
            elif img.mode == 'P':
                # Palette mode - check for transparency
                if 'transparency' in img.info:
                    # Has transparency - convert carefully
                    img = img.convert('RGBA')
                    alpha_channel = img.split()[3]
                    alpha_min, alpha_max = alpha_channel.getextrema()
                    
                    if alpha_min == 255 and alpha_max == 255:
                        # Transparent color not actually used
                        img = img.convert('RGB')
                    else:
                        # Has actual transparency
                        background = Image.new('RGB', img.size, (255, 255, 255))
                        background.paste(img, mask=alpha_channel)
                        img = background
                else:
                    # No transparency - direct conversion
                    img = img.convert('RGB')
            elif img.mode not in ('RGB', 'L'):
                # Convert any other modes to RGB
                img = img.convert('RGB')
            
            # Convert to grayscale if requested
            if grayscale and img.mode != 'L':
                img = img.convert('L')
            
            # Optimize JPEG encoding parameters
            save_options = {
                'format': 'JPEG',
                'quality': quality,
                'optimize': True,
                'progressive': True,  # Progressive JPEG for better compression
            }
            
            # For grayscale images, ensure proper subsampling
            if img.mode == 'L':
                save_options['subsampling'] = 0  # No chroma subsampling for grayscale
            
            # Save compressed image
            output = io.BytesIO()
            img.save(output, **save_options)
            new_img_data = output.getvalue()
            new_size = len(new_img_data)
            
            # Skip if compression made it worse (rare but possible)
            if new_size >= original_size * 0.95:  # Allow 5% threshold
                return False, original_size, original_size, "Compression not beneficial"
            
            # Try multiple replacement methods with better error handling and layer preservation
            replacement_success = False
            last_error = None
            
            # Method 1: Use page.replace_image (preserves layer order)
            try:
                # Get original image properties to preserve them
                original_obj = doc.xref_get_key(xref, "")  # Get original object
                
                # Replace the image using the safest method
                page.replace_image(xref, stream=new_img_data)
                
                # Verify the replacement was successful and dimensions are correct
                # This helps catch cases where the replacement might have failed silently
                try:
                    replaced_dict = doc.extract_image(xref)
                    if replaced_dict and replaced_dict['width'] == img.size[0] and replaced_dict['height'] == img.size[1]:
                        replacement_success = True
                    else:
                        raise Exception("Image replacement verification failed - dimensions mismatch")
                except:
                    raise Exception("Image replacement verification failed - could not extract replaced image")
                
            except Exception as e:
                last_error = str(e)
                
                # Method 2: Direct stream replacement with careful property preservation
                try:
                    # Store original image properties that we want to preserve
                    original_props = {}
                    try:
                        original_props['ColorSpace'] = doc.xref_get_key(xref, "ColorSpace")
                        original_props['BitsPerComponent'] = doc.xref_get_key(xref, "BitsPerComponent")
                        original_props['Interpolate'] = doc.xref_get_key(xref, "Interpolate")
                    except:
                        pass
                    
                    # Clear potentially problematic filters
                    try:
                        doc.xref_set_key(xref, "Filter", "null")
                        doc.xref_set_key(xref, "DecodeParms", "null")
                        doc.xref_set_key(xref, "Length", "null")
                    except:
                        pass
                    
                    # Update the image stream with JPEG data
                    doc.xref_stream(xref, new_img_data)
                    
                    # Set JPEG-specific properties
                    doc.xref_set_key(xref, "Filter", "/DCTDecode")
                    doc.xref_set_key(xref, "Length", str(new_size))
                    doc.xref_set_key(xref, "Width", str(img.size[0]))
                    doc.xref_set_key(xref, "Height", str(img.size[1]))
                    
                    # Set appropriate color space
                    if grayscale or img.mode == 'L':
                        doc.xref_set_key(xref, "ColorSpace", "/DeviceGray")
                    else:
                        doc.xref_set_key(xref, "ColorSpace", "/DeviceRGB")
                    
                    doc.xref_set_key(xref, "BitsPerComponent", "8")
                    
                    # Preserve certain original properties if they exist
                    if 'Interpolate' in original_props and original_props['Interpolate'] not in [None, 'null']:
                        doc.xref_set_key(xref, "Interpolate", original_props['Interpolate'])
                    
                    replacement_success = True
                    
                except Exception as e2:
                    last_error = f"Method 1: {e}, Method 2: {e2}"
            
            if replacement_success:
                reduction = (1 - new_size / original_size) * 100
                if verbose:
                    print(f"      Compressed {xref}: {original_size:,} → {new_size:,} bytes ({reduction:.1f}% reduction)")
                return True, original_size, new_size, None
            else:
                return False, original_size, original_size, f"Replacement failed: {last_error}"
                
        except Exception as process_error:
            return False, original_size, original_size, f"Processing failed: {process_error}"
            
    except Exception as e:
        return False, 0, 0, f"Extraction failed: {e}"


def optimize_pdf_improved(input_path, output_path, optimization_level=4, image_dpi=150, 
                         trim_to_artbox=True, grayscale=False, verbose=True):
    """
    Improved PDF optimization with robust image processing and fallback mechanisms.
    
    Args:
        input_path: Input PDF file path
        output_path: Output PDF file path
        optimization_level: Garbage collection level (1-4, default: 4)
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
        
        # Step 1: Art box trimming
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
        
        # Step 2: Basic optimizations
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
                    print("  Applied level 1 optimization: Document cleanup")
            except Exception as e:
                if verbose:
                    print(f"  Warning: Document cleanup failed: {e}")
        
        if optimization_level >= 2:
            try:
                doc.subset_fonts()
                if verbose:
                    print("  Applied level 2 optimization: Font subsetting")
            except Exception as e:
                if verbose:
                    print(f"  Warning: Font subsetting failed: {e}")
        
        # Step 3: Image optimization (levels 3 and 4)
        if optimization_level >= 3:
            quality = 75 if optimization_level == 3 else 50
            
            # Collect all unique images
            all_images = {}  # xref -> (page, img_info, page_count)
            image_usage = {}  # xref -> count
            
            for page_num in range(len(doc)):
                page = doc[page_num]
                image_list = page.get_images()
                
                for img in image_list:
                    xref = img[0]
                    if xref not in all_images:
                        all_images[xref] = (page, img, page_num + 1)
                        image_usage[xref] = 1
                    else:
                        image_usage[xref] += 1
            
            if verbose:
                total_refs = sum(image_usage.values())
                print(f"  Found {len(all_images)} unique image(s) with {total_refs} total reference(s)")
                print(f"  Target quality: {quality}, DPI: {image_dpi}")
            
            # Process images with detailed tracking
            processed_count = 0
            failed_count = 0
            total_original_image_size = 0
            total_compressed_image_size = 0
            error_summary = {}
            
            for xref, (page, img, page_num) in all_images.items():
                success, orig_size, new_size, error_msg = process_image_safely(
                    doc, page, img, xref, image_dpi, quality, grayscale, verbose
                )
                
                if success:
                    processed_count += 1
                    total_original_image_size += orig_size
                    total_compressed_image_size += new_size
                else:
                    failed_count += 1
                    if error_msg:
                        error_type = error_msg.split(':')[0]  # Get error category
                        error_summary[error_type] = error_summary.get(error_type, 0) + 1
                        if verbose and "failed" in error_msg.lower():
                            print(f"      Failed to process {xref} on page {page_num}: {error_msg}")
            
            if verbose:
                if processed_count > 0:
                    image_reduction = (1 - total_compressed_image_size / total_original_image_size) * 100
                    print(f"  Successfully processed: {processed_count} images")
                    print(f"  Image compression: {total_original_image_size:,} → {total_compressed_image_size:,} bytes ({image_reduction:.1f}% reduction)")
                
                if failed_count > 0:
                    print(f"  Skipped/failed: {failed_count} images")
                    for error_type, count in error_summary.items():
                        print(f"    {error_type}: {count} image(s)")
        
        # Step 4: Save with optimized settings
        save_options = {
            'garbage': min(optimization_level, 4),
            'deflate': True,
            'deflate_images': True,
            'deflate_fonts': True,
            'clean': True,
            'pretty': False,
            'no_new_id': False,
            'preserve_metadata': False,
        }
        
        if optimization_level >= 3:
            save_options['use_objstms'] = True
        
        # Advanced compression for level 4
        if optimization_level >= 4:
            try:
                save_options['compression_effort'] = 100
            except:
                pass  # Not supported in all versions
        
        # Save the optimized PDF
        try:
            doc.save(output_path, **save_options)
        except TypeError as e:
            if 'compression_effort' in save_options:
                del save_options['compression_effort']
                if verbose:
                    print("  Note: compression_effort not supported, using standard compression")
                doc.save(output_path, **save_options)
            else:
                raise e
        
        doc.close()
        
        # Final size calculation
        optimized_size = os.path.getsize(output_path)
        compression_ratio = (1 - optimized_size / original_size) * 100
        
        if verbose:
            print(f"Final optimized size: {optimized_size:,} bytes")
            print(f"Overall compression: {compression_ratio:.1f}%")
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
    """
    Process multiple PDF files in batch.
    
    Args:
        pdf_files: List of PDF file paths
        output_dir: Output directory (default: same as source)
        optimization_level: Garbage collection level (1-4)
        image_dpi: Target DPI for images
        trim_to_artbox: Whether to trim to art box
        grayscale: Convert color images to grayscale
        suffix: Suffix for output files
    
    Returns:
        list: Results for each file
    """
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
        result = optimize_pdf_improved(
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
        description='Improved PDF optimization with robust image processing',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Optimization levels:
  1: Basic cleanup - Remove metadata, thumbnails, JavaScript (10-20%% reduction)
  2: Font subsetting - Level 1 + subset fonts (20-40%% reduction)
  3: Balanced - Level 2 + conservative image compression (30-70%% reduction)
  4: Maximum - Level 3 + aggressive compression (up to 90%% reduction)

Features:
  - Robust image processing with multiple fallback methods
  - Intelligent DPI calculation and resizing
  - Proper handling of different color spaces (RGB, CMYK, Grayscale)
  - Transparency handling for PNG/GIF images
  - Progressive JPEG encoding for better compression
  - Comprehensive error tracking and reporting

Examples:
  %(prog)s document.pdf                    # Default: level 4, 150 DPI, trim to art box
  %(prog)s document.pdf -l 3               # Balanced optimization
  %(prog)s document.pdf -d 72 -l 4         # Aggressive with 72 DPI images
  %(prog)s *.pdf -o optimized/             # Batch process to directory
  %(prog)s document.pdf --no-trim         # Don't trim to art box
  %(prog)s document.pdf --grayscale        # Convert images to grayscale
        """
    )
    
    parser.add_argument(
        'pdf_files',
        nargs='+',
        help='PDF file(s) to optimize'
    )
    
    parser.add_argument(
        '-l', '--level',
        type=int,
        choices=[1, 2, 3, 4],
        default=4,
        help='Optimization level 1-4 (default: 4)'
    )
    
    parser.add_argument(
        '-d', '--dpi',
        type=int,
        default=150,
        help='Target DPI for images (default: 150)'
    )
    
    parser.add_argument(
        '-o', '--output',
        help='Output directory (default: same as source file)'
    )
    
    parser.add_argument(
        '-s', '--suffix',
        default='-optimized',
        help='Suffix for output files (default: -optimized)'
    )
    
    parser.add_argument(
        '--no-trim',
        action='store_true',
        help='Do not trim to art box (default: trim enabled)'
    )
    
    parser.add_argument(
        '--grayscale',
        action='store_true',
        help='Convert color images to grayscale'
    )
    
    parser.add_argument(
        '-v', '--verbose',
        action='store_true',
        help='Show detailed progress'
    )
    
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
    print(f"PDF Optimizer (Improved) - Processing {len(valid_files)} file(s)")
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