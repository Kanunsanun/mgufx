"""アプリ起動エントリポイント（PyInstaller のビルド対象 / 直接実行用）。

開発時は `mgfx.bat`（= python -m mgfx.app）でも起動できるが、PyInstaller は
モジュール実行(-m)を直接ビルドできないため、このスクリプトをエントリにする。
"""

from mgfx.app import main

if __name__ == "__main__":
    main()
