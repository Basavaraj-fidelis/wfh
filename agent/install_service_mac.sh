
#!/bin/bash
echo "Installing WFH Monitoring Agent as macOS LaunchAgent..."
echo

echo "Step 1: Installing Python dependencies..."
pip3 install -r agent_requirements.txt

echo
echo "Step 2: Creating LaunchAgent plist file..."
PLIST_FILE="$HOME/Library/LaunchAgents/com.company.wfh-agent.plist"
mkdir -p "$HOME/Library/LaunchAgents"

cat > "$PLIST_FILE" <<EOF
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>Label</key>
    <string>com.company.wfh-agent</string>
    <key>ProgramArguments</key>
    <array>
        <string>/usr/bin/python3</string>
        <string>$(pwd)/service_wrapper.py</string>
    </array>
    <key>WorkingDirectory</key>
    <string>$(pwd)</string>
    <key>RunAtLoad</key>
    <true/>
    <key>KeepAlive</key>
    <true/>
    <key>StandardOutPath</key>
    <string>$(pwd)/service.log</string>
    <key>StandardErrorPath</key>
    <string>$(pwd)/service.log</string>
</dict>
</plist>
EOF

echo
echo "Step 3: Loading and starting LaunchAgent..."
launchctl load "$PLIST_FILE"
launchctl start com.company.wfh-agent

echo
echo "LaunchAgent installed and started successfully!"
echo
echo "Service Management Commands:"
echo "  Start:   launchctl start com.company.wfh-agent"
echo "  Stop:    launchctl stop com.company.wfh-agent"
echo "  Unload:  launchctl unload $PLIST_FILE"
echo
echo "Check service.log for agent output"
