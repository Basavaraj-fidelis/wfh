#!/usr/bin/env python3
"""
WFH Employee Monitoring Agent
Runs on employee laptops to send heartbeats and detailed logs to the central server.
"""

import os
import sys
import json
import time
import random
import socket
import platform
import threading
import schedule
import requests
from datetime import datetime, timedelta
from PIL import ImageGrab
import getpass

class MonitoringAgent:
    def __init__(self, server_url, auth_token):
        self.server_url = server_url.rstrip('/')
        self.auth_token = auth_token
        self.username = getpass.getuser()
        self.hostname = socket.gethostname()
        self.last_detailed_log = None
        self.detailed_logs_today = 0
        self.current_date = datetime.now().date()
        
    def get_headers(self):
        """Get authentication headers"""
        return {
            'Authorization': f'Bearer {self.auth_token}',
            'Content-Type': 'application/json'
        }
    
    def get_local_ip(self):
        """Get local IP address"""
        try:
            # Connect to external server to get local IP
            s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            s.connect(("8.8.8.8", 80))
            local_ip = s.getsockname()[0]
            s.close()
            return local_ip
        except:
            return "unknown"
    
    def get_public_ip(self):
        """Get public IP address"""
        try:
            response = requests.get('https://httpbin.org/ip', timeout=10)
            return response.json().get('origin', 'unknown')
        except:
            return "unknown"
    
    def get_location(self, public_ip):
        """Get approximate location from IP using ipinfo.io"""
        try:
            # Use ipinfo.io for accurate geolocation
            response = requests.get(f'https://ipinfo.io/{public_ip}/json', timeout=10)
            if response.status_code == 200:
                data = response.json()
                return json.dumps({
                    "ip": data.get('ip', public_ip),
                    "country": data.get('country', 'Unknown'),
                    "region": data.get('region', 'Unknown'), 
                    "city": data.get('city', 'Unknown'),
                    "provider": data.get('org', 'Unknown'),
                    "timezone": data.get('timezone', 'Unknown'),
                    "location": data.get('loc', 'Unknown')
                })
            else:
                # Fallback to basic info
                return json.dumps({
                    "ip": public_ip,
                    "country": "Unknown",
                    "region": "Unknown", 
                    "city": "Unknown",
                    "provider": "Unknown",
                    "error": f"ipinfo.io returned {response.status_code}"
                })
        except Exception as e:
            return json.dumps({"ip": public_ip, "error": f"Could not determine location: {str(e)}"})
    
    def take_screenshot(self):
        """Take screenshot and save temporarily - Cross-platform compatible"""
        try:
            # Cross-platform screenshot handling
            if platform.system() == "Darwin":  # macOS
                # On macOS, may need additional permissions for screen recording
                import subprocess
                try:
                    # Try using screencapture command first (native macOS)
                    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                    filename = f"temp_screenshot_{self.username}_{timestamp}.png"
                    subprocess.run(['screencapture', '-x', filename], check=True, timeout=30)
                    return filename
                except (subprocess.CalledProcessError, subprocess.TimeoutExpired):
                    # Fall back to PIL
                    pass
            
            # Standard cross-platform PIL approach
            screenshot = ImageGrab.grab()
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"temp_screenshot_{self.username}_{timestamp}.png"
            screenshot.save(filename)
            
            # Verify file was created
            if os.path.exists(filename):
                return filename
            else:
                print(f"Screenshot file not created: {filename}")
                return None
                
        except ImportError:
            print("PIL/Pillow not available for screenshots")
            return None
        except Exception as e:
            print(f"Failed to take screenshot: {e}")
            # For Linux systems that might need different handling
            if platform.system() == "Linux":
                print("Hint: On Linux, you may need: sudo apt-get install python3-tk python3-dev")
            elif platform.system() == "Darwin":
                print("Hint: On macOS, grant screen recording permissions in System Preferences")
            return None
    
    def send_heartbeat(self):
        """Send 5-minute heartbeat to server"""
        try:
            data = {
                "username": self.username,
                "hostname": self.hostname,
                "status": "online"
            }
            
            response = requests.post(
                f"{self.server_url}/api/heartbeat",
                json=data,
                headers=self.get_headers(),
                timeout=30
            )
            
            if response.status_code == 200:
                print(f"[{datetime.now()}] Heartbeat sent successfully")
            else:
                print(f"[{datetime.now()}] Heartbeat failed: {response.status_code}")
                
        except Exception as e:
            print(f"[{datetime.now()}] Heartbeat error: {e}")
    
    def send_detailed_log(self):
        """Send detailed log with screenshot"""
        # Check if we've already sent 2 logs today
        today = datetime.now().date()
        if today != self.current_date:
            # Reset daily counter for new day
            self.current_date = today
            self.detailed_logs_today = 0
        
        if self.detailed_logs_today >= 2:
            print(f"[{datetime.now()}] Already sent 2 detailed logs today, skipping")
            return
        
        try:
            print(f"[{datetime.now()}] Sending detailed log...")
            
            # Get network and location info
            local_ip = self.get_local_ip()
            public_ip = self.get_public_ip()
            location = self.get_location(public_ip)
            
            # Take screenshot
            screenshot_file = self.take_screenshot()
            if not screenshot_file:
                print("Failed to take screenshot, aborting detailed log")
                return
            
            # Prepare form data
            files = {
                'screenshot': open(screenshot_file, 'rb')
            }
            
            data = {
                'username': self.username,
                'hostname': self.hostname,
                'local_ip': local_ip,
                'public_ip': public_ip,
                'location': location
            }
            
            # Send to server
            headers = {'Authorization': f'Bearer {self.auth_token}'}
            response = requests.post(
                f"{self.server_url}/api/log",
                files=files,
                data=data,
                headers=headers,
                timeout=60
            )
            
            # Clean up temp screenshot
            files['screenshot'].close()
            if os.path.exists(screenshot_file):
                os.remove(screenshot_file)
            
            if response.status_code == 200:
                self.detailed_logs_today += 1
                print(f"[{datetime.now()}] Detailed log sent successfully ({self.detailed_logs_today}/2 today)")
            else:
                print(f"[{datetime.now()}] Detailed log failed: {response.status_code}")
                
        except Exception as e:
            print(f"[{datetime.now()}] Detailed log error: {e}")
            # Clean up temp file if it exists
            if 'screenshot_file' in locals() and os.path.exists(screenshot_file):
                os.remove(screenshot_file)
    
    def schedule_detailed_logs(self):
        """Schedule 2 random detailed logs per day between 8 AM and 10 PM"""
        # Clear previous detailed log schedules
        schedule.clear('detailed_logs')
        
        # Generate 2 random times between 8 AM (08:00) and 10 PM (22:00)
        times = []
        for _ in range(2):
            hour = random.randint(8, 21)  # 8 AM to 9 PM (since we want before 10 PM)
            minute = random.randint(0, 59)
            times.append(f"{hour:02d}:{minute:02d}")
        
        times.sort()  # Ensure they're in chronological order
        
        for time_str in times:
            schedule.every().day.at(time_str).do(self.send_detailed_log).tag('detailed_logs')
        
        print(f"[{datetime.now()}] Scheduled detailed logs for today at: {', '.join(times)}")
    
    def start(self):
        """Start the monitoring agent"""
        print(f"Starting WFH Monitoring Agent for {self.username}@{self.hostname}")
        print(f"Server: {self.server_url}")
        print(f"Starting at: {datetime.now()}")
        
        # Schedule heartbeats every 5 minutes
        schedule.every(5).minutes.do(self.send_heartbeat)
        
        # Schedule detailed logs (reschedule daily)
        schedule.every().day.at("00:01").do(self.schedule_detailed_logs)
        
        # Schedule initial detailed logs for today
        self.schedule_detailed_logs()
        
        # Send initial heartbeat
        self.send_heartbeat()
        
        print("Agent started. Press Ctrl+C to stop.")
        
        # Main loop
        try:
            while True:
                schedule.run_pending()
                time.sleep(30)  # Check every 30 seconds
        except KeyboardInterrupt:
            print("\nAgent stopped by user.")
        except Exception as e:
            print(f"Agent error: {e}")

def main():
    """Main function - configure and start agent"""
    # Configuration - modify these values
    SERVER_URL = "http://localhost:5000"  # Change to your server URL
    AUTH_TOKEN = "agent-secret-token-change-this-in-production"  # Agent authentication token
    
    # You can also read from environment variables or config file
    if len(sys.argv) >= 2:
        SERVER_URL = sys.argv[1]
    if len(sys.argv) >= 3:
        AUTH_TOKEN = sys.argv[2]
    
    # Create and start agent
    agent = MonitoringAgent(SERVER_URL, AUTH_TOKEN)
    agent.start()

if __name__ == "__main__":
    main()