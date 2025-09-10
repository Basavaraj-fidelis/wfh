#!/bin/bash
# Employee Installation Script for WFH Monitoring Agent
# This script sets up the monitoring agent on an employee's workstation

echo "WFH Monitoring Agent Installation Script"
echo "========================================"

# Check if running with proper permissions
if [[ $EUID -eq 0 ]]; then
    echo "Please do not run this script as root. Run as the employee user."
    exit 1
fi

# Get employee information
echo ""
echo "Employee Information Setup"
echo "------------------------"
read -p "Employee ID: " EMPLOYEE_ID
read -p "Employee Email: " EMPLOYEE_EMAIL
read -p "Employee Name: " EMPLOYEE_NAME
read -p "Department: " DEPARTMENT
read -p "Manager Name: " MANAGER

# Get server information
echo ""
echo "Server Configuration"
echo "-------------------"
read -p "WFH Server URL (e.g., https://your-server.com): " SERVER_URL
read -p "Agent Authentication Token: " AUTH_TOKEN

# Validate inputs
if [[ -z "$EMPLOYEE_ID" || -z "$EMPLOYEE_EMAIL" || -z "$SERVER_URL" || -z "$AUTH_TOKEN" ]]; then
    echo "Error: Employee ID, Email, Server URL, and Auth Token are required!"
    exit 1
fi

# Create environment file
echo ""
echo "Creating environment configuration..."
cat > ~/.wfh_agent_env << EOF
# WFH Monitoring Agent Configuration
export WFH_EMPLOYEE_ID="$EMPLOYEE_ID"
export WFH_EMPLOYEE_EMAIL="$EMPLOYEE_EMAIL"
export WFH_EMPLOYEE_NAME="$EMPLOYEE_NAME"
export WFH_EMPLOYEE_DEPARTMENT="$DEPARTMENT"
export WFH_EMPLOYEE_MANAGER="$MANAGER"
export WFH_SERVER_URL="$SERVER_URL"
export WFH_AUTH_TOKEN="$AUTH_TOKEN"
EOF

# Make it secure
chmod 600 ~/.wfh_agent_env

# Add to shell profile
if [[ -f ~/.bashrc ]]; then
    if ! grep -q "wfh_agent_env" ~/.bashrc; then
        echo "source ~/.wfh_agent_env" >> ~/.bashrc
    fi
fi

if [[ -f ~/.zshrc ]]; then
    if ! grep -q "wfh_agent_env" ~/.zshrc; then
        echo "source ~/.wfh_agent_env" >> ~/.zshrc
    fi
fi

echo "✓ Environment configuration created"

# Install Python dependencies
echo ""
echo "Installing Python dependencies..."
if command -v pip3 &> /dev/null; then
    pip3 install --user -r agent_requirements.txt
elif command -v pip &> /dev/null; then
    pip install --user -r agent_requirements.txt
else
    echo "Warning: pip not found. Please install Python packages manually:"
    echo "pip install requests schedule Pillow psutil"
fi

echo "✓ Dependencies installed"

# Test connection
echo ""
echo "Testing server connection..."
source ~/.wfh_agent_env

# Create a simple test script
cat > test_connection.py << 'EOF'
import os
import requests
import sys

server_url = os.getenv('WFH_SERVER_URL')
auth_token = os.getenv('WFH_AUTH_TOKEN')

if not server_url or not auth_token:
    print("❌ Environment variables not set properly")
    sys.exit(1)

try:
    response = requests.post(
        f"{server_url}/api/heartbeat",
        json={
            "username": "test",
            "hostname": "test",
            "status": "test"
        },
        headers={"Authorization": f"Bearer {auth_token}"},
        timeout=10
    )
    
    if response.status_code == 200:
        print("✓ Server connection successful!")
    else:
        print(f"❌ Server connection failed: HTTP {response.status_code}")
except Exception as e:
    print(f"❌ Connection error: {e}")
EOF

python3 test_connection.py
rm test_connection.py

# Create systemd service (Linux)
if command -v systemctl &> /dev/null; then
    echo ""
    echo "Setting up systemd service..."
    
    SERVICE_FILE="$HOME/.config/systemd/user/wfh-agent.service"
    mkdir -p "$(dirname "$SERVICE_FILE")"
    
    cat > "$SERVICE_FILE" << EOF
[Unit]
Description=WFH Monitoring Agent
After=network.target

[Service]
Type=simple
User=$USER
WorkingDirectory=$(pwd)
Environment=PYTHONPATH=$(pwd)
EnvironmentFile=%h/.wfh_agent_env
ExecStart=$(which python3) service_wrapper.py
Restart=always
RestartSec=30

[Install]
WantedBy=default.target
EOF
    
    # Enable and start service
    systemctl --user daemon-reload
    systemctl --user enable wfh-agent.service
    echo "✓ Systemd service created and enabled"
    
    read -p "Start the monitoring agent now? (y/n): " START_NOW
    if [[ "$START_NOW" =~ ^[Yy]$ ]]; then
        systemctl --user start wfh-agent.service
        sleep 2
        if systemctl --user is-active --quiet wfh-agent.service; then
            echo "✓ Agent started successfully!"
        else
            echo "❌ Failed to start agent. Check logs with: journalctl --user -u wfh-agent.service"
        fi
    fi
fi

echo ""
echo "Installation Complete!"
echo "====================="
echo "Employee: $EMPLOYEE_NAME ($EMPLOYEE_ID)"
echo "Department: $DEPARTMENT"
echo "Server: $SERVER_URL"
echo ""
echo "Manual start: python3 main.py"
echo "Service status: systemctl --user status wfh-agent.service"
echo "View logs: journalctl --user -u wfh-agent.service -f"
echo ""
echo "The agent will now monitor this workstation and report to your WFH monitoring system."