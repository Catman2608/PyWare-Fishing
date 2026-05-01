# PyWare.spec
# -*- mode: python ; coding: utf-8 -*-

a = Analysis(
    ['IcantFish.py'],
    pathex=[],
    binaries=[],
    datas=[('configs', 'configs')],
    hiddenimports=[
        'cv2',
        'numpy',
        'PIL',
        'PIL._tkinter_finder',
        'customtkinter',
        'pynput',
        'pynput.keyboard',
        'pynput.mouse',
        'mss',
        'mss.windows',
        'threading',
        'time',
        'json',
        'os',
        'subprocess',
        'webbrowser',
        'ctypes'
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    noarchive=False,
)
pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.datas,
    [],
    name='PyWare',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=False,  # Set to False for windowed mode (no console)
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)