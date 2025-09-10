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
import psutil
import subprocess
from http.server import HTTPServer, BaseHTTPRequestHandler
import urllib.parse

class MonitoringAgent:
    def __init__(self, server_url, auth_token):
        self.server_url = server_url.rstrip('/')
        self.auth_token = auth_token
        self.username = getpass.getuser()
        self.hostname = socket.gethostname()
        self.last_detailed_log = None
        self.detailed_logs_today = 0
        self.current_date = datetime.now().date()
        self.last_activity_time = time.time()
        self.activity_log = []
        self.app_usage_log = []
        self.browser_events = []
        self.extension_server = None
        
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
        """Get public IP address with multiple fallback services"""
        # List of reliable IP detection services
        services = [
            ('https://api.ipify.org?format=json', 'ip'),
            ('https://ipapi.co/json/', 'ip'),
            ('https://ifconfig.me/ip', 'text'),
            ('https://icanhazip.com/', 'text'),
            ('https://httpbin.org/ip', 'origin')
        ]
        
        for url, key in services:
            try:
                response = requests.get(url, timeout=8)
                if response.status_code == 200:
                    if key == 'text':
                        # Plain text response
                        ip = response.text.strip()
                        if self._is_valid_ip(ip):
                            return ip
                    else:
                        # JSON response
                        data = response.json()
                        ip = data.get(key, '').strip()
                        if self._is_valid_ip(ip):
                            return ip
            except Exception as e:
                print(f"IP service {url} failed: {e}")
                continue
        
        return "unknown"
    
    def _is_valid_ip(self, ip):
        """Validate IP address format"""
        if not ip or ip == "unknown":
            return False
        # Basic IP validation
        parts = ip.split('.')
        if len(parts) != 4:
            return False
        try:
            for part in parts:
                num = int(part)
                if not 0 <= num <= 255:
                    return False
            return True
        except ValueError:
            return False
    
    def get_idle_time(self):
        """Get system idle time in seconds - Cross-platform"""
        try:
            system = platform.system()
            
            if system == "Windows":
                # Windows: Use GetLastInputInfo via ctypes
                import ctypes
                from ctypes import wintypes
                
                class LASTINPUTINFO(ctypes.Structure):
                    _fields_ = [('cbSize', wintypes.UINT), ('dwTime', wintypes.DWORD)]
                
                def get_last_input_time():
                    lii = LASTINPUTINFO()
                    lii.cbSize = ctypes.sizeof(LASTINPUTINFO)
                    ctypes.windll.user32.GetLastInputInfo(ctypes.byref(lii))
                    return lii.dwTime
                
                millis = ctypes.windll.kernel32.GetTickCount() - get_last_input_time()
                return millis / 1000.0
                
            elif system == "Darwin":  # macOS
                # macOS: Use Core Graphics
                try:
                    import Quartz
                    idle_time = Quartz.CGEventSourceSecondsSinceLastEventType(
                        Quartz.kCGEventSourceStateCombinedSessionState,
                        Quartz.kCGAnyInputEventType
                    )
                    return idle_time
                except ImportError:
                    # Fallback: Use ioreg command
                    try:
                        output = subprocess.check_output(['ioreg', '-c', 'IOHIDSystem'], 
                                                       universal_newlines=True, timeout=5)
                        for line in output.split('\n'):
                            if '"HIDIdleTime"' in line:
                                idle_ns = int(line.split('=')[1].strip())
                                return idle_ns / 1000000000.0  # Convert nanoseconds to seconds
                    except (subprocess.CalledProcessError, subprocess.TimeoutExpired, ValueError):
                        pass
                    return 0
                    
            elif system == "Linux":
                # Linux: Try multiple methods
                try:
                    # Method 1: xprintidle (if available)
                    result = subprocess.run(['xprintidle'], capture_output=True, text=True, timeout=5)
                    if result.returncode == 0:
                        return int(result.stdout.strip()) / 1000.0  # Convert ms to seconds
                except (subprocess.CalledProcessError, subprocess.TimeoutExpired, FileNotFoundError):
                    pass
                
                try:
                    # Method 2: Parse /proc/interrupts for input devices
                    with open('/proc/interrupts', 'r') as f:
                        content = f.read()
                    # This is a simplified approach - in reality you'd track changes over time
                    return 0  # Placeholder - would need more complex implementation
                except:
                    pass
                    
            return 0  # Unknown system or method failed
            
        except Exception as e:
            print(f"Error getting idle time: {e}")
            return 0
    
    def get_screen_lock_status(self):
        """Check if screen is locked - Cross-platform"""
        try:
            system = platform.system()
            
            if system == "Windows":
                import ctypes
                user32 = ctypes.windll.user32
                
                # Check if screen saver is running
                is_screensaver = user32.SystemParametersInfoW(0x0072, 0, None, 0)  # SPI_GETSCREENSAVERRUNNING
                
                # Check if workstation is locked
                hdesk = user32.OpenDesktopW("default", 0, False, 0x0100)  # DESKTOP_SWITCHDESKTOP
                is_locked = hdesk == 0
                
                return {
                    "is_locked": is_locked or is_screensaver,
                    "screensaver_active": is_screensaver
                }
                
            elif system == "Darwin":  # macOS
                try:
                    # Check if screen is locked using Quartz
                    import Quartz
                    session_dict = Quartz.CGSessionCopyCurrentDictionary()
                    if session_dict:
                        is_locked = session_dict.get('CGSSessionScreenIsLocked', False)
                        return {"is_locked": is_locked, "screensaver_active": False}
                except ImportError:
                    pass
                    
            elif system == "Linux":
                try:
                    # Check various Linux screen lock mechanisms
                    # GNOME screensaver
                    result = subprocess.run(['gnome-screensaver-command', '--query'], 
                                          capture_output=True, text=True, timeout=5)
                    if result.returncode == 0 and 'is active' in result.stdout:
                        return {"is_locked": True, "screensaver_active": True}
                    
                    # Check if display is off
                    result = subprocess.run(['xset', 'q'], capture_output=True, text=True, timeout=5)
                    if result.returncode == 0 and 'Monitor is Off' in result.stdout:
                        return {"is_locked": True, "screensaver_active": True}
                        
                except (subprocess.CalledProcessError, subprocess.TimeoutExpired, FileNotFoundError):
                    pass
                    
            return {"is_locked": False, "screensaver_active": False}
            
        except Exception as e:
            print(f"Error checking screen lock status: {e}")
            return {"is_locked": False, "screensaver_active": False}
    
    def get_websites_visited(self):
        """Get recently visited websites from browser extension or fallback to basic detection"""
        websites = []
        
        # First, try to get data from browser extension
        if self.browser_events:
            today = datetime.now().date()
            today_events = [
                event for event in self.browser_events
                if datetime.fromtimestamp(event.get('timestamp', 0) / 1000).date() == today
            ]
            
            # Process browser extension events
            url_visits = {}
            for event in today_events:
                if event.get('eventType') in ['tab_activated', 'tab_updated']:
                    url = event.get('data', {}).get('url', '')
                    title = event.get('data', {}).get('title', '')
                    
                    if url and not url.startswith('chrome://') and not url.startswith('edge://'):
                        if url in url_visits:
                            url_visits[url]['visits'] += 1
                        else:
                            url_visits[url] = {
                                "browser": "Extension",
                                "url": url,
                                "title": title,
                                "timestamp": datetime.fromtimestamp(event['timestamp'] / 1000).isoformat(),
                                "visits": 1
                            }
            
            websites = list(url_visits.values())
            
        # Fallback to basic detection if no extension data
        if not websites:
            try:
                system = platform.system()
                home = os.path.expanduser("~")
                
                # Chrome/Chromium history paths
                chrome_paths = []
                if system == "Windows":
                    chrome_paths = [
                        os.path.join(home, "AppData", "Local", "Google", "Chrome", "User Data", "Default", "History"),
                        os.path.join(home, "AppData", "Local", "Microsoft", "Edge", "User Data", "Default", "History")
                    ]
                elif system == "Darwin":
                    chrome_paths = [
                        os.path.join(home, "Library", "Application Support", "Google", "Chrome", "Default", "History"),
                        os.path.join(home, "Library", "Application Support", "Microsoft Edge", "Default", "History")
                    ]
                elif system == "Linux":
                    chrome_paths = [
                        os.path.join(home, ".config", "google-chrome", "Default", "History"),
                        os.path.join(home, ".config", "chromium", "Default", "History"),
                        os.path.join(home, ".config", "microsoft-edge", "Default", "History")
                    ]
                
                for path in chrome_paths:
                    if os.path.exists(path):
                        websites.append({
                            "browser": "Chrome/Edge",
                            "url": "Browser activity detected (Install extension for detailed tracking)",
                            "timestamp": datetime.now().isoformat(),
                            "visits": 1
                        })
                        break
                        
            except Exception as e:
                print(f"Error getting websites visited: {e}")
                
        return websites
    
    def start_extension_server(self):
        """Start HTTP server to receive data from browser extension"""
        class ExtensionHandler(BaseHTTPRequestHandler):
            def __init__(self, agent, *args, **kwargs):
                self.agent = agent
                super().__init__(*args, **kwargs)
            
            def do_POST(self):
                try:
                    content_length = int(self.headers['Content-Length'])
                    post_data = self.rfile.read(content_length)
                    data = json.loads(post_data.decode('utf-8'))
                    
                    # Handle different endpoint types
                    if self.path == '/browser-extension/ping':
                        self.send_response(200)
                        self.send_header('Content-Type', 'application/json')
                        self.send_header('Access-Control-Allow-Origin', '*')
                        self.end_headers()
                        self.wfile.write(json.dumps({"status": "ok"}).encode())
                        
                    elif self.path == '/browser-extension/event':
                        self.agent.handle_browser_event(data)
                        self.send_response(200)
                        self.send_header('Content-Type', 'application/json')
                        self.send_header('Access-Control-Allow-Origin', '*')
                        self.end_headers()
                        self.wfile.write(json.dumps({"status": "received"}).encode())
                        
                    elif self.path == '/browser-extension/sync':
                        events = data.get('events', [])
                        for event in events:
                            self.agent.handle_browser_event(event)
                        self.send_response(200)
                        self.send_header('Content-Type', 'application/json')
                        self.send_header('Access-Control-Allow-Origin', '*')
                        self.end_headers()
                        self.wfile.write(json.dumps({"status": "synced", "count": len(events)}).encode())
                        
                except Exception as e:
                    print(f"Extension server error: {e}")
                    self.send_response(500)
                    self.end_headers()
            
            def do_OPTIONS(self):
                # Handle CORS preflight
                self.send_response(200)
                self.send_header('Access-Control-Allow-Origin', '*')
                self.send_header('Access-Control-Allow-Methods', 'POST, OPTIONS')
                self.send_header('Access-Control-Allow-Headers', 'Content-Type')
                self.end_headers()
            
            def log_message(self, format, *args):
                # Suppress default logging
                pass
        
        try:
            # Create handler with agent reference
            handler = lambda *args, **kwargs: ExtensionHandler(self, *args, **kwargs)
            self.extension_server = HTTPServer(('localhost', 8001), handler)
            
            # Start server in background thread
            server_thread = threading.Thread(target=self.extension_server.serve_forever)
            server_thread.daemon = True
            server_thread.start()
            
            print(f"[{datetime.now()}] Browser extension server started on http://localhost:8001")
            
        except Exception as e:
            print(f"[{datetime.now()}] Failed to start extension server: {e}")
    
    def handle_browser_event(self, event_data):
        """Handle incoming browser event from extension"""
        try:
            # Add timestamp if not present
            if 'timestamp' not in event_data:
                event_data['timestamp'] = time.time() * 1000
            
            # Store event
            self.browser_events.append(event_data)
            
            # Keep only last 24 hours of events
            cutoff_time = (time.time() - 86400) * 1000  # 24 hours ago in milliseconds
            self.browser_events = [
                event for event in self.browser_events
                if event.get('timestamp', 0) > cutoff_time
            ]
            
            # Update last activity
            self.last_activity_time = time.time()
            
            # Log significant events
            event_type = event_data.get('eventType', 'unknown')
            if event_type in ['tab_activated', 'tab_updated']:
                url = event_data.get('data', {}).get('url', '')
                if url and not url.startswith('chrome://'):
                    print(f"[{datetime.now()}] Browser: {event_type} - {url[:50]}...")
                    
        except Exception as e:
            print(f"Error handling browser event: {e}")
    
    def track_keyboard_mouse_activity(self):
        """Track keyboard and mouse activity"""
        try:
            # Get current idle time
            idle_time = self.get_idle_time()
            
            # Consider active if idle time is less than 30 seconds
            is_active = idle_time < 30
            
            return {
                "timestamp": datetime.now().isoformat(),
                "idle_time_seconds": idle_time,
                "is_active": is_active,
                "activity_type": "keyboard_mouse"
            }
        except Exception as e:
            print(f"Error tracking keyboard/mouse activity: {e}")
            return {
                "timestamp": datetime.now().isoformat(),
                "idle_time_seconds": 0,
                "is_active": False,
                "activity_type": "keyboard_mouse"
            }
    
    def get_active_window_info(self):
        """Get information about the currently active window/application"""
        try:
            system = platform.system()
            
            if system == "Windows":
                # Windows: Use Win32 API
                import ctypes
                from ctypes import wintypes
                
                user32 = ctypes.windll.user32
                
                # Get foreground window
                hwnd = user32.GetForegroundWindow()
                if hwnd:
                    # Get window title
                    length = user32.GetWindowTextLengthW(hwnd)
                    buff = ctypes.create_unicode_buffer(length + 1)
                    user32.GetWindowTextW(hwnd, buff, length + 1)
                    window_title = buff.value
                    
                    # Get process ID and name
                    pid = wintypes.DWORD()
                    user32.GetWindowThreadProcessId(hwnd, ctypes.byref(pid))
                    
                    try:
                        process = psutil.Process(pid.value)
                        app_name = process.name()
                        return {
                            "app_name": app_name,
                            "window_title": window_title,
                            "pid": pid.value
                        }
                    except psutil.NoSuchProcess:
                        return {
                            "app_name": "Unknown",
                            "window_title": window_title,
                            "pid": pid.value
                        }
                        
            elif system == "Darwin":  # macOS
                # macOS: Use AppleScript
                try:
                    script = '''
                    tell application "System Events"
                        set frontApp to first application process whose frontmost is true
                        set appName to name of frontApp
                        try
                            set windowTitle to name of first window of frontApp
                        on error
                            set windowTitle to ""
                        end try
                        return appName & "|" & windowTitle
                    end tell
                    '''
                    result = subprocess.run(['osascript', '-e', script], 
                                          capture_output=True, text=True, timeout=10)
                    if result.returncode == 0:
                        parts = result.stdout.strip().split('|', 1)
                        return {
                            "app_name": parts[0] if parts else "Unknown",
                            "window_title": parts[1] if len(parts) > 1 else "",
                            "pid": 0
                        }
                except (subprocess.CalledProcessError, subprocess.TimeoutExpired):
                    pass
                    
            elif system == "Linux":
                # Linux: Use xdotool or wmctrl
                try:
                    # Try xdotool first
                    result = subprocess.run(['xdotool', 'getactivewindow', 'getwindowname'], 
                                          capture_output=True, text=True, timeout=5)
                    if result.returncode == 0:
                        window_title = result.stdout.strip()
                        
                        # Get process info
                        pid_result = subprocess.run(['xdotool', 'getactivewindow', 'getwindowpid'], 
                                                  capture_output=True, text=True, timeout=5)
                        if pid_result.returncode == 0:
                            try:
                                pid = int(pid_result.stdout.strip())
                                process = psutil.Process(pid)
                                app_name = process.name()
                                return {
                                    "app_name": app_name,
                                    "window_title": window_title,
                                    "pid": pid
                                }
                            except (ValueError, psutil.NoSuchProcess):
                                pass
                        
                        return {
                            "app_name": "Unknown",
                            "window_title": window_title,
                            "pid": 0
                        }
                except (subprocess.CalledProcessError, subprocess.TimeoutExpired, FileNotFoundError):
                    pass
                    
            return {
                "app_name": "Unknown",
                "window_title": "Unknown",
                "pid": 0
            }
            
        except Exception as e:
            print(f"Error getting active window info: {e}")
            return {
                "app_name": "Unknown",
                "window_title": "Unknown", 
                "pid": 0
            }
    
    def track_activity(self):
        """Track user activity and app usage"""
        try:
            current_time = time.time()
            idle_time = self.get_idle_time()
            
            # Consider active if idle time is less than 30 seconds
            is_active = idle_time < 30
            
            # Log activity status
            activity_entry = {
                "timestamp": datetime.now().isoformat(),
                "is_active": is_active,
                "idle_time": idle_time
            }
            
            self.activity_log.append(activity_entry)
            
            # Track app usage if active
            if is_active:
                window_info = self.get_active_window_info()
                app_entry = {
                    "timestamp": datetime.now().isoformat(),
                    "app_name": window_info["app_name"],
                    "window_title": window_info["window_title"],
                    "pid": window_info["pid"]
                }
                self.app_usage_log.append(app_entry)
            
            # Keep only last 24 hours of data
            cutoff_time = datetime.now() - timedelta(hours=24)
            cutoff_iso = cutoff_time.isoformat()
            
            self.activity_log = [
                entry for entry in self.activity_log 
                if entry["timestamp"] > cutoff_iso
            ]
            
            self.app_usage_log = [
                entry for entry in self.app_usage_log 
                if entry["timestamp"] > cutoff_iso
            ]
            
        except Exception as e:
            print(f"Error tracking activity: {e}")
    
    def get_activity_summary(self):
        """Generate comprehensive activity summary for the current day"""
        try:
            today = datetime.now().date()
            today_entries = [
                entry for entry in self.activity_log 
                if datetime.fromisoformat(entry["timestamp"]).date() == today
            ]
            
            if not today_entries:
                return {
                    "total_active_time": 0,
                    "total_idle_time": 0,
                    "activity_rate": 0,
                    "app_usage": {},
                    "websites_visited": [],
                    "screen_lock_events": [],
                    "keyboard_mouse_activity": [],
                    "heartbeat_count": 0
                }
            
            # Calculate active vs idle time
            active_entries = [e for e in today_entries if e["is_active"]]
            total_active_time = len(active_entries) * 60  # 1 minute intervals
            total_time = len(today_entries) * 60
            total_idle_time = total_time - total_active_time
            activity_rate = (total_active_time / total_time * 100) if total_time > 0 else 0
            
            # Calculate app usage
            app_usage = {}
            today_app_entries = [
                entry for entry in self.app_usage_log 
                if datetime.fromisoformat(entry["timestamp"]).date() == today
            ]
            
            for entry in today_app_entries:
                app_name = entry["app_name"]
                if app_name in app_usage:
                    app_usage[app_name] += 1
                else:
                    app_usage[app_name] = 1
            
            # Convert counts to minutes (assuming 1 minute intervals)
            app_usage = {app: count * 1 for app, count in app_usage.items()}
            
            # Get websites visited
            websites = self.get_websites_visited()
            
            # Get screen lock status
            screen_status = self.get_screen_lock_status()
            
            # Get keyboard/mouse activity
            kb_mouse_activity = self.track_keyboard_mouse_activity()
            
            return {
                "total_active_time": total_active_time,
                "total_idle_time": total_idle_time,
                "activity_rate": round(activity_rate, 2),
                "app_usage": app_usage,
                "websites_visited": websites,
                "screen_lock_events": [screen_status],
                "keyboard_mouse_activity": [kb_mouse_activity],
                "heartbeat_count": len(today_entries),
                "last_updated": datetime.now().isoformat()
            }
            
        except Exception as e:
            print(f"Error generating activity summary: {e}")
            return {
                "total_active_time": 0,
                "total_idle_time": 0,
                "activity_rate": 0,
                "app_usage": {},
                "websites_visited": [],
                "screen_lock_events": [],
                "keyboard_mouse_activity": [],
                "heartbeat_count": 0
            }
    
    def get_location(self, public_ip):
        """Get approximate location from IP using multiple services"""
        if public_ip == "unknown" or not self._is_valid_ip(public_ip):
            return json.dumps({
                "ip": "unknown",
                "country": "Unknown",
                "region": "Unknown", 
                "city": "Unknown",
                "provider": "Unknown",
                "error": "Invalid IP address"
            })
            
        # Try multiple location services
        location_services = [
            f'https://ipapi.co/{public_ip}/json/',
            f'https://ipinfo.io/{public_ip}/json',
            f'http://ip-api.com/json/{public_ip}'
        ]
        
        for service_url in location_services:
            try:
                response = requests.get(service_url, timeout=10)
                if response.status_code == 200:
                    data = response.json()
                    
                    # Handle different API response formats
                    if 'ipapi.co' in service_url:
                        return json.dumps({
                            "ip": data.get('ip', public_ip),
                            "country": data.get('country_name', 'Unknown'),
                            "region": data.get('region', 'Unknown'),
                            "city": data.get('city', 'Unknown'),
                            "provider": data.get('org', 'Unknown'),
                            "timezone": data.get('timezone', 'Unknown'),
                            "location": f"{data.get('latitude', '')},{data.get('longitude', '')}"
                        })
                    elif 'ipinfo.io' in service_url:
                        return json.dumps({
                            "ip": data.get('ip', public_ip),
                            "country": data.get('country', 'Unknown'),
                            "region": data.get('region', 'Unknown'),
                            "city": data.get('city', 'Unknown'),
                            "provider": data.get('org', 'Unknown'),
                            "timezone": data.get('timezone', 'Unknown'),
                            "location": data.get('loc', 'Unknown')
                        })
                    elif 'ip-api.com' in service_url:
                        return json.dumps({
                            "ip": data.get('query', public_ip),
                            "country": data.get('country', 'Unknown'),
                            "region": data.get('regionName', 'Unknown'),
                            "city": data.get('city', 'Unknown'),
                            "provider": data.get('isp', 'Unknown'),
                            "timezone": data.get('timezone', 'Unknown'),
                            "location": f"{data.get('lat', '')},{data.get('lon', '')}"
                        })
                        
            except Exception as e:
                print(f"Location service {service_url} failed: {e}")
                continue
        
        # All services failed
        return json.dumps({
            "ip": public_ip,
            "country": "Unknown",
            "region": "Unknown", 
            "city": "Unknown",
            "provider": "Unknown",
            "error": "All location services failed"
        })
    
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
        
        screenshot_file = None
        try:
            print(f"[{datetime.now()}] Sending detailed log...")
            
            # Get network and location info
            local_ip = self.get_local_ip()
            print(f"Local IP: {local_ip}")
            
            public_ip = self.get_public_ip()
            print(f"Public IP: {public_ip}")
            
            location = self.get_location(public_ip)
            print(f"Location data: {location}")
            
            # Take screenshot
            screenshot_file = self.take_screenshot()
            if not screenshot_file:
                print("Failed to take screenshot, sending log without screenshot")
                # Still send the log even without screenshot
                
            # Prepare form data
            if screenshot_file and os.path.exists(screenshot_file):
                files = {
                    'screenshot': open(screenshot_file, 'rb')
                }
            else:
                # Create a dummy file if screenshot failed
                import tempfile
                temp_file = tempfile.NamedTemporaryFile(suffix='.txt', delete=False)
                temp_file.write(b'No screenshot available')
                temp_file.close()
                files = {
                    'screenshot': open(temp_file.name, 'rb')
                }
                screenshot_file = temp_file.name
            
            # Get activity summary
            activity_summary = self.get_activity_summary()
            
            data = {
                'username': self.username,
                'hostname': self.hostname,
                'local_ip': local_ip,
                'public_ip': public_ip,
                'location': location,
                'activity_data': json.dumps(activity_summary)
            }
            
            print(f"Sending data: {data}")
            
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
            
            print(f"Server response: {response.status_code}")
            if response.status_code == 200:
                self.detailed_logs_today += 1
                print(f"[{datetime.now()}] Detailed log sent successfully ({self.detailed_logs_today}/2 today)")
                try:
                    result = response.json()
                    print(f"Server response: {result}")
                except:
                    print(f"Server response text: {response.text}")
            else:
                print(f"[{datetime.now()}] Detailed log failed: {response.status_code}")
                print(f"Error details: {response.text}")
                
        except Exception as e:
            print(f"[{datetime.now()}] Detailed log error: {e}")
            import traceback
            traceback.print_exc()
        finally:
            # Clean up temp file if it exists
            if screenshot_file and os.path.exists(screenshot_file):
                try:
                    os.remove(screenshot_file)
                except:
                    pass
    
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
        
        # Start browser extension server
        self.start_extension_server()
        
        # Schedule heartbeats every 5 minutes
        schedule.every(5).minutes.do(self.send_heartbeat)
        
        # Schedule detailed logs (reschedule daily)
        schedule.every().day.at("00:01").do(self.schedule_detailed_logs)
        
        # Schedule initial detailed logs for today
        self.schedule_detailed_logs()
        
        # Send initial heartbeat
        self.send_heartbeat()
        
        # Send a test detailed log immediately for testing
        print("Sending test detailed log...")
        self.send_detailed_log()
        
        print("Agent started and running in background mode.")
        print("Agent will continue running until process is terminated.")
        print("Activity tracking enabled - monitoring user activity and app usage.")
        print("Browser extension server ready - install the extension to enable detailed web tracking.")
        
        # Main loop - no interactive input required
        try:
            while True:
                schedule.run_pending()
                
                # Track activity every minute
                self.track_activity()
                
                time.sleep(60)  # Check every minute for activity tracking
        except KeyboardInterrupt:
            print("\nAgent stopped by user.")
            if self.extension_server:
                self.extension_server.shutdown()
        except Exception as e:
            print(f"Agent error: {e}")
            # Log error but continue running
            time.sleep(60)  # Wait 1 minute before continuing after error

def main():
    """Main function - configure and start agent"""
    # Configuration - modify these values
    SERVER_URL = "https://bac533f9-caab-40a5-985b-77e95b5b3548-00-26yof333ddv5c.spock.replit.dev"  # Change to your Replit deployment URL
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