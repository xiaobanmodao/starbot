@echo off
setlocal
title StarBot Launcher

cd /d "%~dp0"

echo ========================================
echo            STARBOT LAUNCHER
echo ========================================
echo.

if not exist "package.json" (
  echo [ERROR] package.json not found in current folder.
  echo Put this launcher in the project root.
  echo.
  pause
  exit /b 1
)

where node >nul 2>nul
if errorlevel 1 (
  echo [INFO] Node.js not found. Trying auto install via winget...
  where winget >nul 2>nul
  if errorlevel 1 (
    echo [ERROR] winget not available on this system.
    echo Please install Node.js LTS manually: https://nodejs.org/
    echo.
    pause
    exit /b 1
  )

  winget install -e --id OpenJS.NodeJS.LTS --accept-package-agreements --accept-source-agreements
  if errorlevel 1 (
    echo [ERROR] Auto install failed.
    echo Try running this file as Administrator, or install Node.js manually.
    echo.
    pause
    exit /b 1
  )

  set "PATH=%ProgramFiles%\nodejs;%PATH%"
  where node >nul 2>nul
  if errorlevel 1 (
    echo [WARN] Node installed, but not visible in this window yet.
    echo Close this window and run start_starbot.bat again.
    echo.
    pause
    exit /b 0
  )
)

where npm >nul 2>nul
if errorlevel 1 (
  echo [ERROR] npm not found. Reinstall Node.js LTS.
  echo.
  pause
  exit /b 1
)

if not exist "node_modules" (
  echo [INFO] Installing dependencies...
  call npm install
  if errorlevel 1 (
    echo.
    echo [ERROR] npm install failed. Check network and retry.
    pause
    exit /b 1
  )
) else (
  echo [INFO] Checking dependencies...
  call npm install
)

echo.
echo [INFO] Starting StarBot...
echo.
call npm start

echo.
echo [INFO] StarBot exited.
pause
endlocal
