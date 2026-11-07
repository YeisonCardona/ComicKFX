#!/usr/bin/env bash

set -euo pipefail

# Clean previous build
rm -rf ./lib
rm -f ./generate_comic_kfx.zip

mkdir -p ./lib

rm -rf "$HOME/Library/Preferences/calibre/plugins/_comic_kfx_libs"

# 1. Install dependencies requiring Python 3.14 ARM64 binaries
python3.14 -m pip install numpy lxml pillow --target ./lib/ \
    --platform macosx_11_0_arm64 \
    --implementation cp \
    --python-version 3.14 \
    --only-binary=:all: \
    --force-reinstall --no-cache-dir

# 2. Install remaining dependencies
python3.14 -m pip install amazon-ion rarfile --target ./lib/ \
    --force-reinstall --no-cache-dir

# 3. Patch amazon-ion
echo "Applying amazon-ion cache initialization patch..."
python3.14 ./patch_amazon_ion.py

# 4. Copy kckfxgen
cp -r ../kckfxgen/ ./lib/kckfxgen

# 5. Generate plugin ZIP
echo "Generating generate_comic_kfx.zip..."
zip -r ../generate_comic_kfx.zip lib/ images/ __init__.py ui.py plugin-import-name-generate_comic_kfx.txt

# 6. Install plugin
/Applications/calibre.app/Contents/MacOS/calibre-customize -a ../generate_comic_kfx.zip

# 7. Remove temporary build directory
rm -rf ./lib

echo "Plugin installed successfully."
