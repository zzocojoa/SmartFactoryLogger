# -*- mode: python ; coding: utf-8 -*-
import atexit
import os
from pathlib import Path
import shutil
import sys
import tempfile

from PyInstaller.utils.hooks import collect_all, collect_submodules


SPEC_DIR = os.path.abspath(SPECPATH)
PROJECT_ROOT = os.path.abspath(os.path.join(SPEC_DIR, "..", ".."))

if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from backend.version import (
    BUILD_PROVENANCE_FILENAME,
    verify_build_source_commit,
    write_build_provenance_file,
)


BUILD_PROVENANCE_DIR = tempfile.mkdtemp(prefix='smartfactory-build-provenance-')
atexit.register(shutil.rmtree, BUILD_PROVENANCE_DIR, ignore_errors=True)
BUILD_PROVENANCE_PATH = os.path.join(BUILD_PROVENANCE_DIR, BUILD_PROVENANCE_FILENAME)
BUILD_GIT_COMMIT = write_build_provenance_file(
    project_root=Path(PROJECT_ROOT),
    destination=Path(BUILD_PROVENANCE_PATH),
)
print(f'Build provenance git commit: {BUILD_GIT_COMMIT}')

datas = [
    (BUILD_PROVENANCE_PATH, 'backend'),
    (os.path.join(PROJECT_ROOT, 'frontend', 'dist'), 'frontend/dist'),
    (os.path.join(PROJECT_ROOT, 'backend', 'assets'), 'backend/assets'),
    (os.path.join(PROJECT_ROOT, 'scripts'), 'backend/scripts'),
]
binaries = []
hiddenimports = [
    'httpx', 'httpx._transports', 'httpx._transports.default', 
    'anyio', 'anyio._backends', 'anyio._backends._asyncio',
    'playwright', 'greenlet'
]
hiddenimports += collect_submodules('backend')

tmp_ret = collect_all('pydantic')
datas += tmp_ret[0]; binaries += tmp_ret[1]; hiddenimports += tmp_ret[2]
tmp_ret = collect_all('pydantic_core')
datas += tmp_ret[0]; binaries += tmp_ret[1]; hiddenimports += tmp_ret[2]
tmp_ret = collect_all('playwright')
datas += tmp_ret[0]; binaries += tmp_ret[1]; hiddenimports += tmp_ret[2]
a = Analysis(
    [os.path.join(PROJECT_ROOT, 'backend', 'scripts', 'legacy_servers', 'server_entry.py')],
    pathex=[PROJECT_ROOT],
    binaries=binaries,
    datas=datas + [(os.path.join(PROJECT_ROOT, 'backend', '__init__.py'), 'backend')],
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
    a.binaries,
    a.datas,
    [],
    name='SmartFactoryBackend',
    icon=os.path.join(PROJECT_ROOT, 'backend', 'assets', 'icon.ico'),
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
)

verify_build_source_commit(Path(PROJECT_ROOT), BUILD_GIT_COMMIT)
print(f'Build provenance verified after packaging: {BUILD_GIT_COMMIT}')
