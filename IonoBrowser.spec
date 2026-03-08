# IonoBrowser.spec
# PyInstaller build spec for IonoBrowser
# Run with: pyinstaller IonoBrowser.spec

from PyInstaller.utils.hooks import collect_data_files, collect_dynamic_libs, collect_submodules

block_cipher = None

a = Analysis(
    ['ionobrowser.py'],
    pathex=[],
    binaries=collect_dynamic_libs('PyQt6'),
    datas=[
        # PyQt6 resources (translations, plugins, etc.)
        *collect_data_files('PyQt6'),
        # Include the entire ionobrowser package
        ('ionobrowser', 'ionobrowser'),
    ],
    hiddenimports=[
        'PyQt6.QtCore',
        'PyQt6.QtGui',
        'PyQt6.QtWidgets',
        'PyQt6.sip',
        'websockets',
        'websockets.legacy',
        'websockets.legacy.client',
        'pkg_resources.extern',
        # ionobrowser submodules — explicit so PyInstaller doesn't miss any
        *collect_submodules('ionobrowser'),
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
    name='IonoBrowser',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=False,      # no console window
    disable_windowed_traceback=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    # icon='appimage/ionobrowser.ico',  # uncomment if you add an icon file
)