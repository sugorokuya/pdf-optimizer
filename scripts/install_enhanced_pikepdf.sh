#!/bin/bash
# Enhanced pikepdf インストールスクリプト
# 他のユーザーや環境でEnhanced pikepdfを利用するためのセットアップ

set -e

echo "🚀 Enhanced pikepdf インストール開始"

# 1. 必要な依存関係をチェック
echo "📋 依存関係の確認..."

# Python3の確認
if ! command -v python3 &> /dev/null; then
    echo "❌ Python3 が見つかりません"
    exit 1
fi

# gitの確認
if ! command -v git &> /dev/null; then
    echo "❌ git が見つかりません"
    exit 1
fi

# 2. Enhanced pikepdf ディレクトリの確認
ENHANCED_PIKEPDF_DIR="${1:-$HOME/enhanced-pikepdf}"

if [ ! -d "$ENHANCED_PIKEPDF_DIR" ]; then
    echo "📦 Enhanced pikepdf をクローン中..."
    
    # 実際の運用では、GitHub等のリモートリポジトリからクローン
    echo "ℹ️  この例では、ローカルディレクトリをコピーします"
    echo "   実運用では以下のようなコマンドになります："
    echo "   git clone https://github.com/your-org/enhanced-pikepdf.git $ENHANCED_PIKEPDF_DIR"
    
    # 現在の実装をコピー（実際にはgit cloneを使用）
    if [ -d "/Users/maltakoji/Plant/enhanced-pikepdf" ]; then
        cp -r "/Users/maltakoji/Plant/enhanced-pikepdf" "$ENHANCED_PIKEPDF_DIR"
        echo "✅ Enhanced pikepdf をコピーしました: $ENHANCED_PIKEPDF_DIR"
    else
        echo "❌ Enhanced pikepdf ソースが見つかりません"
        exit 1
    fi
fi

# 3. 仮想環境のセットアップ
echo "🔧 仮想環境のセットアップ..."
cd "$ENHANCED_PIKEPDF_DIR"

if [ ! -d "venv" ]; then
    python3 -m venv venv
    echo "✅ 仮想環境を作成しました"
fi

# 仮想環境のアクティベート
source venv/bin/activate

# 4. 依存関係のインストール
echo "📦 依存関係のインストール..."

# 基本的な依存関係
pip install --upgrade pip setuptools wheel

# Enhanced pikepdf の依存関係
pip install -e ".[dev,test]"
pip install pillow numpy scikit-image

# システム依存関係の確認（macOS）
if [[ "$OSTYPE" == "darwin"* ]]; then
    if ! command -v qpdf &> /dev/null; then
        echo "📦 qpdf をインストール中 (macOS)..."
        if command -v brew &> /dev/null; then
            brew install qpdf
        else
            echo "❌ Homebrew が見つかりません。qpdf を手動でインストールしてください"
            exit 1
        fi
    fi
fi

# 5. Enhanced pikepdf のビルド
echo "🔨 Enhanced pikepdf のビルド..."
python setup.py build_ext --inplace

# 6. 動作確認
echo "✅ インストールの確認..."
python -c "
import pikepdf
print(f'Enhanced pikepdf version: {pikepdf.__version__}')
print(f'Location: {pikepdf.__file__}')

# C++拡張の確認
import pikepdf
pdf = pikepdf.Pdf.new()
page = pdf.add_blank_page()
print('✅ Enhanced pikepdf が正常に動作しています')
"

# 7. 使用方法の表示
echo ""
echo "🎉 Enhanced pikepdf のインストールが完了しました！"
echo ""
echo "📋 使用方法:"
echo "1. 仮想環境のアクティベート:"
echo "   cd $ENHANCED_PIKEPDF_DIR && source venv/bin/activate"
echo ""
echo "2. Enhanced PDF最適化の実行:"
echo "   python enhanced-pikepdf-docs/optimization-tools/enhanced_pdf_optimizer.py input.pdf"
echo ""
echo "3. 統合版オプティマイザーの使用:"
echo "   python enhanced-pikepdf-docs/optimization-tools/enhanced_pdf_optimizer_integrated.py input.pdf -v"
echo ""
echo "📖 詳細なドキュメント:"
echo "   $ENHANCED_PIKEPDF_DIR/enhanced-pikepdf-docs/PROJECT_COMPLETION_REPORT.md"
echo ""

deactivate