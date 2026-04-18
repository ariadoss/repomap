#!/usr/bin/env bash
# Vendor tree-sitter-languages into the vendor/ directory for offline use.
# Run this once on your platform to create a local fallback.
#
# Usage: ./scripts/vendor-deps.sh
#
# This copies the installed tree-sitter and tree-sitter-languages packages
# into vendor/ so repomap can use them when PyPI/GitHub are unreachable.
# The vendored files are platform-specific (different per OS/arch/Python version).

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
REPO_DIR="$(dirname "$SCRIPT_DIR")"
VENDOR_DIR="$REPO_DIR/vendor"

# Ensure dependencies are installed
python3 -m pip install tree-sitter==0.21.3 tree-sitter-languages==1.10.2 --quiet

# Find site-packages
SITE_PACKAGES=$(python3 -c "import site; print(site.getsitepackages()[0])")

# Clean and create vendor dir
rm -rf "$VENDOR_DIR"
mkdir -p "$VENDOR_DIR"

# Copy packages
cp -r "$SITE_PACKAGES/tree_sitter" "$VENDOR_DIR/"
cp -r "$SITE_PACKAGES/tree_sitter_languages" "$VENDOR_DIR/"

SIZE=$(du -sh "$VENDOR_DIR" | cut -f1)
echo "Vendored tree-sitter-languages to $VENDOR_DIR ($SIZE)"
echo ""
echo "Add vendor/ to .gitignore (it's platform-specific) or use Git LFS."
echo "The fallback will be used automatically when PyPI/GitHub are unreachable."
