# Enhanced pikepdf Patches

## C++拡張の改造内容

### 1. _write_with_smask (object.cpp)
SMask参照を保持したままストリームデータを更新

### 2. replace_image_preserve_smask (page.cpp)
画像置換時にSMask参照を維持

## パッチ適用方法
```bash
cd pikepdf
git apply ../patches/*.patch
```

## パッチ作成方法
```bash
cd pikepdf
git diff main enhanced-features > ../patches/001-enhanced-features.patch
```
