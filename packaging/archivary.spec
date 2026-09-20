# -*- mode: python ; coding: utf-8 -*-
"""PyInstaller spec for Archivary.

Build a standalone app for the platform you are running on:

    pyinstaller packaging/archivary.spec --noconfirm

Outputs (under ``dist/``):

* Windows  -> ``Archivary.exe``  (single file)
* Linux    -> ``Archivary``      (single file, ELF)
* macOS    -> ``Archivary.app``  (bundle)

PyInstaller cannot cross-compile, so each target must be built on its own OS.
The GitHub Actions workflow in ``.github/workflows/build.yml`` does this for
all three.  Generate the icon files first with ``packaging/make_icons.py``.
"""

import os
import sys

from PyInstaller.utils.hooks import collect_data_files, collect_submodules

ROOT = os.path.abspath(os.path.join(SPECPATH, os.pardir))  # noqa: F821
IS_MAC = sys.platform == "darwin"

hiddenimports = (
    collect_submodules("internetarchive")
    + collect_submodules("keyring.backends")
    + ["archivary", "archivary.app"]
)

datas = collect_data_files("internetarchive")
datas += [(os.path.join(ROOT, "assets"), "assets")]

if sys.platform == "win32":
    ICON = os.path.join(ROOT, "assets", "Archivary.ico")
elif IS_MAC:
    ICON = os.path.join(ROOT, "assets", "Archivary.icns")
else:
    ICON = None

a = Analysis(
    [os.path.join(ROOT, "run.py")],
    pathex=[ROOT],
    binaries=[],
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[
        "tkinter",
        "matplotlib",
        "numpy",
        "PySide6.QtWebEngineCore",
        "PySide6.QtWebEngineWidgets",
        "PySide6.Qt3DCore",
        "PySide6.QtCharts",
        "PySide6.QtDataVisualization",
        "PySide6.QtMultimedia",
        "PySide6.QtQuick",
        "PySide6.QtQml",
    ],
    noarchive=False,
    optimize=0,
)
pyz = PYZ(a.pure)

if IS_MAC:
    # On macOS the .app bundle is built from an onedir collection.
    exe = EXE(
        pyz,
        a.scripts,
        [],
        exclude_binaries=True,
        name="Archivary",
        debug=False,
        bootloader_ignore_signals=False,
        strip=False,
        upx=True,
        console=False,
        disable_windowed_traceback=False,
        argv_emulation=False,
        target_arch=None,
        codesign_identity=None,
        entitlements_file=None,
        icon=ICON,
    )
    coll = COLLECT(
        exe,
        a.binaries,
        a.datas,
        strip=False,
        upx=True,
        upx_exclude=[],
        name="Archivary",
    )
    app = BUNDLE(
        coll,
        name="Archivary.app",
        icon=ICON,
        bundle_identifier="org.archivary.Archivary",
        info_plist={
            "CFBundleName": "Archivary",
            "CFBundleDisplayName": "Archivary",
            "NSHighResolutionCapable": True,
        },
    )
else:
    exe = EXE(
        pyz,
        a.scripts,
        a.binaries,
        a.datas,
        [],
        name="Archivary",
        debug=False,
        bootloader_ignore_signals=False,
        strip=False,
        upx=True,
        upx_exclude=[],
        runtime_tmpdir=None,
        console=False,
        disable_windowed_traceback=False,
        argv_emulation=False,
        target_arch=None,
        codesign_identity=None,
        entitlements_file=None,
        icon=ICON,
    )
