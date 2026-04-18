# Packaging DocShield

Portable bundles per OS, no admin rights at install or run time (NFR-3.1).

## Quick build

| OS | Command |
|---|---|
| macOS | `./packaging/build_macos.sh` |
| Linux | `./packaging/build_linux.sh` (must run on Linux) |
| Windows | `.\packaging\build_windows.ps1` (must run on Windows) |

All three produce `dist/DocShield/` — a portable folder the user can
double-click into and launch. macOS additionally produces
`dist/DocShield.app`.

PyInstaller cannot cross-compile. Build on the OS you're shipping to.

## Prerequisites

Same as the dev install, plus PyInstaller:

```
python -m venv .venv
source .venv/bin/activate
pip install -e ".[dev,gui]" pyinstaller
python -m spacy download en_core_web_lg
python -m spacy download it_core_news_lg
```

The build scripts check that both models are installed and fail fast if
they're not — otherwise PyInstaller silently skips them and the bundled
app crashes at first NER call.

## Bundle size

The spec targets ≤ 600 MB (NFR-3.2). Current size:

| Component | Size |
|---|---|
| `it_core_news_lg` | ~600 MB |
| `en_core_web_lg` | ~425 MB |
| PySide6 | ~70 MB |
| everything else | ~100 MB |
| **total** | **~1.2 GB** |

The two large spaCy models dominate. Options if size becomes a blocker:

1. **Swap `_lg` → `_md`** in `src/docshield/core/detector.py` and the
   build scripts. Drops ~1 GB. Expected NER recall drop: ~3–5 pp on
   PERSON/ORG. The spec's ≥ 95% recall acceptance criterion (§15) may
   need re-measurement.
2. **Distil + ONNX-runtime** (spec §6.1 alt). ~50 MB total but a
   significant engineering lift.
3. **Ship both `md` and `lg` as opt-in downloads** — breaks the
   "fully offline at runtime" guarantee unless the user fetches the
   `lg` model manually before first use.

For the MVP hand-off to a single lawyer, 1.2 GB is a one-time download
and fits comfortably on any modern laptop. We've left the spec's 600 MB
target aspirational rather than hit it by downgrading accuracy.

## Cold start

First launch of the bundle takes 10–20 s on macOS:

- PyInstaller's `COLLECT` mode (folder) extracts nothing at launch, so
  the only cold-start cost is spaCy loading the two models into RAM.
- On subsequent launches, the OS file cache makes load ~1 s.

We deliberately chose folder mode over `--onefile`. Onefile extracts the
entire bundle to a temp directory on every launch — with ~1 GB of model
data that adds 5–10 s of pure I/O per launch for no functional benefit.

## macOS signing & notarisation

The build script produces an unsigned `.app`. When a user who didn't
build it themselves double-clicks, Gatekeeper will refuse ("can't be
opened because Apple cannot check it for malicious software"). To
distribute to non-developers, either:

* Ship the folder bundle and tell users to run
  `xattr -dr com.apple.quarantine DocShield.app` after unzipping, or
* Sign with a Developer ID certificate and notarise. Populate
  `codesign_identity=` and `entitlements_file=` in `docshield.spec` and
  run `xcrun notarytool submit` after build.

## Linux portability

PyInstaller builds link against the glibc on the build machine. A binary
built on Ubuntu 24.04 (glibc 2.39) won't run on Ubuntu 20.04 (glibc
2.31). For the widest compatibility, build inside a `manylinux_2_28`
Docker image or an old-LTS VM.

## Verifying a bundle

```
dist/DocShield/DocShield            # Linux folder mode
dist/DocShield.app/Contents/MacOS/DocShield   # macOS, to see stderr
```

Expected first-run output on stderr:

```
[docshield] pre-warming spaCy models…
[docshield] pre-warm done in X.Xs
```

If you see `ImportError` or `MissingModelError`, the spec isn't picking
up a package. Check `build/docshield/warn-docshield.txt` for the list
of missing modules and add them to `hiddenimports` or `collect_all` in
`packaging/docshield.spec`.
