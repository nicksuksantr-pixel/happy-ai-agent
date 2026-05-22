# -*- mode: python ; coding: utf-8 -*-
"""
PyInstaller spec — Happy AI Agent Setup (folder mode)

Bundles dist/HappyAIAgent.zip as payload. Folder output gets zipped by
build_installer.py for one-file distribution.

Folder mode (NOT onefile) because PyInstaller --onefile + --windowed has a
known Tk window-creation bug on Windows.
"""
import os
from pathlib import Path
import customtkinter
from PyInstaller.utils.hooks import collect_all, collect_data_files

ROOT = Path.cwd()

datas = [
    (str(ROOT / 'VERSION'), '.'),
    (str(ROOT / 'dist' / 'HappyAIAgent.zip'), 'payload'),
    (str(ROOT / 'assets'), 'assets'),
]
binaries = []
hiddenimports = ['win32com.client', 'pythoncom']

# Same CTk/PIL bundling pitfall as the main app — installer is also a
# --windowed CTk app and needs theme JSON + Tcl/Tk DLLs to even draw a window.
for _pkg in ('customtkinter', 'PIL'):
    try:
        _ret = collect_all(_pkg)
        datas += _ret[0]; binaries += _ret[1]; hiddenimports += _ret[2]
    except Exception:
        pass

# Explicit CTk assets (collect_all sometimes misses the JSON theme files
# because CTk's setup.py doesn't declare them in package_data).
_ctk_root = os.path.dirname(customtkinter.__file__)
_ctk_assets_src = os.path.join(_ctk_root, 'assets')
if os.path.isdir(_ctk_assets_src):
    datas += [
        (os.path.join(_ctk_assets_src, 'themes'), 'customtkinter/assets/themes'),
        (os.path.join(_ctk_assets_src, 'fonts'),  'customtkinter/assets/fonts'),
        (os.path.join(_ctk_assets_src, 'icons'),  'customtkinter/assets/icons'),
    ]
datas += collect_data_files('customtkinter', include_py_files=False)


a = Analysis(
    [str(ROOT / 'installer' / 'installer.py')],
    pathex=[str(ROOT)],
    binaries=binaries,
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[
        # Installer is tiny — exclude what the main app drags in but installer
        # doesn't need at all.
        'matplotlib', 'scipy', 'numpy.f2py', 'pytest', 'sphinx',
        'google.genai', 'google.auth', 'google.api_core',
        'pygments', 'docx', 'openpyxl', 'pypdf',
        'streamlit', 'tornado', 'altair', 'pyarrow', 'pympler',
    ],
    noarchive=False,
    optimize=0,
)

pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name='HappyAIAgent-Setup',
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
    icon=str(ROOT / 'assets' / 'happy_logo.ico'),
)
coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name='HappyAIAgent-Setup',
)
