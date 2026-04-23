# -*- mode: python ; coding: utf-8 -*-
"""
PyInstaller spec file for Trends — Windows build (single .exe)
"""

import os
import importlib.util

block_cipher = None

# Dynamically locate the snap7 package (works in any venv / CI environment)
_snap7_spec = importlib.util.find_spec('snap7')
if _snap7_spec:
    _snap7_dir = os.path.dirname(_snap7_spec.origin)
    snap7_datas = [(_snap7_dir, 'snap7')]
else:
    snap7_datas = []

a = Analysis(
    ['trends_app.py'],
    pathex=[],
    binaries=[],
    datas=[
        ('config.yaml', '.'),
        ('web/templates', 'web/templates'),
        ('web/static', 'web/static'),
        ('assets/trends.ico', 'assets'),
    ] + snap7_datas,
    hiddenimports=[
        'uvicorn.logging',
        'uvicorn.loops',
        'uvicorn.loops.auto',
        'uvicorn.protocols',
        'uvicorn.protocols.http',
        'uvicorn.protocols.http.auto',
        'uvicorn.protocols.websockets',
        'uvicorn.protocols.websockets.auto',
        'uvicorn.lifespan',
        'uvicorn.lifespan.on',
        'pystray._win32',
        'PIL._tkinter_finder',
        'snap7',
        'snap7.client',
        'snap7.server',
        'snap7.util',
        'snap7.common',
        'snap7.types',
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
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
    name='Trends',
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
    icon='assets/trends.ico',
)
