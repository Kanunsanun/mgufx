@echo off
rem === 開発環境セットアップ: ローカル .venv を作成し依存を導入 ===
cd /d %~dp0

echo [setup] 仮想環境 .venv を作成します...
python -m venv .venv
if errorlevel 1 (
    echo [エラー] python が見つかりません。Python 3.x をインストールしてください。
    pause
    exit /b 1
)

echo [setup] 依存パッケージを導入します（実行時＋ビルド）...
".venv\Scripts\python.exe" -m pip install --upgrade pip
".venv\Scripts\python.exe" -m pip install -r requirements-dev.txt

echo.
echo [setup] 完了しました。
echo   起動  : mgfx.bat
echo   配布  : build.bat  （dist\MG12XU-StereoFX.exe を生成）
pause
