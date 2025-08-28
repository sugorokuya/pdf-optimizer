# PDF Optimizer

高度なPDF最適化ツール - Enhanced pikepdfによる革新的圧縮技術

## 🚀 特徴

- **76-85% サイズ削減** - 品質を維持しながら大幅圧縮
- **SMask完全保持** - 透明度情報の確実な維持
- **背景画像超劣化** - 1/4解像度化による効果的削減
- **CMYK安全変換** - ICCプロファイル対応
- **C++拡張** - pikepdf改造による根本的問題解決

## 📊 実証結果

| ファイル | 元サイズ | 最適化後 | 削減率 |
|---------|---------|----------|--------|
| sample.pdf | 5.2 MB | 1.2 MB | 76.9% |

## 🔧 インストール

```bash
# サブモジュール含めてクローン
git clone --recurse-submodules https://github.com/maltakoji/pdf-optimizer.git
cd pdf-optimizer

# 依存関係インストール
pip install -r requirements.txt

# Enhanced pikepdfビルド
cd pikepdf
python setup.py build_ext --inplace
cd ..
```

## 📝 使用方法

```bash
# 基本的な最適化
python src/enhanced_pdf_optimizer_integrated.py input.pdf

# オプション指定
python src/enhanced_pdf_optimizer_integrated.py input.pdf -o output.pdf -q 70 --dpi 150
```

## 🐳 Docker

```bash
docker-compose up
docker run -v /path/to/pdfs:/data pdf-optimizer input.pdf
```

## 📁 プロジェクト構造

```
pdf-optimizer/
├── pikepdf/         # サブモジュール（改造版pikepdf）
├── src/             # 最適化ツール本体
├── tests/           # テストスイート
├── test-pdfs/       # テスト用PDF
├── patches/         # pikepdf改造パッチ
├── docker/          # Docker環境
└── docs/            # ドキュメント
```

## 📄 ライセンス

[TBD]

## 🤝 貢献

プルリクエスト歓迎です。大きな変更の場合は、まずissueを開いて議論してください。
