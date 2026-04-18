#!/usr/bin/env bash
# Build a Linux DocShield bundle. Must be run on Linux — PyInstaller
# can't cross-compile. For maximum portability, build inside an older
# glibc (e.g. Ubuntu 20.04 or a manylinux image); binaries built on a
# newer glibc won't run on older distros.
#
# Output: dist/DocShield/DocShield   (portable folder + launcher)

set -euo pipefail

cd "$(dirname "$0")/.."

if [ ! -x .venv/bin/pyinstaller ]; then
    echo "PyInstaller not found in .venv." >&2
    exit 1
fi

.venv/bin/python - <<'PY'
import importlib.util, sys
missing = [m for m in ("en_core_web_lg", "it_core_news_lg") if importlib.util.find_spec(m) is None]
if missing:
    sys.exit(f"missing spaCy models: {missing}")
PY

rm -rf build dist
.venv/bin/pyinstaller --noconfirm --clean packaging/docshield.spec

# Create a tiny launcher script users can run directly.
cat > dist/DocShield/run-docshield.sh <<'EOF'
#!/usr/bin/env bash
DIR="$(cd "$(dirname "$0")" && pwd)"
exec "$DIR/DocShield" "$@"
EOF
chmod +x dist/DocShield/run-docshield.sh

echo "Built: dist/DocShield/    (zip this folder and ship it)"
du -sh dist/DocShield || true
