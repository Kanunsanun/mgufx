@echo off
rem === 配布用 単一exe をビルド（PyInstaller / onefile） ===
cd /d %~dp0

rem 仮想環境の解決: ローカル .venv を優先、無ければ親(共有) ..\.venv
set "PY=.venv\Scripts\python.exe"
if not exist "%PY%" set "PY=..\.venv\Scripts\python.exe"
if not exist "%PY%" (
    echo [エラー] 仮想環境が見つかりません。先に setup.bat を実行してください。
    pause
    exit /b 1
)

rem PyInstaller の存在確認
"%PY%" -c "import PyInstaller" 2>nul
if errorlevel 1 (
    echo [setup] PyInstaller が未導入のため導入します...
    "%PY%" -m pip install pyinstaller
)

echo [build] 単一exe をビルドします...
"%PY%" -m PyInstaller --noconfirm --clean mgfx.spec
if errorlevel 1 (
    echo [エラー] ビルドに失敗しました。
    pause
    exit /b 1
)

echo.
echo [build] 完了: dist\MG12XU-StereoFX.exe
echo   このexe単体を配布できます（Python不要）。
pause
