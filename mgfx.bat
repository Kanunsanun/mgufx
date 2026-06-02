@echo off
rem === MG12XU Stereo FX ランチャー ===
rem プロジェクトルート(このbatの場所)へ移動
cd /d %~dp0

rem 仮想環境の解決: ローカル .venv を優先、無ければ親(共有) ..\.venv にフォールバック
set "PY=.venv\Scripts\python.exe"
if not exist "%PY%" set "PY=..\.venv\Scripts\python.exe"

if not exist "%PY%" (
    echo [エラー] Python 仮想環境が見つかりません。
    echo   %~dp0.venv  または  %~dp0..\.venv  を作成してください。
    echo   setup.bat を実行すると自動作成できます。
    pause
    exit /b 1
)

"%PY%" -m mgfx.app
if errorlevel 1 pause
