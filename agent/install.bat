
@echo off
echo Installing WFH Monitoring Agent for Windows...
echo.

echo Step 1: Installing Python dependencies...
pip install -r agent_requirements.txt
if %ERRORLEVEL% NEQ 0 (
    echo Failed to install Python dependencies
    pause
    exit /b 1
)

echo.
echo Step 2: Testing agent connection...
python agent.py --test
if %ERRORLEVEL% NEQ 0 (
    echo Failed to connect to server. Please check your configuration.
    pause
    exit /b 1
)

echo.
echo Installation completed successfully!
echo You can now run the agent with: python agent.py
echo.
echo For Windows Service installation, run: install_service_windows.bat
pause
