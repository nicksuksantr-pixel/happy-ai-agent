# -*- mode: python ; coding: utf-8 -*-
from PyInstaller.utils.hooks import collect_submodules
from PyInstaller.utils.hooks import collect_all
from PyInstaller.utils.hooks import copy_metadata

datas = [('app.py', '.'), ('agents.py', '.'), ('auth.py', '.'), ('pipeline.py', '.'), ('file_loader.py', '.'), ('extractor.py', '.'), ('builder.py', '.'), ('assets', 'assets'), ('.streamlit', '.streamlit')]
binaries = []
hiddenimports = []
datas += copy_metadata('streamlit')
datas += copy_metadata('google-genai')

# Fix 2026-05-15: ใช้ collect_all แทน collect_submodules สำหรับ google.genai
# (collect_submodules ใส่แต่ module names ใน hiddenimports — ไม่ copy ไฟล์ .py เข้า bundle
#  → ตอน runtime import เจอ module name แต่ไม่มีไฟล์ → ImportError)
for _pkg in ('google.genai', 'google.auth', 'google.api_core',
             'streamlit', 'pygments',
             # ASGI stack — PyInstaller missed these on its own
             'starlette', 'uvicorn', 'anyio', 'sniffio', 'h11', 'websockets'):
    try:
        _ret = collect_all(_pkg)
        datas += _ret[0]; binaries += _ret[1]; hiddenimports += _ret[2]
    except Exception:
        pass


a = Analysis(
    ['happy_desktop.py'],
    pathex=[],
    binaries=binaries,
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    noarchive=False,
    optimize=0,
)
pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name='HAPPY',
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
    icon=['assets\\happy_logo.ico'],
)
coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name='HAPPY',
)
