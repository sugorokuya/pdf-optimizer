# pikepdf フォークプロジェクト仕様書

## プロジェクト概要

**目的**: pikepdfをフォークして、PDF画像最適化に特化した機能を追加し、PyMuPDFの制約を克服する

**背景**: 現在のPyMuPDF + pikepdf ハイブリッドアプローチでは、以下の技術的制約により完全な最適化が実現できない：
- PyMuPDFのSMask参照破損問題（`replace_image()`時に`SMask`が`('null', 'null')`になる）
- pikepdfのXObject更新問題（`obj.write()`が実際のPDFストリームに反映されない）
- PNG画像の146倍膨張問題（PyMuPDFでPNGを埋め込むと生データに展開）

## 現在の技術的問題の詳細

### 1. PyMuPDF制約
```python
# 問題のあるコード
page.replace_image(xref, stream=jpeg_data)
# 結果: SMask参照が ('xref', '449 0 R') → ('null', 'null') に変化
# 原因: PyMuPDFの仕様で画像置換時にSMask属性が自動リセット
```

### 2. pikepdf XObject更新制約
```python
# 期待通りに動作しないコード
obj.write(jpeg_data, filter=pikepdf.Name.DCTDecode)
obj.Width = base_img.width
obj.Height = base_img.height
# 結果: ログでは99.7%削減と表示されるが、実際のPDFストリームは変更されない
```

### 3. 正しいpikepdf方法（現在実装済み）
```python
# 新しいXObjectを作成（動作するが最適化されていない）
new_img_obj = pdf.make_stream(jpeg_data)
new_img_obj.Width = base_img.width  
new_img_obj.Height = base_img.height
new_img_obj.Filter = pikepdf.Name.DCTDecode
xobjects[name] = new_img_obj  # Resources辞書で参照更新
```

## 達成したい機能要件

### 1. 背景画像超劣化
- **背景画像自動検出**: ページの60%以上をカバーする画像
- **解像度大幅ダウン**: 元解像度の1/4に縮小
- **JPEG品質1適用**: 最低品質での圧縮
- **期待効果**: 99.5%以上のサイズ削減

### 2. DPI制限機能  
- **目標DPI**: 150 DPI制限
- **自動リサイズ**: 閾値（150 DPI × 1.5 = 225 DPI）超過時に自動縮小
- **期待効果**: 高解像度画像の大幅サイズ削減

### 3. JPEG+SMask分離
- **PNG膨張回避**: PNGの146倍膨張問題を根本解決
- **透明度保持**: SMask参照を正しく維持
- **高品質圧縮**: Adobe Acrobat並み（Similarity 0.985）の品質実現

## フォーク実装計画

### Phase 1: pikepdfフォーク基盤構築
1. **リポジトリセットアップ**
   - pikepdf公式リポジトリからフォーク
   - 開発環境構築（C++コンパイル環境）
   - 既存テストスイートの動作確認

2. **コードベース理解**
   - qpdf（C++基盤）とPythonバインディングの関係把握
   - XObject操作部分のソースコード特定
   - Stream更新メカニズムの調査

### Phase 2: 画像最適化機能実装
1. **XObject直接更新機能**
```cpp
// 想定するC++レベルの実装
void updateXObjectStream(QPDFObjectHandle obj, std::string const& data, 
                        std::string const& filter) {
    // 既存ストリームを直接更新
    obj.replaceStreamData(data, QPDFObjectHandle::parse(filter), 
                         QPDFObjectHandle::newNull());
    // Resources辞書の参照も自動更新
}
```

2. **画像解析・変換機能**
```python
# Pythonラッパー側での実装
class EnhancedPdfImage(pikepdf.PdfImage):
    def optimize_for_background(self, quality=1, max_resolution=150):
        """背景画像向け超劣化処理"""
        pass
        
    def apply_dpi_limit(self, target_dpi=150):
        """DPI制限適用"""
        pass
        
    def convert_to_jpeg_with_smask(self, quality=70):
        """JPEG+SMask分離（SMask参照保持）"""
        pass
```

### Phase 3: 統合最適化機能
1. **自動最適化パイプライン**
```python
def optimize_pdf_enhanced(input_path, output_path, options=None):
    """統合最適化機能"""
    pdf = EnhancedPikePdf.open(input_path)
    
    for page in pdf.pages:
        for image in page.get_images():
            if image.is_background():
                image.optimize_for_background()
            elif image.has_transparency():
                image.convert_to_jpeg_with_smask()
            else:
                image.apply_dpi_limit()
    
    pdf.save(output_path, optimize_all=True)
```

## 技術仕様詳細

### 1. 背景画像検出アルゴリズム
```python
def is_background_image(self, page_rect):
    """
    背景画像判定基準：
    1. ページカバー率 >= 60%
    2. 透明度なし or 透明度が背景的
    3. Z-order（描画順序）が背景レイヤー
    """
    coverage = self.get_coverage_ratio(page_rect)
    return coverage >= 0.6 and not self.has_foreground_transparency()
```

### 2. DPI計算・制限
```python  
def calculate_effective_dpi(self, display_size):
    """
    実効DPI計算：
    effective_dpi = (image_width / display_width) * 72
    """
    return (self.width / display_size.width) * 72

def resize_for_dpi_limit(self, target_dpi=150):
    """
    DPI制限リサイズ：
    scale_factor = target_dpi / effective_dpi
    new_size = (width * scale_factor, height * scale_factor)
    """
    pass
```

### 3. SMask参照保持
```cpp
// C++レベルでのSMask参照管理
class SMaskManager {
    void preserveSMaskReference(QPDFObjectHandle image_obj, 
                               QPDFObjectHandle smask_obj) {
        // SMask参照を確実に維持する実装
        image_obj.replaceKey("/SMask", smask_obj.getObjGen());
    }
};
```

## 品質検証要件

### 1. 定量的目標
- **ファイルサイズ削減**: 80%以上削減（Adobe Acrobat並み）
- **画質保持**: 非背景画像でSimilarity 0.95以上
- **透明度保持**: SMask付き画像の黒画素率 0%維持
- **処理速度**: 大型PDF（50MB+）を5分以内で処理

### 2. テストケース
```python
# 必須テストケース
test_cases = [
    "smasked-image-sample.pdf",      # SMask付き画像（51個）
    "rule-2pages.pdf",               # 複数ページ、背景画像混在
    "background-heavy.pdf",          # 背景画像中心のPDF
    "transparency-complex.pdf",      # 複雑な透明度処理
]

# 品質検証基準
quality_thresholds = {
    'background_similarity': 0.3,    # 背景画像は劣化OK
    'foreground_similarity': 0.95,   # 前景画像は高品質維持
    'transparency_preservation': 1.0, # 透明度は完全保持
    'file_size_reduction': 0.8       # 80%以上削減
}
```

## 開発環境・依存関係

### 1. 必要なツール
```bash
# C++開発環境
apt-get install build-essential cmake
apt-get install libqpdf-dev

# Python開発環境  
pip install pybind11 setuptools wheel
pip install Pillow pytest

# qpdfビルド（最新版）
git clone https://github.com/qpdf/qpdf.git
cd qpdf && cmake -B build && cmake --build build
```

### 2. プロジェクト構造
```
enhanced-pikepdf/
├── src/
│   ├── qpdf/              # qpdf C++拡張
│   ├── pikepdf/           # Pythonバインディング
│   └── image_optimizer/   # 画像最適化モジュール
├── tests/
│   ├── test_pdfs/         # テスト用PDFファイル
│   └── quality_validation/ # 品質検証スクリプト
├── docs/
│   └── api_reference.md   # API仕様書
└── examples/
    └── optimization_demo.py # デモスクリプト
```

## 現在の成果・参考実装

### 1. 現行実装ファイル（参考用）
- `pdf_optimizer_simple_smask.py`: メイン最適化スクリプト（PyMuPDF + pikepdfハイブリッド）
- `test_quality_validation.py`: 品質検証ツール
- `test_pikepdf_simple.py`: pikepdf単体テスト（成功例）
- `SMASK_JPEG_ISSUES.md`: 技術的問題の詳細分析

### 2. 実証済み技術要素
- **JPEG+SMask分離ロジック**: PIL/Pillowベースの画像分離
- **背景画像検出**: カバー率ベースの判定アルゴリズム  
- **DPI最適化**: 解像度計算とリサイズ処理
- **品質検証**: Similarity, PSNR, 黒画素率による自動評価

### 3. 既知の成功パターン
```python
# テスト済みの成功例（pikepdf単体）
def successful_optimization():
    """
    test_pikepdf_simple.py での成功例：
    - 3個の小画像で動作確認済み
    - Similarity: 0.9826（Adobe並み）
    - 黒画素率: 0%（透明度保持）
    - 個別画像で80-90%削減達成
    """
    pass
```

## 成功指標・完了条件

### 1. 技術的成功指標
- [ ] XObject更新がPDFストリームに正しく反映される
- [ ] SMask参照が画像置換後も保持される  
- [ ] 背景画像で99%以上のサイズ削減を達成
- [ ] 全体で80%以上のファイルサイズ削減を達成

### 2. 品質検証クリア
- [ ] Adobe Acrobat比較でSimilarity 0.95以上
- [ ] 透明度付き画像の黒画素率 0%維持
- [ ] 大型PDF（50MB+）での安定動作確認

### 3. 使いやすさ
- [ ] 既存PyMuPDFコードからの移行が簡単
- [ ] コマンドライン・Python API両方での利用可能
- [ ] 詳細な最適化レポート機能

## 次セッションでの作業開始手順

1. **環境確認**: C++開発環境、Python環境の構築状況確認
2. **リポジトリフォーク**: pikepdf公式からフォーク作成
3. **ベースライン確認**: 既存pikepdfでの現在の制約を再現
4. **Phase 1実装開始**: XObject直接更新機能の実装
5. **テスト実行**: sample-background.pdf での動作検証

このプロジェクトにより、現在の技術的制約を根本から解決し、Adobe Acrobat以上の最適化性能を実現できる見込みです。