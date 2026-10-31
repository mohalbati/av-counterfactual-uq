@echo off
REM ---------------------------------------------------------------------------
REM  Double-click to record the CARLA demo (scenario S02, four drivers).
REM  Extra options can be passed, e.g.:  run_carla_demo.bat --scenario S09
REM ---------------------------------------------------------------------------
set CARLA_EXE=C:\CARLA_0.9.15\WindowsNoEditor\CarlaUE4.exe
cd /d "%~dp0"

REM 1) Python 3.10 is required (CARLA 0.9.15 has Windows packages for Python 3.7-3.10 only)
py -3.10 --version >nul 2>&1
if errorlevel 1 (
  echo.
  echo Python 3.10 is not installed. Install "Python 3.10.11 Windows installer 64-bit" from
  echo https://www.python.org/downloads/release/python-31011/  and run this file again.
  pause
  exit /b 1
)

REM 2) Install the Python packages the first time
py -3.10 -c "import carla, numpy, PIL, imageio_ffmpeg" >nul 2>&1
if errorlevel 1 (
  echo Installing Python packages ^(first run only^) ...
  py -3.10 -m pip install --upgrade pip
  py -3.10 -m pip install carla==0.9.15 numpy pillow "imageio[ffmpeg]"
)

REM 3) Start the simulator if it is not running, and give it time to load
tasklist /FI "IMAGENAME eq CarlaUE4-Win64-Shipping.exe" | find /I "CarlaUE4" >nul
if errorlevel 1 (
  echo Starting CARLA ...
  start "" "%CARLA_EXE%" -quality-level=Epic
  echo Waiting 90 s for the simulator to load ^(the CARLA window will show a city^) ...
  timeout /t 90 /nobreak >nul
)

REM 4) Record the demo
py -3.10 scripts\carla_demo.py %*
echo.
echo The video is in the "results" folder.
pause
