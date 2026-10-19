#!/usr/bin/env bash
# Builds dist/PBI2PPTX.app and dist/PBI2PPTX-<version>-macOS.dmg. Run from anywhere; needs uv and npm.
set -euo pipefail
cd "$(dirname "$0")/.."

npm --prefix ui ci --no-audit --no-fund
npm --prefix ui run build
uv sync --locked
uv run pyinstaller --noconfirm --clean --distpath dist --workpath build packaging/pbi2pptx.spec

# The packaged app must be able to build a Deck on its own (catches files the packager left out).
dist/PBI2PPTX.app/Contents/MacOS/PBI2PPTX --self-test

VERSION=$(uv run python -c "import pbi2pptx; print(pbi2pptx.__version__)")
DMG="dist/PBI2PPTX-${VERSION}-macOS.dmg"
rm -f "$DMG"
hdiutil create -quiet -volname "PBI2PPTX" -srcfolder dist/PBI2PPTX.app -ov -format UDZO "$DMG"
echo "Built dist/PBI2PPTX.app and $DMG"
