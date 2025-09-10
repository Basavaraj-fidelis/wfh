
#!/usr/bin/env python3
"""
WFH Employee Monitoring Agent - ActivityWatch Integration Version
Integrates with ActivityWatch for detailed activity tracking
"""

import os
import sys
import time
import json
import sqlite3
import logging
import requests
import schedule
import threading
from datetime import datetime, timedelta
from PIL import ImageGrab
import socket
import getpass
import random

class MonitoringAgent:
    def __init__(self, server_url, auth_token):
        self.server_url = server_url.rstrip('/')
        self.auth_token = auth_token
        self.username = getpass.getuser()
        self.hostname = socket.gethostname()
        self.is_running = False
        
        # Setup logging
        self.setup_logging()
        
        # Setup local database for data storage
        self.setup_database()
        
        logging.info("WFH Monitoring Agent initialized")
        logging.info(f"Server: {self.server_url}")
        logging.info(f"User: {self.username}@{self.hostname}")

    def setup_logging(self):
        """Setup logging configuration"""
        log_file = os.path.join(os.path.dirname(__file__), 'agent.log')
        
        logging.basicConfig(
            level=logging.INFO,
            format='%(asctime)s - %(levelname)s - %(message)s',
            handlers=[
                logging.FileHandler(log_file, encoding='utf-8'),
                logging.StreamHandler(sys.stdout)
            ]
        )

    def setup_database(self):
        """Setup local SQLite database for storing monitoring data"""
        try:
            db_path = os.path.join(os.path.dirname(__file__), 'agent_data.db')
            self.conn = sqlite3.connect(db_path, check_same_thread=False)
            self.conn.execute('PRAGMA foreign_keys = ON')
            
            # Create tables
            self.conn.execute('''
                CREATE TABLE IF NOT EXISTS heartbeats (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    timestamp TEXT NOT NULL,
                    status TEXT NOT NULL,
                    location_data TEXT,
                    sent_to_server BOOLEAN DEFAULT FALSE
                )
            ''')
            
            self.conn.execute('''
                CREATE TABLE IF NOT EXISTS activity_data (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    timestamp TEXT NOT NULL,
                    source TEXT NOT NULL,
                    activity_data TEXT NOT NULL,
                    productivity_hours REAL DEFAULT 0,
                    screenshot_path TEXT,
                    sent_to_server BOOLEAN DEFAULT FALSE
                )
            ''')
            
            self.conn.execute('''
                CREATE TABLE IF NOT EXISTS web_activity (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    timestamp TEXT NOT NULL,
                    url TEXT,
                    title TEXT,
                    duration INTEGER DEFAULT 0,
                    sent_to_server BOOLEAN DEFAULT FALSE
                )
            ''')
            
            self.conn.commit()
            logging.info("Local database setup complete")
            
        except Exception as e:
            logging.error(f"Database setup error: {e}")

    def get_location_data(self):
        """Get basic location/network information"""
        try:
            # Get local IP
            s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            s.connect(("8.8.8.8", 80))
            local_ip = s.getsockname()[0]
            s.close()
            
            # Try to get public IP
            try:
                response = requests.get('https://api.ipify.org?format=json', timeout=5)
                public_ip = response.json().get('ip', 'unknown')
            except:
                public_ip = 'unknown'
            
            return {
                'local_ip': local_ip,
                'public_ip': public_ip,
                'hostname': self.hostname
            }
        except Exception as e:
            logging.error(f"Location data error: {e}")
            return {'local_ip': 'unknown', 'public_ip': 'unknown', 'hostname': self.hostname}

    def capture_screenshot(self):
        """Capture desktop screenshot"""
        try:
            screenshots_dir = os.path.join(os.path.dirname(__file__), 'screenshots')
            os.makedirs(screenshots_dir, exist_ok=True)
            
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"{self.username}_{timestamp}.png"
            filepath = os.path.join(screenshots_dir, filename)
            
            screenshot = ImageGrab.grab()
            screenshot.save(filepath, 'PNG')
            
            logging.info(f"Screenshot captured: {filename}")
            return filepath
            
        except Exception as e:
            logging.error(f"Screenshot capture error: {e}")
            return None

    def get_activitywatch_data(self):
        """Get activity data from ActivityWatch"""
        try:
            # ActivityWatch typically runs on localhost:5600
            aw_base_url = "http://localhost:5600"
            
            # Get available buckets
            buckets_response = requests.get(f"{aw_base_url}/api/0/buckets", timeout=10)
            if buckets_response.status_code != 200:
                logging.warning("ActivityWatch not available - falling back to basic monitoring")
                return self.get_basic_activity_data()
            
            buckets = buckets_response.json()
            
            # Get data from last hour
            end_time = datetime.now()
            start_time = end_time - timedelta(hours=1)
            
            activity_data = {
                'timestamp': end_time.isoformat(),
                'window_data': [],
                'web_data': [],
                'productivity_hours': 0
            }
            
            # Get window activity data
            for bucket_id, bucket_info in buckets.items():
                if 'afk' in bucket_id.lower():
                    continue
                    
                try:
                    events_url = f"{aw_base_url}/api/0/buckets/{bucket_id}/events"
                    params = {
                        'start': start_time.isoformat(),
                        'end': end_time.isoformat()
                    }
                    
                    events_response = requests.get(events_url, params=params, timeout=5)
                    if events_response.status_code == 200:
                        events = events_response.json()
                        
                        if 'window' in bucket_id.lower():
                            activity_data['window_data'].extend(events)
                        elif 'web' in bucket_id.lower() or 'browser' in bucket_id.lower():
                            activity_data['web_data'].extend(events)
                            
                except Exception as e:
                    logging.error(f"Error getting events from bucket {bucket_id}: {e}")
            
            # Calculate productivity hours (simple estimation)
            total_active_time = 0
            for event in activity_data['window_data']:
                if 'duration' in event:
                    total_active_time += event['duration']
            
            activity_data['productivity_hours'] = total_active_time / 3600  # Convert to hours
            
            logging.info(f"ActivityWatch data collected: {len(activity_data['window_data'])} window events, {len(activity_data['web_data'])} web events")
            return activity_data
            
        except Exception as e:
            logging.error(f"ActivityWatch data collection error: {e}")
            return self.get_basic_activity_data()

    def get_basic_activity_data(self):
        """Fallback basic activity monitoring when ActivityWatch is not available"""
        try:
            import psutil
            
            # Get basic system info
            activity_data = {
                'timestamp': datetime.now().isoformat(),
                'cpu_percent': psutil.cpu_percent(interval=1),
                'memory_percent': psutil.virtual_memory().percent,
                'active_processes': len(psutil.pids()),
                'productivity_hours': 1.0  # Assume 1 hour of activity as basic fallback
            }
            
            logging.info("Basic activity data collected (ActivityWatch not available)")
            return activity_data
            
        except Exception as e:
            logging.error(f"Basic activity data error: {e}")
            return {
                'timestamp': datetime.now().isoformat(),
                'error': str(e),
                'productivity_hours': 0.5
            }

    def store_heartbeat(self):
        """Store heartbeat data locally"""
        try:
            location_data = self.get_location_data()
            timestamp = datetime.now().isoformat()
            
            self.conn.execute('''
                INSERT INTO heartbeats (timestamp, status, location_data, sent_to_server)
                VALUES (?, ?, ?, ?)
            ''', (timestamp, 'online', json.dumps(location_data), False))
            
            self.conn.commit()
            logging.info("Heartbeat stored locally")
            
        except Exception as e:
            logging.error(f"Store heartbeat error: {e}")

    def store_activity_data(self):
        """Store detailed activity data locally"""
        try:
            # Get activity data from ActivityWatch
            activity_data = self.get_activitywatch_data()
            
            # Capture screenshot
            screenshot_path = self.capture_screenshot()
            
            # Store in local database
            timestamp = datetime.now().isoformat()
            self.conn.execute('''
                INSERT INTO activity_data (timestamp, source, activity_data, productivity_hours, screenshot_path, sent_to_server)
                VALUES (?, ?, ?, ?, ?, ?)
            ''', (timestamp, 'activitywatch', json.dumps(activity_data), activity_data.get('productivity_hours', 0), screenshot_path, False))
            
            self.conn.commit()
            logging.info(f"Activity data stored locally (Productivity: {activity_data.get('productivity_hours', 0):.2f} hours)")
            
        except Exception as e:
            logging.error(f"Store activity data error: {e}")

    def send_data_to_server(self):
        """Send stored data to server"""
        try:
            headers = {'Authorization': f'Bearer {self.auth_token}'}
            
            # Send unsent heartbeats
            cursor = self.conn.execute('SELECT * FROM heartbeats WHERE sent_to_server = FALSE ORDER BY timestamp')
            heartbeats = cursor.fetchall()
            
            for heartbeat in heartbeats:
                hb_id, timestamp, status, location_data, _ = heartbeat
                
                data = {
                    'username': self.username,
                    'hostname': self.hostname,
                    'status': status,
                    'timestamp': timestamp,
                    'location_data': json.loads(location_data) if location_data else {}
                }
                
                try:
                    response = requests.post(f"{self.server_url}/api/heartbeat", json=data, headers=headers, timeout=30)
                    if response.status_code == 200:
                        self.conn.execute('UPDATE heartbeats SET sent_to_server = TRUE WHERE id = ?', (hb_id,))
                        logging.info(f"Heartbeat sent successfully: {response.status_code}")
                    else:
                        logging.error(f"Heartbeat failed: {response.status_code}")
                except Exception as e:
                    logging.error(f"Heartbeat send error: {e}")
            
            # Send unsent activity data
            cursor = self.conn.execute('SELECT * FROM activity_data WHERE sent_to_server = FALSE ORDER BY timestamp')
            activity_logs = cursor.fetchall()
            
            for activity_log in activity_logs:
                log_id, timestamp, source, activity_data_str, productivity_hours, screenshot_path, _ = activity_log
                
                files = {}
                if screenshot_path and os.path.exists(screenshot_path):
                    files['screenshot'] = open(screenshot_path, 'rb')
                
                data = {
                    'username': self.username,
                    'hostname': self.hostname,
                    'timestamp': timestamp,
                    'source': source,
                    'activity_data': activity_data_str,
                    'productivity_hours': str(productivity_hours),
                    'location_data': json.dumps(self.get_location_data())
                }
                
                try:
                    response = requests.post(f"{self.server_url}/api/log", data=data, files=files, headers=headers, timeout=60)
                    
                    if files:
                        files['screenshot'].close()
                    
                    if response.status_code == 200:
                        self.conn.execute('UPDATE activity_data SET sent_to_server = TRUE WHERE id = ?', (log_id,))
                        logging.info(f"Activity log sent successfully: {response.status_code}")
                    else:
                        logging.error(f"Activity log failed: {response.status_code}")
                        
                except Exception as e:
                    logging.error(f"Activity log send error: {e}")
                    if files and 'screenshot' in files:
                        files['screenshot'].close()
            
            self.conn.commit()
            
        except Exception as e:
            logging.error(f"Send data to server error: {e}")

    def schedule_tasks(self):
        """Schedule all monitoring tasks"""
        # Heartbeat every 5 minutes
        schedule.every(5).minutes.do(self.store_heartbeat)
        
        # Activity data collection every 30 minutes
        schedule.every(30).minutes.do(self.store_activity_data)
        
        # Send data to server every 10 minutes
        schedule.every(10).minutes.do(self.send_data_to_server)
        
        # Initial data collection
        self.store_heartbeat()
        self.store_activity_data()

    def run_scheduler(self):
        """Run the task scheduler"""
        while self.is_running:
            try:
                schedule.run_pending()
                time.sleep(30)  # Check every 30 seconds
            except Exception as e:
                logging.error(f"Scheduler error: {e}")
                time.sleep(60)

    def start(self):
        """Start the monitoring agent"""
        try:
            self.is_running = True
            logging.info("Starting WFH Monitoring Agent...")
            
            # Schedule tasks
            self.schedule_tasks()
            
            # Start scheduler in a separate thread
            scheduler_thread = threading.Thread(target=self.run_scheduler, daemon=True)
            scheduler_thread.start()
            
            logging.info("Agent is running. Press Ctrl+C to stop.")
            
            # Keep main thread alive
            while self.is_running:
                time.sleep(1)
                
        except KeyboardInterrupt:
            logging.info("Agent stopped by user")
            self.stop()
        except Exception as e:
            logging.error(f"Agent error: {e}")
            self.stop()

    def stop(self):
        """Stop the monitoring agent"""
        self.is_running = False
        if hasattr(self, 'conn'):
            self.conn.close()
        logging.info("Agent stopped")

if __name__ == "__main__":
    # Configuration
    SERVER_URL = "https://bac533f9-caab-40a5-985b-77e95b5b3548-00-26yof333ddv5c.spock.replit.dev"
    AUTH_TOKEN = "agent-secret-token-change-this-in-production"
    
    # Create and start agent
    agent = MonitoringAgent(SERVER_URL, AUTH_TOKEN)
    agent.start()
