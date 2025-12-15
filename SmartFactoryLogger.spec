# -*- mode: python ; coding: utf-8 -*-
from PyInstaller.utils.hooks import collect_data_files, collect_submodules

block_cipher = None

# CustomTkinter datas
# CTk needs its theme/json files to work
datas = collect_data_files('customtkinter')

# Collect all submodules in 'modules' package explicitly
hidden_modules = collect_submodules('modules')

# Exclude heavy libraries not used
# ... (Same excludes list) ...
excludes = [
    'pandas', 
    'scipy', 
    'notebook', 
    'IPython', 
    'sqlite3', 
    'PyQt5', 
    'PySide2',
    'curses',
    'lib2to3',
    'test',
    'unittest',
    'pydoc_data',
    'distutils'
]

a = Analysis(
    ['src/main.py'],
    pathex=['.', 'src'], # [Fix] Look in root and src
    binaries=[],
    datas=[('assets/icon.ico', 'assets'), ('config/config.ini', 'config')] + datas, 
    hiddenimports=['PIL', 'PIL.Image', 'requests'] + hidden_modules,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=excludes,
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)
pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

# [Splash Screen]
splash = Splash(
    'assets/icon.png',
    binaries=a.binaries,
    datas=a.datas,
    text_pos=(10, 240), # Bottom-Left (assuming 256px height)
    text_size=10,       # Smaller professional font
    text_color='white',
    always_on_top=True,
)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.zipfiles,
    a.datas,
    splash, # [Splash] Include splash target
    splash.binaries, # [Splash] Include splash binaries
    [],
    name='SmartFactoryLogger',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=False, # Windowed mode (no console)
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon='assets/icon.ico', # [Icon] 데스크탑/실행파일 아이콘 설정
)
