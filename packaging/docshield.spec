# -*- mode: python ; coding: utf-8 -*-
"""PyInstaller spec for DocShield (M7).

Targets: macOS, Linux, Windows. The same spec drives all three; the
build scripts in this folder pick the right output format per OS.

Why a hand-written spec instead of bare ``pyinstaller`` flags:

* spaCy's models (``en_core_web_lg``, ``it_core_news_lg``) ship as
  separate Python packages with non-Python data files (vectors,
  vocabulary, model.bin). PyInstaller doesn't pick those up by default —
  ``collect_all`` is the documented work-around.
* Presidio loads recogniser YAML files and a built-in conf at runtime;
  same problem.
* PySide6's Qt plugins (platforms, styles) must be co-located with the
  binary or the GUI won't render.

Build:

    .venv/bin/pyinstaller --noconfirm packaging/docshield.spec

The result lands in ``dist/DocShield`` (folder mode) — chosen over
``--onefile`` because onefile re-extracts ~600 MB of model data to a
temp dir on every launch, which hurts cold start badly. Folder mode is
still portable: zip it, hand it over, the user double-clicks the inner
binary. No installer, no admin (NFR-3.1).
"""

from PyInstaller.utils.hooks import collect_all, copy_metadata

block_cipher = None

datas: list = []
binaries: list = []
hiddenimports: list = []

# Pull in everything (Python files, native libs, data) for the heavy deps.
for pkg in (
    "spacy",
    "thinc",
    "srsly",
    "blis",
    "preshed",
    "cymem",
    "murmurhash",
    "wasabi",
    "catalogue",
    "confection",
    "presidio_analyzer",
    "presidio_anonymizer",
    "en_core_web_lg",
    "it_core_news_lg",
    "langdetect",
):
    pkg_datas, pkg_bins, pkg_hidden = collect_all(pkg)
    datas += pkg_datas
    binaries += pkg_bins
    hiddenimports += pkg_hidden

# Some Presidio recogniser configs are read by ``importlib.metadata`` —
# without metadata files the analyzer raises at startup.
for pkg in ("presidio_analyzer", "presidio_anonymizer", "spacy"):
    datas += copy_metadata(pkg)


a = Analysis(
    ["entry.py"],
    pathex=["../src"],
    binaries=binaries,
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    runtime_hooks=[],
    excludes=[
        # Trim a bit; none of these are used by DocShield.
        "tkinter",
        "matplotlib",
        "scipy",
        "pandas",
        "IPython",
        "jupyter",
    ],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name="DocShield",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    console=False,  # GUI app; no terminal window on Windows/macOS
    disable_windowed_traceback=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)

coll = COLLECT(
    exe,
    a.binaries,
    a.zipfiles,
    a.datas,
    strip=False,
    upx=False,
    upx_exclude=[],
    name="DocShield",
)

# macOS .app bundle (ignored on other OSes).
import sys

if sys.platform == "darwin":
    app = BUNDLE(
        coll,
        name="DocShield.app",
        icon=None,
        bundle_identifier="com.docshield.app",
        info_plist={
            "CFBundleShortVersionString": "0.1.0",
            "CFBundleVersion": "0.1.0",
            "NSHighResolutionCapable": True,
            # Lets the app read user-chosen .docx files without the macOS
            # Files-and-Folders prompt blocking the open-file dialog.
            "NSDocumentsFolderUsageDescription": "DocShield reads .docx files you select.",
            "NSDesktopFolderUsageDescription": "DocShield reads .docx files you select.",
            "NSDownloadsFolderUsageDescription": "DocShield reads .docx files you select.",
        },
    )
