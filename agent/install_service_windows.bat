
@echo off
echo Installing WFH Monitoring Agent as Windows Service...
echo.

echo Step 1: Installing Python dependencies...
pip install -r agent_requirements.txt
pip install pywin32

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
nssm install "WFH-Agent" "%CD%\python.exe" "%CD%\service_wrapper.py"
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
