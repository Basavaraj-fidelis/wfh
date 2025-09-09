
@echo off
echo Installing WFH Monitoring Agent as Windows Service...
echo.

echo Checking current directory...
echo Current directory: %CD%

REM Change to the directory where this batch file is located
cd /d "%~dp0"

if not exist "agent_requirements.txt" (
    echo Error: agent_requirements.txt not found in current directory: %CD%
    echo Please ensure agent.py and agent_requirements.txt are in the same folder as install_service_windows.bat
    pause
    exit /b 1
)

echo Step 1: Installing Python dependencies...
pip install -r agent_requirements.txt
if %ERRORLEVEL% NEQ 0 (
    echo Error: Failed to install agent requirements
    pause
    exit /b 1
)

pip install pywin32
if %ERRORLEVEL% NEQ 0 (
    echo Error: Failed to install pywin32
    pause
    exit /b 1
)

echo.
echo Step 2: Installing NSSM (Non-Sucking Service Manager)...
echo Downloading NSSM...
powershell -Command "Invoke-WebRequest -Uri 'https://nssm.cc/release/nssm-2.24.zip' -OutFile 'nssm.zip'"
powershell -Command "Expand-Archive -Path 'nssm.zip' -DestinationPath '.'"
copy "nssm-2.24\win64\nssm.exe" .
del nssm.zip
rmdir /s /q nssm-2.24

echo.
echo Step 3: Creating Windows Service...
for /f "tokens=*" %%i in ('where python') do set PYTHON_PATH=%%i
if "%PYTHON_PATH%"=="" (
    echo Error: Python not found in PATH
    pause
    exit /b 1
)

nssm install "WFH-Agent" "%PYTHON_PATH%" "%CD%\service_wrapper.py"
nssm set "WFH-Agent" AppDirectory "%CD%"
nssm set "WFH-Agent" DisplayName "WFH Monitoring Agent"
nssm set "WFH-Agent" Description "Employee monitoring agent for work from home"
nssm set "WFH-Agent" Start SERVICE_AUTO_START
nssm set "WFH-Agent" AppStdout "%CD%\service.log"
nssm set "WFH-Agent" AppStderr "%CD%\service.log"

echo.
echo Step 4: Starting service...
nssm start "WFH-Agent"

echo.
echo Service installed and started successfully!
echo.
echo Service Management Commands:
echo   Start:   nssm start "WFH-Agent"
echo   Stop:    nssm stop "WFH-Agent"
echo   Restart: nssm restart "WFH-Agent"
echo   Remove:  nssm remove "WFH-Agent" confirm
echo.
echo Check service.log for agent output
pause
