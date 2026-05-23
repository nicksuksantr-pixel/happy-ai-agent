# -*- mode: python ; coding: utf-8 -*-
import os
import customtkinter
from PyInstaller.utils.hooks import collect_all, collect_data_files, copy_metadata

datas = [
    ('VERSION', '.'),
    ('agents.py', '.'),
    ('auth.py', '.'),
    ('pipeline.py', '.'),
    ('file_loader.py', '.'),
    ('extractor.py', '.'),
    ('builder.py', '.'),
    ('updater.py', '.'),
    ('assets', 'assets'),
]

# Bake .env into the bundle if present — carries HAPPY_AI_UPDATE_TOKEN
# (read-only PAT for the private update repo). Only bundled when the
# file exists on the build machine. Gitignored.
import os as _os
if _os.path.exists('.env'):
    datas.append(('.env', '.'))
binaries = []
# v2.1.0: UI split into ui/ + core/ packages per the new-desktop-project
# playbook. PyInstaller's static import scan usually catches these via the
# import chain happy_native.py -> ui.app -> ui.pages.* -> core.*, but we
# list them explicitly so a future refactor (lazy import, importlib)
# doesn't quietly drop a module from the bundle.
hiddenimports = [
    # core
    'core', 'core.config', 'core.persistence',
    # ui root
    'ui', 'ui.app', 'ui.sidebar', 'ui.theme', 'ui.emoji_image',
    # ui.components
    'ui.components',
    'ui.components.logo',
    'ui.components.output_view',
    'ui.components.page_header',
    'ui.components.pill',
    'ui.components.placeholder_textbox',
    'ui.components.section_card',
    'ui.components.status_dot',
    # ui.pages
    'ui.pages',
    'ui.pages.home',
    'ui.pages.runs',
    'ui.pages.stats',
    'ui.pages.settings',
    'ui.pages.running',
    'ui.pages.done',
    # ui.modals
    'ui.modals',
    'ui.modals.dark_modal',
    # pystray system tray — platform backend isn't picked up by static scan
    'pystray',
    'pystray._win32',
    'pystray._util',
    'pystray._util.win32',
]
datas += copy_metadata('google-genai')

# customtkinter ships its own theme JSON + fonts → must be bundled.
# google.genai/auth/api_core → API runtime.
# pygments → code highlighting (used by happy_native.py).
# PIL → icon loading.
for _pkg in (
    'google.genai', 'google.auth', 'google.api_core',
    'pygments', 'customtkinter', 'PIL',
):
    try:
        _ret = collect_all(_pkg)
        datas += _ret[0]; binaries += _ret[1]; hiddenimports += _ret[2]
    except Exception:
        pass

# Fix v2.0.1: collect_all('customtkinter') misses the assets/ folder on some
# PyInstaller versions because the package's setup.py doesn't declare them in
# package_data. Without these, set_default_color_theme('blue') fails silently
# at widget render time → process runs but no window appears.
# Bundle them explicitly to the location CTk's runtime looks them up at.
_ctk_root = os.path.dirname(customtkinter.__file__)
_ctk_assets_src = os.path.join(_ctk_root, 'assets')
if os.path.isdir(_ctk_assets_src):
    datas += [
        (os.path.join(_ctk_assets_src, 'themes'), 'customtkinter/assets/themes'),
        (os.path.join(_ctk_assets_src, 'fonts'),  'customtkinter/assets/fonts'),
        (os.path.join(_ctk_assets_src, 'icons'),  'customtkinter/assets/icons'),
    ]
# Also catch any other non-py files inside the package as defense in depth.
datas += collect_data_files('customtkinter', include_py_files=False)


a = Analysis(
    ['happy_native.py'],
    pathex=[],
    binaries=binaries,
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[
        # Streamlit + Streamlit-specific stack — no longer used.
        # NOTE: do NOT exclude anyio/sniffio/h11/websockets — google.genai's
        # underlying httpx/httpcore stack needs them. v2.0.0 first build crashed
        # with "No module named 'anyio'" because of an over-aggressive exclude.
        'streamlit', 'tornado', 'altair', 'pyarrow', 'pydeck', 'pympler',
        # Browser wrapper — only needed by builder.py when user builds web .exe.
        # builder.py installs it lazily on the user's machine, so Happy AI Agent itself
        # does NOT need pywebview at runtime.
        'webview',
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
    name='HappyAIAgent',
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
    name='HappyAIAgent',
)
