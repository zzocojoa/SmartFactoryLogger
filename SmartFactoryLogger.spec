# -*- mode: python ; coding: utf-8 -*-
from PyInstaller.utils.hooks import collect_data_files

block_cipher = None

# CustomTkinter datas
# CTk needs its theme/json files to work
datas = collect_data_files('customtkinter')

# Exclude heavy libraries not used
# Verify carefully: 
# - pandas: Not used (we use CSV module and lists)
# - scipy: Not used
# - notebook, IPython: Dev tools
# - sqlite3: Not used (Using CSV)
# - tk/tcl: KEPT because we use tkinter
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
    'setuptools',
    'distutils'
]

a = Analysis(
    ['main.py'],
    pathex=[],
    binaries=[],
    datas=[('icon.ico', '.')] + datas, # [Fix] Bundle icon inside EXE
    hiddenimports=[],
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

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.zipfiles,
    a.datas,
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
    icon='icon.ico', # [Icon] 데스크탑/실행파일 아이콘 설정
)
