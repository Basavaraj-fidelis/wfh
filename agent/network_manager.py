#!/usr/bin/env python3
"""
Network Manager for WFH Monitoring Agent
Handles server communication with retry logic and proper error handling
"""

import requests
import logging
import time
import socket
from datetime import datetime
from typing import Dict, Any, Optional, Tuple
import json
from urllib.parse import urljoin

class NetworkManager:
    def __init__(self, config_manager, database_manager):
        self.config = config_manager
        self.db = database_manager
        self.server_config = config_manager.get_section("server")
        
        self.server_url = config_manager.get_server_url()
        self.auth_token = config_manager.get_auth_token()
        self.timeout = self.server_config.get("timeout", 30)
        self.retry_attempts = self.server_config.get("retry_attempts", 3)
        self.retry_delay = self.server_config.get("retry_delay", 5)
        
        # Session for connection reuse
        self.session = requests.Session()
        self.session.headers.update({
            'Authorization': f'Bearer {self.auth_token}',
            'User-Agent': 'WFH-Agent/2.0'
        })
        
        logging.info(f"NetworkManager initialized for server: {self.server_url}")
        
    def _get_location_data(self) -> Dict[str, Any]:
        """Get current location/network information"""
        try:
            # Get local IP
            s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            s.connect(("8.8.8.8", 80))
            local_ip = s.getsockname()[0]
            s.close()
            
            # Try to get public IP and location
            try:
                response = requests.get('https://ipinfo.io/json', timeout=10)
                if response.status_code == 200:
                    location_info = response.json()
                    return {
                        'local_ip': local_ip,
                        'public_ip': location_info.get('ip', 'unknown'),
                        'city': location_info.get('city', 'unknown'),
                        'region': location_info.get('region', 'unknown'),
                        'country': location_info.get('country', 'unknown'),
                        'location': location_info.get('loc', 'unknown'),
                        'org': location_info.get('org', 'unknown'),
                        'hostname': socket.gethostname()
                    }
            except Exception as e:
                logging.debug(f"Public IP lookup failed: {e}")
                
            return {
                'local_ip': local_ip,
                'public_ip': 'unknown',
                'hostname': socket.gethostname()
            }
            
        except Exception as e:
            logging.error(f"Location data error: {e}")
            return {
                'local_ip': 'unknown',
                'public_ip': 'unknown',
                'hostname': socket.gethostname()
            }
            
    def test_server_connection(self) -> Tuple[bool, str]:
        """Test connection to server and validate authentication"""
        try:
            # Test basic connectivity
            test_url = urljoin(self.server_url, '/api/heartbeat')
            
            test_data = {
                'username': 'test',
                'hostname': 'test',
                'status': 'test'
            }
            
            response = self.session.post(test_url, json=test_data, timeout=self.timeout)
            
            if response.status_code == 200:
                return True, "Server connection successful"
            elif response.status_code == 401:
                return False, "Authentication failed - invalid token"
            elif response.status_code == 403:
                return False, "Access forbidden - check permissions"
            else:
                return False, f"Server returned HTTP {response.status_code}"
                
        except requests.exceptions.ConnectionError:
            return False, "Cannot connect to server - check URL and network"
        except requests.exceptions.Timeout:
            return False, "Server connection timeout"
        except Exception as e:
            return False, f"Connection test failed: {str(e)}"
            
    def send_heartbeat(self, username: str, hostname: str, employee_info: Dict[str, str], 
                      status: str = "online") -> Tuple[bool, str]:
        """Send heartbeat to server with retry logic"""
        heartbeat_data = {
            'username': username,
            'hostname': hostname,
            'employee_id': employee_info.get('employee_id', ''),
            'employee_email': employee_info.get('employee_email', ''),
            'employee_name': employee_info.get('employee_name', ''),
            'department': employee_info.get('department', ''),
            'manager': employee_info.get('manager', ''),
            'status': status
        }
        
        return self._send_with_retry(
            endpoint='/api/heartbeat',
            data=heartbeat_data,
            method='POST'
        )
        
    def send_detailed_log(self, username: str, hostname: str, employee_info: Dict[str, str],
                         activity_data: Dict[str, Any], screenshot_path: Optional[str] = None) -> Tuple[bool, str]:
        """Send detailed activity log to server with screenshot"""
        try:
            location_data = self._get_location_data()
            
            # Prepare form data
            form_data = {
                'username': username,
                'hostname': hostname,
                'employee_id': employee_info.get('employee_id', ''),
                'employee_email': employee_info.get('employee_email', ''),
                'employee_name': employee_info.get('employee_name', ''),
                'department': employee_info.get('department', ''),
                'manager': employee_info.get('manager', ''),
                'local_ip': location_data.get('local_ip', 'unknown'),
                'public_ip': location_data.get('public_ip', 'unknown'),
                'location': json.dumps(location_data),
                'activity_data': json.dumps(activity_data)
            }
            
            # Prepare files
            files = {}
            if screenshot_path:
                try:
                    files['screenshot'] = open(screenshot_path, 'rb')
                except Exception as e:
                    logging.error(f"Failed to open screenshot file {screenshot_path}: {e}")
                    screenshot_path = None
            
            try:
                success, message = self._send_multipart_with_retry(
                    endpoint='/api/log',
                    data=form_data,
                    files=files
                )
                return success, message
                
            finally:
                # Ensure file is closed
                if 'screenshot' in files:
                    files['screenshot'].close()
                    
        except Exception as e:
            error_msg = f"Error preparing detailed log: {e}"
            logging.error(error_msg)
            return False, error_msg
            
    def _send_with_retry(self, endpoint: str, data: Dict[str, Any], 
                        method: str = 'POST') -> Tuple[bool, str]:
        """Send JSON data with retry logic"""
        url = urljoin(self.server_url, endpoint)
        
        for attempt in range(self.retry_attempts):
            try:
                if method.upper() == 'POST':
                    response = self.session.post(url, json=data, timeout=self.timeout)
                elif method.upper() == 'PUT':
                    response = self.session.put(url, json=data, timeout=self.timeout)
                else:
                    return False, f"Unsupported HTTP method: {method}"
                
                if response.status_code == 200:
                    logging.debug(f"Successfully sent to {endpoint}")
                    return True, "Success"
                elif response.status_code in [401, 403]:
                    # Don't retry authentication errors
                    error_msg = f"Authentication error: HTTP {response.status_code}"
                    logging.error(error_msg)
                    return False, error_msg
                else:
                    error_msg = f"Server error: HTTP {response.status_code}"
                    if attempt < self.retry_attempts - 1:
                        logging.warning(f"{error_msg}, retrying in {self.retry_delay}s...")
                        time.sleep(self.retry_delay)
                        continue
                    else:
                        logging.error(error_msg)
                        return False, error_msg
                        
            except requests.exceptions.ConnectionError as e:
                error_msg = f"Connection error: {e}"
                if attempt < self.retry_attempts - 1:
                    logging.warning(f"{error_msg}, retrying in {self.retry_delay}s...")
                    time.sleep(self.retry_delay)
                    continue
                else:
                    logging.error(error_msg)
                    return False, error_msg
                    
            except requests.exceptions.Timeout as e:
                error_msg = f"Timeout error: {e}"
                if attempt < self.retry_attempts - 1:
                    logging.warning(f"{error_msg}, retrying in {self.retry_delay}s...")
                    time.sleep(self.retry_delay)
                    continue
                else:
                    logging.error(error_msg)
                    return False, error_msg
                    
            except Exception as e:
                error_msg = f"Unexpected error: {e}"
                logging.error(error_msg)
                return False, error_msg
                
        return False, "Max retry attempts exceeded"
        
    def _send_multipart_with_retry(self, endpoint: str, data: Dict[str, Any], 
                                  files: Dict[str, Any]) -> Tuple[bool, str]:
        """Send multipart data with retry logic"""
        url = urljoin(self.server_url, endpoint)
        
        for attempt in range(self.retry_attempts):
            try:
                # Reset file pointer if retrying
                if attempt > 0 and 'screenshot' in files:
                    files['screenshot'].seek(0)
                
                response = self.session.post(
                    url, 
                    data=data, 
                    files=files, 
                    timeout=self.timeout * 2  # Longer timeout for file uploads
                )
                
                if response.status_code == 200:
                    logging.debug(f"Successfully sent multipart data to {endpoint}")
                    return True, "Success"
                elif response.status_code in [401, 403]:
                    # Don't retry authentication errors
                    error_msg = f"Authentication error: HTTP {response.status_code}"
                    logging.error(error_msg)
                    return False, error_msg
                else:
                    error_msg = f"Server error: HTTP {response.status_code}"
                    if attempt < self.retry_attempts - 1:
                        logging.warning(f"{error_msg}, retrying in {self.retry_delay}s...")
                        time.sleep(self.retry_delay)
                        continue
                    else:
                        logging.error(error_msg)
                        return False, error_msg
                        
            except requests.exceptions.ConnectionError as e:
                error_msg = f"Connection error: {e}"
                if attempt < self.retry_attempts - 1:
                    logging.warning(f"{error_msg}, retrying in {self.retry_delay}s...")
                    time.sleep(self.retry_delay)
                    continue
                else:
                    logging.error(error_msg)
                    return False, error_msg
                    
            except requests.exceptions.Timeout as e:
                error_msg = f"Timeout error: {e}"
                if attempt < self.retry_attempts - 1:
                    logging.warning(f"{error_msg}, retrying in {self.retry_delay}s...")
                    time.sleep(self.retry_delay)
                    continue
                else:
                    logging.error(error_msg)
                    return False, error_msg
                    
            except Exception as e:
                error_msg = f"Unexpected error during multipart upload: {e}"
                logging.error(error_msg)
                return False, error_msg
                
        return False, "Max retry attempts exceeded"
        
    def sync_stored_data(self, username: str, hostname: str) -> Dict[str, Any]:
        """Synchronize all stored data with server"""
        sync_results = {
            'heartbeats_sent': 0,
            'activity_logs_sent': 0,
            'heartbeats_failed': 0,
            'activity_logs_failed': 0,
            'errors': []
        }
        
        try:
            # Sync heartbeats
            heartbeats = self.db.get_unsent_heartbeats()
            for heartbeat in heartbeats:
                (hb_id, timestamp, hb_username, hb_hostname, employee_id, employee_email, 
                 employee_name, department, manager, status, location_data) = heartbeat
                
                employee_info = {
                    'employee_id': employee_id or '',
                    'employee_email': employee_email or '',
                    'employee_name': employee_name or '',
                    'department': department or '',
                    'manager': manager or ''
                }
                
                success, message = self.send_heartbeat(hb_username, hb_hostname, employee_info, status)
                
                if success:
                    self.db.mark_as_sent('heartbeats', hb_id)
                    sync_results['heartbeats_sent'] += 1
                else:
                    self.db.record_sync_attempt('heartbeats', hb_id, message)
                    sync_results['heartbeats_failed'] += 1
                    sync_results['errors'].append(f"Heartbeat {hb_id}: {message}")
                    
            # Sync activity data
            activity_logs = self.db.get_unsent_activity_data()
            for activity_log in activity_logs:
                (log_id, timestamp, act_username, act_hostname, employee_id, employee_email, 
                 employee_name, department, manager, source, activity_data_str, 
                 productivity_hours, screenshot_path, location_data) = activity_log
                
                employee_info = {
                    'employee_id': employee_id or '',
                    'employee_email': employee_email or '',
                    'employee_name': employee_name or '',
                    'department': department or '',
                    'manager': manager or ''
                }
                
                try:
                    activity_data = json.loads(activity_data_str)
                except json.JSONDecodeError as e:
                    error_msg = f"Invalid activity data JSON: {e}"
                    self.db.record_sync_attempt('activity_data', log_id, error_msg)
                    sync_results['activity_logs_failed'] += 1
                    sync_results['errors'].append(f"Activity log {log_id}: {error_msg}")
                    continue
                
                success, message = self.send_detailed_log(
                    act_username, act_hostname, employee_info, activity_data, screenshot_path
                )
                
                if success:
                    self.db.mark_as_sent('activity_data', log_id)
                    sync_results['activity_logs_sent'] += 1
                else:
                    self.db.record_sync_attempt('activity_data', log_id, message)
                    sync_results['activity_logs_failed'] += 1
                    sync_results['errors'].append(f"Activity log {log_id}: {message}")
                    
            logging.info(f"Sync completed: {sync_results['heartbeats_sent']} heartbeats, "
                        f"{sync_results['activity_logs_sent']} activity logs sent")
                        
            return sync_results
            
        except Exception as e:
            error_msg = f"Sync process error: {e}"
            logging.error(error_msg)
            sync_results['errors'].append(error_msg)
            return sync_results
            
    def close(self):
        """Clean up network resources"""
        if hasattr(self, 'session'):
            self.session.close()
            logging.debug("Network session closed")