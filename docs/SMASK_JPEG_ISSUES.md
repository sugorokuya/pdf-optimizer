# JPEG+SMask分離処理の問題点まとめ

## 現状の問題

### 1. 主要な症状
- **画像が真っ黒になる**: 最適化後のPDFでカード画像部分が黒く表示される
- **品質スコア低下**: Similarity 0.667（元画像との比較、Adobe版は0.985）
- **黒画素率33.4%**: 元画像は0%だが、最適化後は1/3が黒画素

### 2. 技術的な原因

#### 2.1 PNG膨張問題
- PyMuPDFでPNG画像を埋め込むと**146倍に膨張**
- 例: 700bytes → 120,000bytes（171倍）
- 原因: PDFがPNGを生のRGBAデータに展開して保存
- `deflate=True`でもPNG内部の膨張は解決しない

#### 2.2 SMask参照の破損
```python
# 処理前
SMask: ('xref', '449 0 R')  # 正しい参照

# 処理後（問題）
SMask: ('null', 'null')  # 参照が失われる
```

#### 2.3 replace_image()の挙動
- `page.replace_image(xref, stream=jpeg_data)`実行時にSMask参照が自動的にクリアされる
- 新しい画像データがJPEGの場合、既存のSMask構造が破棄される

## 試みた解決策と結果

### 1. JPEG+SMask完全分離（現在の実装）
```python
def complete_jpeg_smask_separation(doc, page, xref, img, quality=70):
    # 1. RGB部分をJPEGで保存
    page.replace_image(xref, stream=new_jpeg_data)
    
    # 2. SMaskもJPEGで保存
    page.replace_image(smask_xref, stream=new_alpha_data)
    
    # 3. SMask参照を再設定（動作しない）
    doc.xref_set_key(xref, "SMask", smask_ref)
```

**結果**: SMask参照の再設定が機能せず、透明度情報が失われる

### 2. Adobe Acrobatの手法（参考）
- JPEG + SMask構造を維持
- ColorSpace: `('xref', '540 0 R')` - 参照形式を使用
- SMaskのFilter: `JPXDecode`（JPEG2000）または`DCTDecode`（JPEG）
- **成功している**: Similarity 0.985、品質維持

### 3. 色数削減PNG（フォールバック案）
- 8色（品質1）まで削減
- それでもPDF内で膨張（5KB → 49KB、約10倍）
- 根本的な解決にならない

## 技術的制約

### PyMuPDFの制限
1. **xref_set_key()の限界**: 一部の属性（特にSMask）は正しく更新されない
2. **replace_image()の副作用**: 画像置換時に関連属性が自動リセット
3. **PNG処理の仕様**: 必ず生データに展開される設計

### PDF仕様の複雑さ
1. **SMaskオブジェクトの独立性**: 画像とSMaskは別々のxrefオブジェクト
2. **相互参照の管理**: 画像→SMask、SMask→画像の双方向参照が必要
3. **ColorSpace管理**: 適切なColorSpace設定が必要

## 未解決の課題

### 1. SMask参照の正しい復元方法
- `xref_set_key()`では不十分
- PDFオブジェクト辞書の直接操作が必要？
- PyMuPDFの内部APIの制限

### 2. 代替アプローチの検討
- **Option A**: PNG使用を受け入れ、他の部分で圧縮
- **Option B**: 透明度のある画像のみ品質を犠牲にする
- **Option C**: 他のPDFライブラリ（pikepdf等）の使用
- **Option D**: 透明度を白背景で合成（透明度を破棄）

### 3. 検証の自動化
- 現在: `test_quality_validation.py`で黒画像を自動検出
- 必要: SMask参照の整合性チェック機能

## 推奨される次のステップ

1. **短期的対策**: 
   - 透明度のある画像は現状維持（処理しない）
   - 透明度のない画像のみJPEG圧縮

2. **中期的対策**:
   - PyMuPDFの代替手法調査
   - PDFオブジェクト直接操作の研究

3. **長期的対策**:
   - カスタムPDF処理ライブラリの開発
   - またはPyMuPDFへのパッチ提案

## 関連ファイル

- `pdf_optimizer_simple_smask.py`: メイン実装（573行目でJPEG+SMask分離の有効/無効切り替え）
- `test_quality_validation.py`: 品質自動検証
- `test_jpeg_smask_complete.py`: JPEG+SMask分離テスト
- `smasked-image-sample.pdf`: テスト用元PDF（13.7MB）
- `smasked-image-sample-acrobat.pdf`: Adobe最適化版（3.2MB、成功例）
- `smasked-image-sample-smask.pdf`: 我々の最適化版（1.8MB、黒画像問題）

## 数値データ

| 項目 | 元PDF | Adobe版 | 我々の版 |
|------|-------|---------|----------|
| ファイルサイズ | 13.7MB | 3.2MB (76.4%削減) | 1.8MB (86.6%削減) |
| Similarity | 1.000 | 0.985 | 0.667 |
| 黒画素率 | 0% | 0% | 33.4% |
| PSNR | - | - | 9.56dB |
| 主な問題 | - | なし | 画像が黒い |

## 結論

JPEG+SMask分離は理論的には正しいアプローチだが、PyMuPDFの制限により**SMask参照の適切な管理が困難**。Adobe Acrobatは独自の処理方法でこれを回避している。現状では完全な解決策は見つかっていない。