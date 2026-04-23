# -*- mode: python ; coding: utf-8 -*-
"""
PyInstaller spec file for Trends — Linux build
"""

import os
import ctypes.util

block_cipher = None

# Ищем libsnap7.so в системе
snap7_binaries = []
libsnap7 = ctypes.util.find_library('snap7')
if libsnap7:
    import ctypes
    # find_library возвращает имя, нужен полный путь
    for search_dir in ['/usr/lib', '/usr/lib/x86_64-linux-gnu', '/usr/local/lib']:
        candidate = os.path.join(search_dir, f'lib{libsnap7}') if not libsnap7.startswith('lib') else os.path.join(search_dir, libsnap7)
        if os.path.exists(candidate):
            snap7_binaries = [(candidate, '.')]
            break
        # Попробуем с .so расширением
        candidate2 = os.path.join(search_dir, 'libsnap7.so')
        if os.path.exists(candidate2):
            snap7_binaries = [(candidate2, '.')]
            break
        candidate3 = os.path.join(search_dir, 'libsnap7.so.1')
        if os.path.exists(candidate3):
            snap7_binaries = [(candidate3, '.')]
            break

a = Analysis(
    ['trends_app.py'],
    pathex=[],
    binaries=snap7_binaries,
    datas=[
        ('config.yaml', '.'),
        ('web/templates', 'web/templates'),
        ('assets/trends.png', 'assets'),
    ],
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
        'pystray._appindicator',
        'pystray._gtk',
        'pystray._xorg',
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
    excludes=['pystray._win32', 'pystray._darwin'],
    cipher=block_cipher,
    noarchive=False,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name='Trends',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    icon='assets/trends.png',
)

# Папка с бинарниками (не onefile, для совместимости с GTK)
coll = COLLECT(
    exe,
    a.binaries,
    a.zipfiles,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name='Trends',
)
