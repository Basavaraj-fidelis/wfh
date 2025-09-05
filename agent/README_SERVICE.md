
# WFH Monitoring Agent - Service Installation

This guide helps you install the WFH Monitoring Agent as a background service on different operating systems.

## Windows Service Installation

1. **Run as Administrator**: Right-click Command Prompt and select "Run as administrator"
2. **Navigate to agent folder**: `cd C:\path\to\agent\folder`
3. **Run installer**: `install_service_windows.bat`

The script will:
- Install Python dependencies
- Download and install NSSM (service manager)
- Create and start the Windows service
- Configure automatic startup

### Windows Service Management

```cmd
# Start service
nssm start "WFH-Agent"

# Stop service
nssm stop "WFH-Agent"

# Restart service
nssm restart "WFH-Agent"

# Remove service
nssm remove "WFH-Agent" confirm

# Check status
sc query "WFH-Agent"
```

## Linux SystemD Service Installation

1. **Navigate to agent folder**: `cd /path/to/agent/folder`
2. **Make script executable**: `chmod +x install_service_linux.sh`
3. **Run installer**: `./install_service_linux.sh`

### Linux Service Management

```bash
# Check status
sudo systemctl status wfh-agent

# Start service
sudo systemctl start wfh-agent

# Stop service
sudo systemctl stop wfh-agent

# Restart service
sudo systemctl restart wfh-agent

# View logs
sudo journalctl -u wfh-agent -f

# Disable automatic startup
sudo systemctl disable wfh-agent
```

## macOS LaunchAgent Installation

1. **Navigate to agent folder**: `cd /path/to/agent/folder`
2. **Make script executable**: `chmod +x install_service_mac.sh`
3. **Run installer**: `./install_service_mac.sh`

### macOS Service Management

```bash
# Start service
launchctl start com.company.wfh-agent

# Stop service
launchctl stop com.company.wfh-agent

# Unload service
launchctl unload ~/Library/LaunchAgents/com.company.wfh-agent.plist

# Check if running
launchctl list | grep wfh-agent
```

## Logs and Monitoring

All platforms will create a `service.log` file in the agent directory containing:
- Agent startup/shutdown messages
- Heartbeat confirmations
- Detailed log submissions
- Error messages

Monitor this file to ensure the agent is working correctly:

```bash
# View recent logs
tail -f service.log

# View all logs
cat service.log
```

## Troubleshooting

### Windows
- Ensure you're running as Administrator
- Check Windows Event Viewer for service errors
- Verify Python is in system PATH

### Linux
- Check systemctl status for error details
- Ensure user has proper permissions
- Verify Python3 is installed

### macOS
- Grant necessary permissions in System Preferences
- Ensure Python3 is available at `/usr/bin/python3`
- Check Console.app for LaunchAgent errors

## Manual Service Operation

If automatic installation fails, you can run the service wrapper manually:

```bash
python3 service_wrapper.py
```

This will run the agent in service mode with proper logging and error recovery.
