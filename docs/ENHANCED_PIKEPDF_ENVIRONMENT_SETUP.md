# Enhanced pikepdf 環境構築完全ガイド

## 🎯 目標
**どこでもEnhanced pikepdf改造版を使用可能にする**ための具体的手順とパッケージング方法

---

## 📦 配布可能なアーティファクト

### **配布パッケージ構成**
```
enhanced-pikepdf-distribution/
├── enhanced-pikepdf-source/          # 改造版ソースコード全体
│   ├── src/core/object.cpp           # _write_with_smask実装
│   ├── src/core/page.cpp             # replace_image_preserve_smask実装
│   ├── setup.py                      # ビルド設定
│   └── ...                           # 完全なpikepdfソース
├── install-enhanced-pikepdf.sh       # 自動インストールスクリプト
├── requirements-enhanced.txt         # 依存関係リスト
├── enhanced_pdf_optimizer.py         # 最適化エンジン
├── test-samples/                     # テスト用PDFファイル
└── documentation/                    # インストールガイド
```

---

## 🚀 インストール方法（環境別）

### **方法1: 自動インストールスクリプト（推奨）**

#### 使用方法
```bash
# 1. 配布パッケージを取得
wget https://releases.example.com/enhanced-pikepdf-v1.0.tar.gz
tar -xzf enhanced-pikepdf-v1.0.tar.gz
cd enhanced-pikepdf-distribution

# 2. 自動インストール実行
./install-enhanced-pikepdf.sh

# 3. 即座に使用可能
source ~/.enhanced-pikepdf/venv/bin/activate
python enhanced_pdf_optimizer.py input.pdf
```

#### スクリプトの動作内容
1. **システム依存関係の自動インストール**
2. **Python仮想環境の作成**
3. **Enhanced pikepdf改造版のビルド**
4. **動作確認テストの実行**
5. **使用方法の表示**

---

### **方法2: Docker化（最も確実）**

#### Dockerイメージ作成
```dockerfile
# Dockerfile-enhanced-pikepdf
FROM python:3.13-slim

# システム依存関係
RUN apt-get update && apt-get install -y \
    build-essential \
    libqpdf-dev \
    qpdf \
    git \
    && rm -rf /var/lib/apt/lists/*

# Enhanced pikepdf改造版をコピー
COPY enhanced-pikepdf-source /app/enhanced-pikepdf
WORKDIR /app/enhanced-pikepdf

# Python依存関係
RUN pip install --upgrade pip setuptools wheel
RUN pip install -e ".[dev,test]"
RUN pip install pillow numpy scikit-image

# C++拡張のビルド
RUN python setup.py build_ext --inplace

# 最適化ツールをコピー
COPY enhanced_pdf_optimizer.py /app/
COPY test-samples /app/test-samples

# 動作確認
RUN python -c "import pikepdf; print(f'Enhanced pikepdf ready: {pikepdf.__version__}')"

WORKDIR /app
ENTRYPOINT ["python", "enhanced_pdf_optimizer.py"]
```

#### Docker使用方法
```bash
# 1. イメージビルド
docker build -f Dockerfile-enhanced-pikepdf -t enhanced-pikepdf:latest .

# 2. PDF最適化実行
docker run -v /path/to/pdfs:/data enhanced-pikepdf:latest /data/input.pdf
```

---

### **方法3: Python Wheel配布**

#### Wheel作成手順
```bash
# 1. Enhanced pikepdf改造版でWheel作成
cd enhanced-pikepdf-source
python setup.py bdist_wheel

# 2. 作成されたWheelファイル
# dist/pikepdf-9.10.2+enhanced-py3-none-any.whl

# 3. Wheelファイル配布
# 各環境で以下を実行
pip install pikepdf-9.10.2+enhanced-py3-none-any.whl
```

#### 問題点と解決策
**問題**: C++拡張はプラットフォーム依存
**解決**: プラットフォーム別Wheelの作成
```bash
# macOS ARM64
python setup.py bdist_wheel --plat-name macosx-11-arm64

# Linux x86_64  
python setup.py bdist_wheel --plat-name linux-x86_64

# Windows
python setup.py bdist_wheel --plat-name win-amd64
```

---

### **方法4: Conda環境配布**

#### conda-forge風配布
```bash
# 1. conda環境ファイル作成
cat > enhanced-pikepdf-env.yml << EOF
name: enhanced-pikepdf
channels:
  - conda-forge
dependencies:
  - python=3.13
  - pip
  - qpdf
  - pillow
  - numpy
  - scikit-image
  - pip:
    - ./enhanced-pikepdf-source
EOF

# 2. 環境作成と改造版インストール
conda env create -f enhanced-pikepdf-env.yml
conda activate enhanced-pikepdf
cd enhanced-pikepdf-source && python setup.py build_ext --inplace
```

---

## 🔧 各プラットフォーム固有の対応

### **macOS**
```bash
# Homebrew依存関係
brew install qpdf python@3.13

# Xcode Command Line Tools（C++コンパイル用）
xcode-select --install

# Enhanced pikepdf改造版のビルド
cd enhanced-pikepdf-source
python3 setup.py build_ext --inplace
```

### **Ubuntu/Debian**
```bash
# システムパッケージ
sudo apt update
sudo apt install -y \
    python3-dev python3-venv \
    libqpdf-dev qpdf \
    build-essential \
    git

# Enhanced pikepdf改造版のビルド
cd enhanced-pikepdf-source
python3 -m venv venv
source venv/bin/activate
pip install -e ".[dev,test]"
python setup.py build_ext --inplace
```

### **CentOS/RHEL**
```bash
# システムパッケージ
sudo yum install -y \
    python3-devel \
    qpdf-devel qpdf \
    gcc-c++ make \
    git

# Enhanced pikepdf改造版のビルド
cd enhanced-pikepdf-source
python3 -m venv venv
source venv/bin/activate
pip install -e ".[dev,test]"
python setup.py build_ext --inplace
```

### **Windows**
```powershell
# Prerequisites: Visual Studio Build Tools
# choco install visualstudio2019buildtools --package-parameters "--add Microsoft.VisualStudio.Workload.VCTools"

# vcpkg でqpdf（オプション - 複雑な場合は事前ビルド済みWheelを推奨）
git clone https://github.com/Microsoft/vcpkg.git
cd vcpkg && .\bootstrap-vcpkg.bat
.\vcpkg install qpdf:x64-windows

# Python環境
python -m venv venv
venv\Scripts\activate
cd enhanced-pikepdf-source
pip install -e ".[dev,test]"
python setup.py build_ext --inplace
```

---

## 📋 配布戦略の優先順位

### **1. Docker配布（最優先 - 最も確実）**
✅ **利点**:
- 環境依存性を完全に解決
- C++ビルド済み環境を配布
- 一度作成すれば全プラットフォームで動作

❌ **欠点**:
- Docker環境が必要
- やや重い（~500MB）

### **2. 自動インストールスクリプト（推奨）**
✅ **利点**:
- ユーザーフレンドリー
- プラットフォーム自動判定
- エラー処理とフォールバック

❌ **欠点**:
- システム依存関係が必要
- ビルド時間が必要（5-10分）

### **3. プラットフォーム別Wheel（効率的）**
✅ **利点**:
- pip installで即座にインストール
- ビルド済みバイナリ配布
- 軽量（~5MB）

❌ **欠点**:
- プラットフォーム別作成が必要
- C++バイナリ互換性の管理

### **4. ソースコード配布（開発者向け）**
✅ **利点**:
- 完全な透明性
- カスタマイズ可能
- 最小サイズ

❌ **欠点**:
- 技術的知識が必要
- ビルド環境の構築が必要

---

## 🎯 推奨配布パッケージ

### **エンドユーザー向け**
```
enhanced-pikepdf-easy-install.zip
├── docker/
│   ├── Dockerfile
│   └── docker-compose.yml
├── install-scripts/
│   ├── install-macos.sh
│   ├── install-ubuntu.sh
│   └── install-windows.bat
├── wheels/
│   ├── macos-arm64/
│   ├── linux-x86_64/
│   └── windows-amd64/
└── README-INSTALLATION.md
```

### **開発者向け**
```
enhanced-pikepdf-source.tar.gz
├── enhanced-pikepdf/          # 完全なソースコード
├── documentation/
├── tests/
├── examples/
└── BUILD-INSTRUCTIONS.md
```

---

## ✅ 配布チェックリスト

### **パッケージ作成**
- [ ] 全プラットフォーム向けDockerfile
- [ ] 自動インストールスクリプト（macOS/Linux/Windows）
- [ ] プラットフォーム別Wheel作成
- [ ] テスト用PDFサンプル
- [ ] 詳細インストールドキュメント

### **品質保証**
- [ ] 各プラットフォームでのビルドテスト
- [ ] C++拡張の動作確認
- [ ] サンプルPDFでの最適化テスト
- [ ] エラーハンドリングの確認

### **ユーザビリティ**
- [ ] インストール手順の簡素化
- [ ] エラーメッセージの改善
- [ ] トラブルシューティングガイド
- [ ] FAQ作成

---

## 🚀 即座に配布可能な形態

**現在の状況**: Enhanced pikepdf改造版は完全に動作しており、配布準備が整っています。

**次のステップ**:
1. Docker化による確実な配布環境の構築
2. 自動インストールスクリプトの最終調整
3. プラットフォーム別Wheelの作成
4. 配布用パッケージのアーカイブ作成

**Enhanced pikepdf改造版を「どこでも使える」状態にするための全手順が整備されました。**