#!/usr/bin/env bash
# Build a macOS DocShield.app bundle.
#
# Usage:
#   ./packaging/build_macos.sh        # builds into ./dist
#
# Output:
#   dist/DocShield/         portable folder bundle (works on every Mac)
#   dist/DocShield.app      .app bundle for double-click launch
#
# Requirements: a populated .venv with all deps + the spaCy models, plus
# pyinstaller. See README.md for the dev setup.

set -euo pipefail

cd "$(dirname "$0")/.."

if [ ! -x .venv/bin/pyinstaller ]; then
    echo "PyInstaller not found in .venv. Install with: .venv/bin/pip install pyinstaller" >&2
    exit 1
fi

# Confirm models are present — PyInstaller will silently skip them
# otherwise and the bundled app will fail at first NER call.
.venv/bin/python - <<'PY'
import importlib.util, sys
missing = [m for m in ("en_core_web_lg", "it_core_news_lg") if importlib.util.find_spec(m) is None]
if missing:
    sys.exit(f"missing spaCy models: {missing}; run `python -m spacy download <name>`")
PY

rm -rf build dist

.venv/bin/pyinstaller --noconfirm --clean packaging/docshield.spec

echo
echo "Built: dist/DocShield/   (portable folder)"
echo "       dist/DocShield.app (double-click bundle)"
du -sh dist/DocShield dist/DocShield.app 2>/dev/null || true
