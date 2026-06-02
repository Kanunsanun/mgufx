# -*- mode: python ; coding: utf-8 -*-
"""PyInstaller 設定（onefile・単一exe）。

要点:
- sounddevice 同梱の ASIO 対応 PortAudio DLL は `_sounddevice_data` パッケージ内に
  あり、collect_all で datas/binaries として確実に同梱しないと ASIO が動かない。
- onefile では実行時に一時フォルダへ展開され、sounddevice は _sounddevice_data の
  パスから DLL を見つけるため、構造ごと同梱する必要がある。
"""

from PyInstaller.utils.hooks import collect_all

datas, binaries, hiddenimports = [], [], []

# sounddevice 本体と同梱DLL（ASIO含む）を丸ごと収集
for pkg in ("sounddevice", "_sounddevice_data"):
    d, b, h = collect_all(pkg)
    datas += d
    binaries += b
    hiddenimports += h

# scipy.signal(sosfilt) / numpy は標準フックで概ね解決されるが明示しておく
hiddenimports += ["scipy.signal", "scipy.special.cython_special", "numpy"]

a = Analysis(
    ["run.py"],
    pathex=[],
    binaries=binaries,
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    runtime_hooks=[],
    # 未使用の重量級ライブラリを除外してサイズ削減
    excludes=["pyqtgraph", "matplotlib", "tkinter", "PySide2", "PySide6", "PyQt6"],
    noarchive=False,
)

pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.datas,
    [],
    name="MG12XU-StereoFX",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=False,          # GUIアプリ（コンソール非表示）
    disable_windowed_traceback=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=None,              # アイコンを用意したら "icon.ico" を指定
)
