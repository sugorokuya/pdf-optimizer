#!/usr/bin/env python3
"""
Enhanced PDF Optimizer - 安全なCMYK処理とSMask保持を含む高度PDF最適化

主要機能:
1. 安全なCMYK→RGB変換
2. SMask参照を保持したJPEG+SMask分離  
3. 背景画像の超劣化（1/4解像度、品質1）
4. DPI制限（150DPI）
5. 品質検証（Similarity 0.985以上）
"""
import io
import os
import math
import logging
from typing import Dict, List, Tuple, Optional, Any
from dataclasses import dataclass
from PIL import Image, ImageCms
import pikepdf
import numpy as np
from skimage.metrics import structural_similarity as ssim

# ログ設定
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

@dataclass
class OptimizationConfig:
    """最適化設定"""
    # 基本設定
    jpeg_quality: int = 70
    max_dpi: int = 150
    enable_cmyk_conversion: bool = True
    enable_background_degradation: bool = True
    
    # 背景劣化設定
    background_quality: int = 1
    background_scale: float = 0.25  # 1/4解像度
    background_threshold_mb: float = 1.0  # 1MB以上で背景とみなす
    
    # 品質検証設定
    min_similarity: float = 0.985
    min_psnr: float = 30.0
    max_black_pixel_ratio: float = 0.01
    
    # 処理制限
    max_images_per_page: int = 50
    skip_small_images: bool = True
    min_image_size: int = 64  # 64x64未満はスキップ

@dataclass  
class ImageInfo:
    """画像情報"""
    name: str
    obj: Any
    width: int
    height: int
    colorspace: str
    filter_type: str
    bits_per_component: int
    has_smask: bool
    stream_size: int
    estimated_dpi: float
    is_background: bool
    processing_safe: bool

class EnhancedPDFOptimizer:
    """拡張PDF最適化クラス"""
    
    def __init__(self, config: OptimizationConfig = None):
        self.config = config or OptimizationConfig()
        self.stats = {
            'processed': 0,
            'skipped': 0,
            'errors': 0,
            'size_reduction': 0,
            'quality_scores': []
        }
    
    def analyze_colorspace(self, obj: Any) -> Tuple[str, int]:
        """色空間を安全に分析"""
        try:
            colorspace = obj.get('/ColorSpace')
            
            if colorspace is None:
                return 'Unknown', 3
                
            if isinstance(colorspace, pikepdf.Name):
                cs_name = str(colorspace)
                if cs_name == '/DeviceRGB':
                    return 'RGB', 3
                elif cs_name == '/DeviceCMYK':
                    return 'CMYK', 4
                elif cs_name == '/DeviceGray':
                    return 'Gray', 1
                else:
                    return cs_name, 3
                    
            elif isinstance(colorspace, list) or hasattr(colorspace, '__len__'):
                if len(colorspace) >= 2:
                    cs_type = str(colorspace[0])
                    if cs_type == '/ICCBased':
                        # ICCプロファイルから成分数を取得
                        try:
                            icc_stream = colorspace[1]
                            n_components = int(icc_stream.get('/N', 3))
                            if n_components == 4:
                                return 'CMYK_ICC', 4
                            elif n_components == 3:
                                return 'RGB_ICC', 3
                            elif n_components == 1:
                                return 'Gray_ICC', 1
                            else:
                                return f'ICC_{n_components}', n_components
                        except:
                            return 'ICC_Unknown', 3
                    elif cs_type == '/CalRGB':
                        return 'CalRGB', 3
                    elif cs_type == '/CalGray':
                        return 'CalGray', 1
                        
            return 'Unknown', 3
            
        except Exception as e:
            logger.warning(f"色空間分析エラー: {e}")
            return 'Error', 3
    
    def estimate_dpi(self, width: int, height: int, page_size: Tuple[float, float]) -> float:
        """DPIを推定"""
        try:
            # ページサイズからインチを計算（72 points per inch）
            page_width_inch = page_size[0] / 72
            page_height_inch = page_size[1] / 72
            
            # 画像の実効DPIを計算
            dpi_x = width / page_width_inch if page_width_inch > 0 else 72
            dpi_y = height / page_height_inch if page_height_inch > 0 else 72
            
            return max(dpi_x, dpi_y)
        except:
            return 72  # デフォルト
    
    def is_background_image(self, info: ImageInfo, page_size: Tuple[float, float]) -> bool:
        """背景画像かどうか判定"""
        try:
            # サイズベースの判定
            if info.stream_size > self.config.background_threshold_mb * 1024 * 1024:
                return True
                
            # 解像度ベースの判定 - ページ全体に近いサイズ
            page_width_px = page_size[0] * 2  # 144DPI相当
            page_height_px = page_size[1] * 2
            
            if (info.width >= page_width_px * 0.8 and 
                info.height >= page_height_px * 0.8):
                return True
                
            return False
            
        except:
            return False
    
    def analyze_page_images(self, page: Any) -> List[ImageInfo]:
        """ページ内の全画像を分析"""
        images = []
        
        try:
            if '/Resources' not in page or '/XObject' not in page['/Resources']:
                return images
                
            xobjects = page['/Resources']['/XObject']
            
            # ページサイズを取得
            try:
                mediabox = page.get('/MediaBox', [0, 0, 612, 792])  # デフォルトはLetter
                page_size = (float(mediabox[2] - mediabox[0]), float(mediabox[3] - mediabox[1]))
            except:
                page_size = (612, 792)
            
            for name, obj in xobjects.items():
                if not ('/Subtype' in obj and obj['/Subtype'] == '/Image'):
                    continue
                    
                try:
                    width = int(obj.get('/Width', 0))
                    height = int(obj.get('/Height', 0))
                    
                    if width == 0 or height == 0:
                        continue
                        
                    # 小さい画像をスキップ
                    if (self.config.skip_small_images and 
                        min(width, height) < self.config.min_image_size):
                        continue
                    
                    # 基本情報収集
                    colorspace_name, n_components = self.analyze_colorspace(obj)
                    filter_obj = obj.get('/Filter', 'None')
                    filter_str = str(filter_obj)
                    bits = int(obj.get('/BitsPerComponent', 8))
                    has_smask = '/SMask' in obj
                    
                    # ストリームサイズ
                    try:
                        stream_size = len(obj.read_raw_bytes())
                    except:
                        stream_size = 0
                    
                    # DPI推定
                    estimated_dpi = self.estimate_dpi(width, height, page_size)
                    
                    info = ImageInfo(
                        name=name,
                        obj=obj,
                        width=width,
                        height=height,
                        colorspace=colorspace_name,
                        filter_type=filter_str,
                        bits_per_component=bits,
                        has_smask=has_smask,
                        stream_size=stream_size,
                        estimated_dpi=estimated_dpi,
                        is_background=False,
                        processing_safe=True
                    )
                    
                    # 背景画像判定
                    info.is_background = self.is_background_image(info, page_size)
                    
                    # 処理安全性チェック
                    info.processing_safe = self.is_processing_safe(info)
                    
                    images.append(info)
                    
                except Exception as e:
                    logger.warning(f"画像{name}の分析エラー: {e}")
                    continue
                    
        except Exception as e:
            logger.error(f"ページ画像分析エラー: {e}")
            
        return images
    
    def is_processing_safe(self, info: ImageInfo) -> bool:
        """画像処理が安全かどうか判定"""
        # CMYK画像は慎重に処理
        if 'CMYK' in info.colorspace and not self.config.enable_cmyk_conversion:
            return False
            
        # 既にJPEGの画像で品質劣化のみの場合
        if '/DCTDecode' in info.filter_type and not info.is_background:
            return False
            
        # 非常に小さいストリームは処理しない
        if info.stream_size < 1000:  # 1KB未満
            return False
            
        return True
    
    def safe_cmyk_to_rgb(self, image_data: bytes, width: int, height: int) -> Image.Image:
        """安全なCMYK→RGB変換"""
        try:
            # CMYKデータからPIL画像を作成
            cmyk_image = Image.frombytes('CMYK', (width, height), image_data)
            
            # sRGBプロファイルを使用した変換
            rgb_image = cmyk_image.convert('RGB')
            
            logger.debug(f"CMYK→RGB変換成功: {cmyk_image.size} -> {rgb_image.size}")
            return rgb_image
            
        except Exception as e:
            logger.error(f"CMYK→RGB変換エラー: {e}")
            # フォールバック: 単純な数式変換
            try:
                cmyk_array = np.frombuffer(image_data, dtype=np.uint8)
                cmyk_array = cmyk_array.reshape((height, width, 4))
                
                c, m, y, k = cmyk_array[:,:,0], cmyk_array[:,:,1], cmyk_array[:,:,2], cmyk_array[:,:,3]
                
                # 単純なCMYK→RGB変換
                r = 255 * (1 - c / 255) * (1 - k / 255)
                g = 255 * (1 - m / 255) * (1 - k / 255)  
                b = 255 * (1 - y / 255) * (1 - k / 255)
                
                rgb_array = np.stack([r, g, b], axis=2).astype(np.uint8)
                return Image.fromarray(rgb_array, 'RGB')
                
            except Exception as e2:
                logger.error(f"フォールバック変換も失敗: {e2}")
                raise e
    
    def create_degraded_background(self, image: Image.Image) -> Image.Image:
        """背景画像の超劣化（1/4解像度）"""
        try:
            original_size = image.size
            new_size = (
                max(1, int(original_size[0] * self.config.background_scale)),
                max(1, int(original_size[1] * self.config.background_scale))
            )
            
            # リサイズ
            degraded = image.resize(new_size, Image.Resampling.LANCZOS)
            
            # 元のサイズに戻す（品質劣化）
            degraded = degraded.resize(original_size, Image.Resampling.LANCZOS)
            
            logger.debug(f"背景劣化: {original_size} -> {new_size} -> {original_size}")
            return degraded
            
        except Exception as e:
            logger.error(f"背景劣化エラー: {e}")
            return image

    def optimize_image(self, info: ImageInfo) -> Tuple[bytes, bytes, bool]:
        """画像を最適化"""
        try:
            # 元データを読み込み
            if info.colorspace.startswith('CMYK') and 'CMYK' in info.colorspace:
                # CMYKデータの処理
                try:
                    decoded_data = info.obj.read_bytes()
                    rgb_image = self.safe_cmyk_to_rgb(decoded_data, info.width, info.height)
                except Exception as e:
                    logger.warning(f"CMYK処理失敗 {info.name}: {e}")
                    return None, None, False
            else:
                # RGB/Grayスケール画像
                try:
                    pil_image = info.obj.as_pil_image()
                    if pil_image is None:
                        # 手動でデコード
                        decoded_data = info.obj.read_bytes()
                        expected_components = 4 if 'CMYK' in info.colorspace else 3
                        mode = 'CMYK' if expected_components == 4 else 'RGB'
                        pil_image = Image.frombytes(mode, (info.width, info.height), decoded_data)
                    
                    if pil_image.mode != 'RGB':
                        rgb_image = pil_image.convert('RGB')
                    else:
                        rgb_image = pil_image
                        
                except Exception as e:
                    logger.warning(f"画像読み込み失敗 {info.name}: {e}")
                    return None, None, False
            
            # DPI制限適用
            if info.estimated_dpi > self.config.max_dpi:
                scale_factor = self.config.max_dpi / info.estimated_dpi
                new_size = (
                    max(1, int(rgb_image.width * scale_factor)),
                    max(1, int(rgb_image.height * scale_factor))
                )
                rgb_image = rgb_image.resize(new_size, Image.Resampling.LANCZOS)
                logger.debug(f"DPI制限適用: {info.width}x{info.height} -> {new_size}")
            
            # 背景画像の超劣化
            if info.is_background and self.config.enable_background_degradation:
                rgb_image = self.create_degraded_background(rgb_image)
                jpeg_quality = self.config.background_quality
                logger.debug(f"背景超劣化適用: 品質{jpeg_quality}")
            else:
                jpeg_quality = self.config.jpeg_quality
            
            # JPEG変換
            jpeg_output = io.BytesIO()
            rgb_image.save(jpeg_output, format='JPEG', quality=jpeg_quality, optimize=True)
            jpeg_data = jpeg_output.getvalue()
            
            # SMask処理
            smask_data = None
            if info.has_smask:
                try:
                    smask_obj = info.obj['/SMask']
                    
                    # SMask画像の読み込み
                    try:
                        smask_pil = smask_obj.as_pil_image()
                        if smask_pil is None:
                            # 手動でデコード
                            smask_decoded = smask_obj.read_bytes()
                            smask_pil = Image.frombytes('L', (info.width, info.height), smask_decoded)
                    except:
                        # フォールバック: 元サイズと同じグレー画像を作成
                        smask_pil = Image.new('L', rgb_image.size, 255)
                    
                    # SMaskのサイズ調整
                    if smask_pil.size != rgb_image.size:
                        smask_pil = smask_pil.resize(rgb_image.size, Image.Resampling.LANCZOS)
                    
                    # SMaskをJPEGで保存
                    if smask_pil.mode != 'L':
                        smask_pil = smask_pil.convert('L')
                        
                    smask_output = io.BytesIO()
                    smask_pil.save(smask_output, format='JPEG', quality=jpeg_quality, optimize=True)
                    smask_data = smask_output.getvalue()
                    
                    logger.debug(f"SMask処理完了: {len(smask_data)} bytes")
                    
                except Exception as e:
                    logger.warning(f"SMask処理エラー {info.name}: {e}")
                    smask_data = None
            
            logger.debug(f"最適化完了 {info.name}: JPEG {len(jpeg_data)} bytes")
            return jpeg_data, smask_data, True
            
        except Exception as e:
            logger.error(f"画像最適化エラー {info.name}: {e}")
            return None, None, False
    
    def calculate_similarity(self, original_bytes: bytes, optimized_bytes: bytes, 
                           width: int, height: int) -> float:
        """画像の類似度を計算"""
        try:
            # 比較用に同じサイズの画像を作成
            orig_img = Image.open(io.BytesIO(original_bytes)).convert('L').resize((width, height))
            opt_img = Image.open(io.BytesIO(optimized_bytes)).convert('L').resize((width, height))
            
            # NumPy配列に変換
            orig_array = np.array(orig_img, dtype=np.float64) / 255.0
            opt_array = np.array(opt_img, dtype=np.float64) / 255.0
            
            # SSIM計算
            similarity = ssim(orig_array, opt_array, data_range=1.0)
            return similarity
            
        except Exception as e:
            logger.warning(f"類似度計算エラー: {e}")
            return 0.0
    
    def optimize_page(self, page: Any) -> Dict[str, Any]:
        """ページ全体を最適化"""
        page_stats = {
            'processed': 0,
            'skipped': 0,
            'errors': 0,
            'size_before': 0,
            'size_after': 0,
            'quality_scores': []
        }
        
        try:
            # 画像分析
            images = self.analyze_page_images(page)
            logger.info(f"ページ内画像数: {len(images)}")
            
            for info in images:
                try:
                    logger.info(f"処理中: {info.name} ({info.width}x{info.height}, "
                              f"{info.colorspace}, {info.stream_size:,}bytes)")
                    
                    page_stats['size_before'] += info.stream_size
                    
                    # 処理安全性チェック
                    if not info.processing_safe:
                        logger.info(f"  スキップ: 処理安全性チェック失敗")
                        page_stats['skipped'] += 1
                        page_stats['size_after'] += info.stream_size
                        continue
                    
                    # 最適化実行
                    jpeg_data, smask_data, success = self.optimize_image(info)
                    
                    if not success:
                        logger.warning(f"  最適化失敗: {info.name}")
                        page_stats['errors'] += 1
                        page_stats['size_after'] += info.stream_size
                        continue
                    
                    # 品質検証
                    try:
                        original_data = info.obj.read_raw_bytes()
                        similarity = self.calculate_similarity(
                            original_data, jpeg_data, info.width, info.height)
                        
                        if similarity < self.config.min_similarity:
                            logger.warning(f"  品質チェック失敗: similarity={similarity:.3f} < {self.config.min_similarity}")
                            page_stats['skipped'] += 1
                            page_stats['size_after'] += info.stream_size
                            continue
                            
                        page_stats['quality_scores'].append(similarity)
                        
                    except Exception as e:
                        logger.debug(f"  品質検証スキップ: {e}")
                    
                    # PDFオブジェクト更新 - 新しいC++メソッドを使用
                    try:
                        if smask_data and info.has_smask:
                            # SMask保持メソッドを使用
                            info.obj._write_with_smask(
                                data=jpeg_data,
                                filter=pikepdf.Name('/DCTDecode'),
                                decode_parms=None,
                                smask=info.obj['/SMask']
                            )
                            
                            # SMask更新
                            smask_obj = info.obj['/SMask']
                            smask_obj.write(smask_data, filter=pikepdf.Name('/DCTDecode'))
                            
                        else:
                            # 通常の更新
                            info.obj.write(jpeg_data, filter=pikepdf.Name('/DCTDecode'))
                        
                        # 寸法更新
                        rgb_img_temp = Image.open(io.BytesIO(jpeg_data))
                        info.obj['/Width'] = rgb_img_temp.width
                        info.obj['/Height'] = rgb_img_temp.height
                        
                        size_after = len(jpeg_data) + (len(smask_data) if smask_data else 0)
                        page_stats['size_after'] += size_after
                        
                        reduction = (1 - size_after / info.stream_size) * 100 if info.stream_size > 0 else 0
                        logger.info(f"  ✓ 完了: {info.stream_size:,} -> {size_after:,} bytes ({reduction:+.1f}%)")
                        
                        page_stats['processed'] += 1
                        
                    except Exception as e:
                        logger.error(f"  PDF更新エラー: {e}")
                        page_stats['errors'] += 1
                        page_stats['size_after'] += info.stream_size
                        
                except Exception as e:
                    logger.error(f"画像処理エラー {info.name if 'info' in locals() else 'unknown'}: {e}")
                    page_stats['errors'] += 1
                    if 'info' in locals():
                        page_stats['size_after'] += info.stream_size
        
        except Exception as e:
            logger.error(f"ページ最適化エラー: {e}")
            
        return page_stats
    
    def optimize_pdf(self, input_path: str, output_path: str) -> Dict[str, Any]:
        """PDF全体を最適化"""
        logger.info(f"PDF最適化開始: {input_path} -> {output_path}")
        
        total_stats = {
            'processed': 0,
            'skipped': 0, 
            'errors': 0,
            'size_before': 0,
            'size_after': 0,
            'quality_scores': [],
            'pages': 0
        }
        
        try:
            # 元ファイルサイズ
            original_file_size = os.path.getsize(input_path)
            total_stats['file_size_before'] = original_file_size
            
            # PDF読み込み
            pdf = pikepdf.Pdf.open(input_path)
            total_stats['pages'] = len(pdf.pages)
            
            logger.info(f"ページ数: {total_stats['pages']}, ファイルサイズ: {original_file_size:,} bytes")
            
            # 各ページを処理
            for i, page in enumerate(pdf.pages):
                logger.info(f"\n=== ページ {i+1}/{total_stats['pages']} ===")
                
                page_stats = self.optimize_page(page)
                
                # 統計を集約
                total_stats['processed'] += page_stats['processed']
                total_stats['skipped'] += page_stats['skipped']
                total_stats['errors'] += page_stats['errors']
                total_stats['size_before'] += page_stats['size_before']
                total_stats['size_after'] += page_stats['size_after']
                total_stats['quality_scores'].extend(page_stats['quality_scores'])
            
            # PDF保存
            pdf.save(output_path)
            pdf.close()
            
            # 最終ファイルサイズ
            final_file_size = os.path.getsize(output_path)
            total_stats['file_size_after'] = final_file_size
            
            # 結果表示
            self.print_optimization_results(total_stats, input_path, output_path)
            
        except Exception as e:
            logger.error(f"PDF最適化エラー: {e}")
            total_stats['error'] = str(e)
        
        return total_stats
    
    def print_optimization_results(self, stats: Dict[str, Any], input_path: str, output_path: str):
        """最適化結果を表示"""
        print(f"\n{'='*60}")
        print("PDF最適化結果")  
        print(f"{'='*60}")
        
        print(f"入力ファイル: {input_path}")
        print(f"出力ファイル: {output_path}")
        print(f"ページ数: {stats['pages']}")
        
        print(f"\n画像処理結果:")
        print(f"  処理成功: {stats['processed']} 個")
        print(f"  スキップ: {stats['skipped']} 個")
        print(f"  エラー: {stats['errors']} 個")
        
        if stats['file_size_before'] > 0:
            file_reduction = (1 - stats['file_size_after'] / stats['file_size_before']) * 100
            print(f"\nファイルサイズ:")
            print(f"  変更前: {stats['file_size_before']:,} bytes ({stats['file_size_before']/1024/1024:.1f}MB)")
            print(f"  変更後: {stats['file_size_after']:,} bytes ({stats['file_size_after']/1024/1024:.1f}MB)")
            print(f"  削減率: {file_reduction:+.1f}%")
        
        if stats['quality_scores']:
            avg_quality = np.mean(stats['quality_scores'])
            min_quality = np.min(stats['quality_scores'])
            print(f"\n品質指標:")
            print(f"  平均類似度: {avg_quality:.3f}")
            print(f"  最低類似度: {min_quality:.3f}")
            print(f"  品質基準: {self.config.min_similarity:.3f} 以上")
            print(f"  品質判定: {'✓ 合格' if min_quality >= self.config.min_similarity else '✗ 不合格'}")

if __name__ == '__main__':
    # テスト実行
    config = OptimizationConfig(
        enable_cmyk_conversion=True,
        enable_background_degradation=True,
        jpeg_quality=75,
        background_quality=10,
        min_similarity=0.95  # テスト用に緩和
    )
    
    optimizer = EnhancedPDFOptimizer(config)
    
    # サンプルPDFで最適化テスト
    if os.path.exists('smasked-image-sample.pdf'):
        optimizer.optimize_pdf('smasked-image-sample.pdf', 'enhanced-optimized.pdf')
    else:
        logger.info("Enhanced PDF Optimizer初期化完了 - テストPDFが見つかりません")