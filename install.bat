@echo off
REM Installation script for gScreen on Windows
REM
REM Usage:
REM   install.bat          - Install dependencies
REM   install.bat run      - Install and run
REM   install.bat sync     - Install and sync only
REM   install.bat clean    - Clean up

setlocal enabledelayedexpansion

echo =========================================
echo gScreen Windows Installation Script
echo =========================================
echo.

REM Get script directory
set "SCRIPT_DIR=%~dp0"
cd /d "%SCRIPT_DIR%"

REM Check Python installation
python --version >nul 2>&1
if errorlevel 1 (
    echo ERROR: Python is not installed or not in PATH
    echo Please install Python 3.8 or later from https://www.python.org/
    pause
    exit /b 1
)

for /f "tokens=2" %%i in ('python --version 2^>^&1') do set PYTHON_VERSION=%%i
echo Found Python %PYTHON_VERSION%

REM Parse command argument
set "COMMAND=%~1"

if /i "%COMMAND%"=="clean" goto :clean
if /i "%COMMAND%"=="uninstall" goto :clean

echo.
echo =========================================
echo Installing Python dependencies...
echo =========================================
echo.

REM Install required Python packages (suppress all output)
set PIP_QUIET=1
pip install --upgrade pip --quiet >nul 2>&1
pip install pygame-ce --quiet >nul 2>&1
pip install gdown --quiet >nul 2>&1
pip install requests --quiet >nul 2>&1
pip install tenacity --quiet >nul 2>&1
pip install Pillow --quiet >nul 2>&1

echo.
echo Python packages installed successfully.
echo.

REM Check if Flutter is available
flutter --version >nul 2>&1
if errorlevel 1 (
    echo WARNING: Flutter is not installed or not in PATH
    echo For Flutter UI, install from https://flutter.dev/
    echo.
) else (
    echo Flutter found:
    flutter --version | findstr /B "Flutter"
    echo.
)

REM Create media directory if not exists
if not exist "media" (
    mkdir media
    echo Created media directory.
)

REM Create run scripts
echo @echo off > run.bat
echo python "%%~dp0main.py" %%* >> run.bat

echo @echo off > sync.bat  
echo python "%%~dp0main.py" --sync-only %%* >> run.bat

echo.
echo =========================================
echo Installation complete!
echo =========================================
echo.
echo To run gScreen:
echo   run.bat
echo.
echo To sync only:
echo   sync.bat
echo.
echo To run with Flutter:
echo   flutter run -d windows
echo.
echo Next steps:
echo 1. Edit google_drive.url and add your Google Drive folder URL
echo 2. Run: run.bat
echo.

REM Execute command if provided
if /i "%COMMAND%"=="run" (
    echo Starting gScreen...
    call run.bat
    goto :end
)

if /i "%COMMAND%"=="sync" (
    echo Syncing from Google Drive...
    call sync.bat
    goto :end
)

pause
goto :end

:clean
echo.
echo Cleaning up...
if exist "media" rmdir /s /q "media"
if exist "__pycache__" rmdir /s /q "__pycache__"
if exist "build" rmdir /s /q "build"
echo Cleanup complete.
echo.
pause
goto :end

:end
endlocal
