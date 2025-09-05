
#!/bin/bash
echo "Installing WFH Monitoring Agent as Linux SystemD Service..."
echo

echo "Step 1: Installing Python dependencies..."
pip3 install -r agent_requirements.txt

echo
echo "Step 2: Creating systemd service file..."
sudo tee /etc/systemd/system/wfh-agent.service > /dev/null <<EOF
[Unit]
Description=WFH Monitoring Agent
After=network.target

[Service]
Type=simple
User=$USER
WorkingDirectory=$(pwd)
ExecStart=/usr/bin/python3 $(pwd)/service_wrapper.py
Restart=always
RestartSec=10
StandardOutput=append:$(pwd)/service.log
StandardError=append:$(pwd)/service.log

[Install]
WantedBy=multi-user.target
EOF

echo
echo "Step 3: Enabling and starting service..."
sudo systemctl daemon-reload
sudo systemctl enable wfh-agent.service
sudo systemctl start wfh-agent.service

echo
echo "Service installed and started successfully!"
echo
echo "Service Management Commands:"
echo "  Status:  sudo systemctl status wfh-agent"
echo "  Start:   sudo systemctl start wfh-agent"
echo "  Stop:    sudo systemctl stop wfh-agent"
echo "  Restart: sudo systemctl restart wfh-agent"
echo "  Logs:    sudo journalctl -u wfh-agent -f"
echo
echo "Check service.log for agent output"
