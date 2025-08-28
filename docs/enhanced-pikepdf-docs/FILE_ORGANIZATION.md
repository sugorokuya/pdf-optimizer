# Enhanced pikepdf プロジェクト ファイル構成

## ディレクトリ構成

```
enhanced-pikepdf/
├── CLAUDE.md                           # プロジェクト指示書
├── PIKEPDF_FORK_PROJECT_SPEC.md        # プロジェクト仕様書
├── SMASK_JPEG_ISSUES.md               # JPEG+SMask問題分析
├── TECHNICAL_CONSTRAINTS_ANALYSIS.md   # 技術制約分析
├── pdf_optimizer_simple_smask.py       # メイン最適化ツール
├── test_pikepdf_simple.py              # 基本動作テスト
├── test_quality_validation.py          # 品質検証ツール
├── sample-pdf/                         # テスト用PDFファイル
│   └── smasked-image-sample.pdf
├── pikepdf/                            # フォークしたpikepdfリポジトリ（公式）
│   ├── src/core/                       # C++ソースコード（改良版）
│   │   ├── object.cpp                  # SMask保持機能追加
│   │   └── page.cpp                    # 画像置換機能追加
│   └── [公式pikepdfファイル群]
├── enhanced-pikepdf-docs/              # プロジェクト成果物・ドキュメント
│   ├── PROJECT_COMPLETION_REPORT.md    # プロジェクト完了報告書
│   ├── TECHNICAL_ACHIEVEMENTS_SUMMARY.md # 技術成果サマリー
│   ├── NEXT_STEPS_ROADMAP.md          # 次ステップロードマップ
│   ├── README.md                       # ドキュメント概要
│   ├── optimization-tools/             # 最適化・診断ツール群
│   │   ├── enhanced_pdf_optimizer.py   # 包括的PDF最適化エンジン
│   │   ├── perfect_optimization.py     # 完璧最適化テスト
│   │   ├── ultra_safe_optimization.py  # 超安全最適化テスト
│   │   ├── emergency_diagnosis.py      # 緊急診断ツール
│   │   ├── diagnose_images.py         # 画像診断ツール
│   │   ├── image_extraction_test.py   # 画像抽出テスト
│   │   └── compare_final_safe.py      # ファイル比較ツール
│   ├── tests/                          # テストスクリプト群
│   │   ├── test_pikepdf_simple.py      # 基本機能テスト
│   │   ├── test_enhanced_pikepdf.py    # 拡張機能テスト
│   │   ├── test_pikepdf_safe.py        # 安全機能テスト
│   │   ├── test_enhanced_optimizer_safe.py # 最適化安全テスト
│   │   └── test_final_optimization.py  # 最終最適化テスト
│   └── test-outputs/                   # テスト出力ファイル群
│       ├── smasked-image-sample.pdf
│       ├── enhanced-optimized.pdf
│       ├── safe-optimized.pdf
│       ├── final-optimized.pdf
│       ├── perfect-optimized.pdf
│       ├── ultra-safe-copy.pdf
│       └── [その他テスト出力PDF群]
└── venv/                              # Python仮想環境
```

## ファイル分類

### 1. プロジェクト管理ファイル
- `CLAUDE.md` - Claude向けプロジェクト指示書
- `PIKEPDF_FORK_PROJECT_SPEC.md` - 詳細仕様書
- `SMASK_JPEG_ISSUES.md` - 技術課題分析
- `TECHNICAL_CONSTRAINTS_ANALYSIS.md` - 制約分析

### 2. コア実装ファイル
- `pdf_optimizer_simple_smask.py` - メイン最適化実装
- `test_pikepdf_simple.py` - 基本動作確認
- `test_quality_validation.py` - 品質検証

### 3. pikepdf公式リポジトリ（改良版）
- `pikepdf/src/core/object.cpp` - `_write_with_smask`メソッド追加
- `pikepdf/src/core/page.cpp` - `replace_image_preserve_smask`メソッド追加

### 4. プロジェクト成果物（enhanced-pikepdf-docs/）
#### ドキュメント
- `PROJECT_COMPLETION_REPORT.md` - 包括的完了報告
- `TECHNICAL_ACHIEVEMENTS_SUMMARY.md` - 技術成果要約
- `NEXT_STEPS_ROADMAP.md` - 将来開発計画

#### 実装ツール（optimization-tools/）
- `enhanced_pdf_optimizer.py` - 包括的最適化エンジン（11KB）
- `perfect_optimization.py` - 完璧最適化テスト
- `ultra_safe_optimization.py` - 超安全テスト
- `emergency_diagnosis.py` - 画像消失診断
- `diagnose_images.py` - 画像状態診断
- `image_extraction_test.py` - 画像抽出確認
- `compare_final_safe.py` - ファイル間比較

#### テストスクリプト（tests/）
- `test_pikepdf_simple.py` - 基本機能確認
- `test_enhanced_pikepdf.py` - 拡張機能テスト
- `test_pikepdf_safe.py` - 安全機能テスト
- `test_enhanced_optimizer_safe.py` - 最適化安全テスト
- `test_final_optimization.py` - 最終最適化テスト

#### テスト出力（test-outputs/）
- 各種最適化テストで生成されたPDFファイル群

## 整理の方針

1. **pikepdf/ディレクトリ**: 公式リポジトリのクローンとして保持、プロジェクト固有ファイルは除去
2. **enhanced-pikepdf-docs/**: プロジェクト成果物を体系的に整理
3. **ルートディレクトリ**: プロジェクト管理とコア実装ファイルのみ配置

## アクセス方法

```bash
# ドキュメント閲覧
cd enhanced-pikepdf-docs/
cat PROJECT_COMPLETION_REPORT.md

# ツール実行
cd enhanced-pikepdf-docs/optimization-tools/
python enhanced_pdf_optimizer.py input.pdf output.pdf

# テスト実行
cd enhanced-pikepdf-docs/tests/
python test_pikepdf_simple.py

# テスト出力確認
ls enhanced-pikepdf-docs/test-outputs/
```

この構成により、プロジェクトの成果物が適切に整理され、公式pikepdfリポジトリとプロジェクト固有ファイルが明確に分離されています。