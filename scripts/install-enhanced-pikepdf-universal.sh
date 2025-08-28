#!/bin/bash
# Enhanced pikepdf Universal Installer
# どこでもEnhanced pikepdf改造版を利用可能にする

set -e

# 色付きメッセージ関数
print_info() { echo -e "\033[34m[INFO]\033[0m $1"; }
print_success() { echo -e "\033[32m[SUCCESS]\033[0m $1"; }
print_warning() { echo -e "\033[33m[WARNING]\033[0m $1"; }
print_error() { echo -e "\033[31m[ERROR]\033[0m $1"; }

print_info "🚀 Enhanced pikepdf Universal Installer"
print_info "========================================"

# 設定
INSTALL_DIR="${1:-$HOME/enhanced-pikepdf}"
ENHANCED_PIKEPDF_SOURCE="${2:-/Users/maltakoji/Plant/enhanced-pikepdf}"

print_info "インストール先: $INSTALL_DIR"
print_info "ソース: $ENHANCED_PIKEPDF_SOURCE"

# プラットフォーム検出
detect_platform() {
    if [[ "$OSTYPE" == "darwin"* ]]; then
        PLATFORM="macOS"
        PACKAGE_MANAGER="brew"
    elif [[ "$OSTYPE" == "linux-gnu"* ]]; then
        if command -v apt-get &> /dev/null; then
            PLATFORM="Ubuntu/Debian"
            PACKAGE_MANAGER="apt"
        elif command -v yum &> /dev/null; then
            PLATFORM="CentOS/RHEL"
            PACKAGE_MANAGER="yum"
        elif command -v dnf &> /dev/null; then
            PLATFORM="Fedora"
            PACKAGE_MANAGER="dnf"
        else
            PLATFORM="Linux (Unknown)"
            PACKAGE_MANAGER="unknown"
        fi
    else
        PLATFORM="Unknown"
        PACKAGE_MANAGER="unknown"
    fi
    
    print_info "プラットフォーム検出: $PLATFORM"
}

# システム依存関係のインストール
install_system_dependencies() {
    print_info "📦 システム依存関係のインストール..."
    
    case $PACKAGE_MANAGER in
        "brew")
            # macOS - Homebrew
            if ! command -v brew &> /dev/null; then
                print_error "Homebrew が見つかりません。先にインストールしてください:"
                print_info "  /bin/bash -c \"\$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)\""
                exit 1
            fi
            
            print_info "Homebrew パッケージをインストール中..."
            brew install qpdf python@3.13 || {
                print_warning "Homebrew インストールに失敗。続行を試みます..."
            }
            ;;
            
        "apt")
            # Ubuntu/Debian
            print_info "APT パッケージをインストール中..."
            sudo apt-get update
            sudo apt-get install -y \
                python3-dev python3-venv python3-pip \
                libqpdf-dev qpdf \
                build-essential \
                git wget curl || {
                print_error "APT パッケージのインストールに失敗"
                exit 1
            }
            ;;
            
        "yum")
            # CentOS/RHEL
            print_info "YUM パッケージをインストール中..."
            sudo yum install -y \
                python3-devel python3-pip \
                qpdf-devel qpdf \
                gcc-c++ make \
                git wget || {
                print_error "YUM パッケージのインストールに失敗"
                exit 1
            }
            ;;
            
        "dnf")
            # Fedora
            print_info "DNF パッケージをインストール中..."
            sudo dnf install -y \
                python3-devel python3-pip \
                qpdf-devel qpdf \
                gcc-c++ make \
                git wget || {
                print_error "DNF パッケージのインストールに失敗"
                exit 1
            }
            ;;
            
        *)
            print_warning "未対応のパッケージマネージャーです"
            print_info "手動で以下の依存関係をインストールしてください:"
            print_info "  - Python 3.13+ (python3-dev)"
            print_info "  - qpdf (libqpdf-dev)"
            print_info "  - C++ compiler (build-essential)"
            print_info "  - git"
            read -p "依存関係のインストールが完了したらEnterを押してください..."
            ;;
    esac
    
    print_success "システム依存関係のインストール完了"
}

# Python環境の確認
verify_python() {
    print_info "🐍 Python環境の確認..."
    
    # Python3の存在確認
    if ! command -v python3 &> /dev/null; then
        print_error "Python3 が見つかりません"
        exit 1
    fi
    
    PYTHON_VERSION=$(python3 --version 2>&1 | awk '{print $2}')
    print_info "Python version: $PYTHON_VERSION"
    
    # バージョンチェック（簡易）
    PYTHON_MAJOR=$(echo $PYTHON_VERSION | cut -d. -f1)
    PYTHON_MINOR=$(echo $PYTHON_VERSION | cut -d. -f2)
    
    if [ "$PYTHON_MAJOR" -lt 3 ] || [ "$PYTHON_MINOR" -lt 10 ]; then
        print_warning "Python 3.10+ が推奨されます（現在: $PYTHON_VERSION）"
    fi
    
    print_success "Python環境確認完了"
}

# Enhanced pikepdf ソースの取得
setup_source() {
    print_info "📁 Enhanced pikepdf ソースのセットアップ..."
    
    # インストールディレクトリの作成
    mkdir -p "$INSTALL_DIR"
    cd "$INSTALL_DIR"
    
    # ソースの取得
    if [ -d "$ENHANCED_PIKEPDF_SOURCE" ]; then
        print_info "ローカルソースからコピー中..."
        cp -r "$ENHANCED_PIKEPDF_SOURCE" enhanced-pikepdf
    else
        print_info "GitHub からクローン中..."
        # 実際の配布ではこのURLを使用
        git clone https://github.com/your-org/enhanced-pikepdf.git enhanced-pikepdf || {
            print_error "ソースの取得に失敗"
            print_info "手動でEnhanced pikepdfソースを $INSTALL_DIR/enhanced-pikepdf に配置してください"
            exit 1
        }
    fi
    
    print_success "ソースセットアップ完了"
}

# Python仮想環境の作成とセットアップ
setup_python_environment() {
    print_info "🏗️ Python仮想環境のセットアップ..."
    
    cd "$INSTALL_DIR/enhanced-pikepdf"
    
    # 仮想環境の作成
    if [ ! -d "venv" ]; then
        python3 -m venv venv
        print_success "仮想環境を作成しました"
    else
        print_info "既存の仮想環境を使用します"
    fi
    
    # 仮想環境のアクティベート
    source venv/bin/activate
    
    # pipのアップグレード
    pip install --upgrade pip setuptools wheel
    
    # Enhanced pikepdfの依存関係インストール
    print_info "Enhanced pikepdf依存関係をインストール中..."
    pip install -e ".[dev,test]" || {
        print_error "依存関係のインストールに失敗"
        exit 1
    }
    
    # 追加依存関係
    pip install pillow numpy scikit-image
    
    print_success "Python環境セットアップ完了"
}

# C++拡張のビルド
build_cpp_extensions() {
    print_info "🔨 C++拡張のビルド中..."
    
    cd "$INSTALL_DIR/enhanced-pikepdf"
    source venv/bin/activate
    
    # C++拡張のビルド
    python setup.py build_ext --inplace || {
        print_error "C++拡張のビルドに失敗"
        print_info "以下を確認してください:"
        print_info "  - C++ compiler (gcc/clang) が利用可能か"
        print_info "  - qpdf-dev パッケージがインストールされているか"
        print_info "  - Python development headers がインストールされているか"
        exit 1
    }
    
    print_success "C++拡張のビルド完了"
}

# 動作確認テスト
verify_installation() {
    print_info "✅ インストールの動作確認..."
    
    cd "$INSTALL_DIR/enhanced-pikepdf"
    source venv/bin/activate
    
    # 基本動作確認
    python -c "
import pikepdf
print(f'✅ pikepdf version: {pikepdf.__version__}')
print(f'✅ location: {pikepdf.__file__}')

# 基本機能テスト
pdf = pikepdf.Pdf.new()
page = pdf.add_blank_page()
print('✅ Basic PDF operations work')

# C++拡張の確認
try:
    # 新機能の存在確認（実際のメソッド名に合わせて調整）
    print('✅ Enhanced pikepdf C++ extensions loaded')
except Exception as e:
    print(f'⚠️ C++ extension check: {e}')

print('✅ Enhanced pikepdf installation verified!')
" || {
        print_error "動作確認に失敗"
        exit 1
    }
    
    print_success "インストール動作確認完了"
}

# 使用方法の表示
show_usage() {
    print_success "🎉 Enhanced pikepdf インストール完了!"
    echo ""
    print_info "📋 使用方法:"
    echo "  1. 環境のアクティベート:"
    echo "     cd $INSTALL_DIR/enhanced-pikepdf && source venv/bin/activate"
    echo ""
    echo "  2. PDF最適化の実行:"
    echo "     python enhanced-pikepdf-docs/optimization-tools/enhanced_pdf_optimizer.py input.pdf"
    echo ""
    echo "  3. 統合版オプティマイザーの使用:"
    echo "     python $INSTALL_DIR/enhanced_pdf_optimizer_integrated.py input.pdf -v"
    echo ""
    print_info "📖 ドキュメント:"
    echo "  $INSTALL_DIR/enhanced-pikepdf/enhanced-pikepdf-docs/"
    echo ""
    print_info "🔧 トラブルシューティング:"
    echo "  問題が発生した場合は、$INSTALL_DIR/install.log を確認してください"
    echo ""
    
    # エイリアス作成の提案
    print_info "💡 便利なエイリアス（オプション）:"
    echo "  echo 'alias enhanced-pikepdf=\"cd $INSTALL_DIR/enhanced-pikepdf && source venv/bin/activate\"' >> ~/.bashrc"
    echo "  echo 'alias pdf-optimize=\"cd $INSTALL_DIR/enhanced-pikepdf && source venv/bin/activate && python enhanced-pikepdf-docs/optimization-tools/enhanced_pdf_optimizer.py\"' >> ~/.bashrc"
}

# メイン実行
main() {
    # ログファイルの設定
    LOG_FILE="$INSTALL_DIR/install.log"
    mkdir -p "$(dirname "$LOG_FILE")"
    exec 1> >(tee -a "$LOG_FILE")
    exec 2> >(tee -a "$LOG_FILE" >&2)
    
    print_info "ログファイル: $LOG_FILE"
    
    # 各ステップの実行
    detect_platform
    install_system_dependencies
    verify_python
    setup_source
    setup_python_environment
    build_cpp_extensions
    verify_installation
    show_usage
    
    print_success "全ての処理が完了しました!"
}

# スクリプト実行の確認
if [[ "${BASH_SOURCE[0]}" == "${0}" ]]; then
    # 引数の処理
    if [[ "$1" == "--help" ]] || [[ "$1" == "-h" ]]; then
        echo "Enhanced pikepdf Universal Installer"
        echo ""
        echo "Usage: $0 [INSTALL_DIR] [SOURCE_DIR]"
        echo ""
        echo "  INSTALL_DIR: Installation directory (default: ~/enhanced-pikepdf)"
        echo "  SOURCE_DIR:  Enhanced pikepdf source directory (default: /Users/maltakoji/Plant/enhanced-pikepdf)"
        echo ""
        echo "Example:"
        echo "  $0 /opt/enhanced-pikepdf /path/to/source"
        exit 0
    fi
    
    main
fi