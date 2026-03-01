@echo off
setlocal
cd /d "%~dp0"

where python >nul 2>nul
if errorlevel 1 (
  echo [ERROR] "python" not found in PATH. Please install Python and ensure python.exe is available.
  exit /b 1
)

if not exist ".venv\\Scripts\\python.exe" (
  python -m venv .venv || exit /b 1
)

call ".venv\\Scripts\\activate.bat" || exit /b 1

python -m pip install -U pip || exit /b 1
python -m pip install -r requirements.txt -r requirements-build.txt || exit /b 1

if exist build rmdir /s /q build
if exist dist rmdir /s /q dist

python -m PyInstaller --noconfirm --clean --noconsole --onefile --name TdxHevoSyncTool main.py || exit /b 1

if exist dist\\TdxHevoSyncTool rmdir /s /q dist\\TdxHevoSyncTool

echo.
echo [OK] Build finished.
echo - onefile: dist\\TdxHevoSyncTool.exe
pause
