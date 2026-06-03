# -*- mode: python ; coding: utf-8 -*-
"""PyInstaller 設定（onedir・インストーラー同梱用）。

要点:
- sounddevice 同梱の ASIO 対応 PortAudio DLL は `_sounddevice_data` パッケージ内に
  あり、collect_all で datas/binaries として確実に同梱しないと ASIO が動かない。
- scipy.stats._sobol(Cython) が動的に importlib.resources/metadata を参照するため明示同梱。
- onedir（フォルダ構成）で出力 → Inno Setup でインストーラー化。
  起動毎の展開が不要になり onefile より起動が速い。
"""

from PyInstaller.utils.hooks import collect_all

datas, binaries, hiddenimports = [], [], []

# sounddevice 本体と同梱DLL（ASIO含む）を丸ごと収集
for pkg in ("sounddevice", "_sounddevice_data"):
    d, b, h = collect_all(pkg)
    datas += d
    binaries += b
    hiddenimports += h

# scipy.signal(sosfilt) / numpy
hiddenimports += ["scipy.signal", "scipy.special.cython_special", "numpy"]
# scipy.stats._sobol が動的参照する標準ライブラリを明示同梱（起動クラッシュ防止）
hiddenimports += [
    "importlib.resources",
    "importlib.metadata",
    "importlib.resources.readers",
    "importlib.resources._common",
]

a = Analysis(
    ["run.py"],
    pathex=[],
    binaries=binaries,
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    runtime_hooks=[],
    excludes=["pyqtgraph", "matplotlib", "tkinter", "PySide2", "PySide6", "PyQt6"],
    noarchive=False,
)

pyz = PYZ(a.pure)

# onedir: EXE は実行ファイルのみ（依存は COLLECT で同フォルダに展開）
exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name="UFX-MG",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=False,          # GUIアプリ（コンソール非表示）
    disable_windowed_traceback=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon="icon.ico",
)

coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name="UFX-MG",          # 出力フォルダ dist/UFX-MG/
)
