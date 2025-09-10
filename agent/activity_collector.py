#!/usr/bin/env python3
"""
ActivityWatch Data Collector for WFH Monitoring Agent
Handles integration with ActivityWatch and fallback activity monitoring
"""

import json
import logging
import requests
import psutil
from datetime import datetime, timedelta
from typing import Dict, List, Any, Optional, Tuple
import time

class ActivityCollector:
    def __init__(self, config_manager):
        self.config = config_manager
        self.aw_config = config_manager.get_section("activitywatch")
        self.base_url = self.aw_config.get("base_url", "http://localhost:5600")
        self.timeout = self.aw_config.get("timeout", 10)
        self.data_retention_hours = self.aw_config.get("data_retention_hours", 24)
        self.bucket_patterns = self.aw_config.get("bucket_patterns", {})
        
        # Cache for bucket information
        self._bucket_cache = {}
        self._last_bucket_refresh = 0
        self._bucket_cache_ttl = 300  # 5 minutes
        
        logging.info("ActivityCollector initialized")
        
    def is_activitywatch_available(self) -> bool:
        """Check if ActivityWatch is running and accessible"""
        try:
            response = requests.get(f"{self.base_url}/api/0/info", timeout=5)
            available = response.status_code == 200
            if available:
                logging.debug("ActivityWatch is available")
            return available
        except Exception as e:
            logging.debug(f"ActivityWatch not available: {e}")
            return False
            
    def get_available_buckets(self) -> Dict[str, Any]:
        """Get available ActivityWatch buckets with caching"""
        current_time = time.time()
        
        # Use cache if fresh
        if (current_time - self._last_bucket_refresh) < self._bucket_cache_ttl and self._bucket_cache:
            return self._bucket_cache
            
        try:
            response = requests.get(f"{self.base_url}/api/0/buckets", timeout=self.timeout)
            if response.status_code == 200:
                self._bucket_cache = response.json()
                self._last_bucket_refresh = current_time
                logging.debug(f"Retrieved {len(self._bucket_cache)} ActivityWatch buckets")
                return self._bucket_cache
            else:
                logging.warning(f"Failed to get buckets: HTTP {response.status_code}")
                return {}
        except Exception as e:
            logging.error(f"Error fetching ActivityWatch buckets: {e}")
            return {}
            
    def categorize_buckets(self, buckets: Dict[str, Any]) -> Dict[str, List[str]]:
        """Categorize buckets based on patterns"""
        categorized = {"window": [], "web": [], "other": []}
        
        for bucket_id, bucket_info in buckets.items():
            # Skip AFK buckets
            if 'afk' in bucket_id.lower():
                continue
                
            # Categorize based on patterns
            categorized_bucket = False
            for category, patterns in self.bucket_patterns.items():
                if category in categorized and any(pattern in bucket_id.lower() for pattern in patterns):
                    categorized[category].append(bucket_id)
                    categorized_bucket = True
                    break
                    
            if not categorized_bucket:
                categorized["other"].append(bucket_id)
                
        return categorized
        
    def get_events_from_bucket(self, bucket_id: str, start_time: datetime, end_time: datetime) -> List[Dict[str, Any]]:
        """Get events from a specific bucket"""
        try:
            events_url = f"{self.base_url}/api/0/buckets/{bucket_id}/events"
            params = {
                'start': start_time.isoformat(),
                'end': end_time.isoformat(),
                'limit': 1000  # Limit to prevent memory issues
            }
            
            response = requests.get(events_url, params=params, timeout=self.timeout)
            if response.status_code == 200:
                events = response.json()
                logging.debug(f"Retrieved {len(events)} events from bucket {bucket_id}")
                return events
            else:
                logging.warning(f"Failed to get events from {bucket_id}: HTTP {response.status_code}")
                return []
                
        except Exception as e:
            logging.error(f"Error getting events from bucket {bucket_id}: {e}")
            return []
            
    def process_window_events(self, events: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Process window/application events"""
        app_usage = {}
        total_active_time = 0
        keyboard_mouse_events = []
        
        for event in events:
            try:
                duration = event.get('duration', 0)
                total_active_time += duration
                
                # Extract application information
                data = event.get('data', {})
                app_name = data.get('app', 'Unknown')
                title = data.get('title', '')
                
                # Aggregate app usage time
                if app_name not in app_usage:
                    app_usage[app_name] = 0
                app_usage[app_name] += duration
                
                # Create keyboard/mouse event records
                keyboard_mouse_events.append({
                    'timestamp': event.get('timestamp'),
                    'duration': duration,
                    'app': app_name,
                    'title': title,
                    'is_active': duration > 0
                })
                
            except Exception as e:
                logging.debug(f"Error processing window event: {e}")
                continue
                
        # Convert seconds to minutes for app usage
        app_usage_minutes = {app: int(time_seconds / 60) for app, time_seconds in app_usage.items()}
        
        return {
            'app_usage_minutes': app_usage_minutes,
            'total_active_seconds': total_active_time,
            'keyboard_mouse_events': keyboard_mouse_events
        }
        
    def process_web_events(self, events: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Process web/browser events"""
        website_usage = {}
        browser_events_count = 0
        
        for event in events:
            try:
                duration = event.get('duration', 0)
                data = event.get('data', {})
                url = data.get('url', '')
                title = data.get('title', '')
                
                browser_events_count += 1
                
                # Extract domain from URL
                if url:
                    try:
                        from urllib.parse import urlparse
                        domain = urlparse(url).netloc
                        if domain:
                            if domain not in website_usage:
                                website_usage[domain] = 0
                            website_usage[domain] += 1  # Count visits rather than time
                    except Exception:
                        pass
                        
            except Exception as e:
                logging.debug(f"Error processing web event: {e}")
                continue
                
        return {
            'website_usage_counts': website_usage,
            'browser_events_count': browser_events_count
        }
        
    def get_comprehensive_activity_data(self) -> Dict[str, Any]:
        """Get comprehensive activity data from ActivityWatch"""
        if not self.is_activitywatch_available():
            logging.info("ActivityWatch not available, using basic monitoring")
            return self.get_basic_activity_data()
            
        # Define time range (last hour by default)
        end_time = datetime.now()
        start_time = end_time - timedelta(hours=1)
        
        # Get and categorize buckets
        buckets = self.get_available_buckets()
        if not buckets:
            return self.get_basic_activity_data()
            
        categorized_buckets = self.categorize_buckets(buckets)
        
        # Collect data from different bucket types
        window_data = []
        web_data = []
        
        # Process window/app buckets
        for bucket_id in categorized_buckets.get("window", []):
            events = self.get_events_from_bucket(bucket_id, start_time, end_time)
            window_data.extend(events)
            
        # Process web/browser buckets
        for bucket_id in categorized_buckets.get("web", []):
            events = self.get_events_from_bucket(bucket_id, start_time, end_time)
            web_data.extend(events)
            
        # Process collected data
        window_analysis = self.process_window_events(window_data)
        web_analysis = self.process_web_events(web_data)
        
        # Calculate summary metrics
        total_active_minutes = int(window_analysis['total_active_seconds'] / 60)
        total_tracked_minutes = 60  # We track last hour
        activity_rate = min(100, int((total_active_minutes / total_tracked_minutes) * 100)) if total_tracked_minutes > 0 else 0
        
        # Calculate productivity score (simple heuristic)
        apps_used = len(window_analysis['app_usage_minutes'])
        websites_visited = len(web_analysis['website_usage_counts'])
        productivity_score = min(100, int((activity_rate * 0.7) + (min(apps_used, 10) * 2) + (min(websites_visited, 10) * 1)))
        
        comprehensive_data = {
            'date': end_time.date().isoformat(),
            'timestamp': end_time.isoformat(),
            'activitywatch_available': True,
            'total_active_time_minutes': total_active_minutes,
            'total_tracked_time_minutes': total_tracked_minutes,
            'activity_rate_percentage': activity_rate,
            'our_app_usage_minutes': window_analysis['app_usage_minutes'],
            'browser_activity_counts': web_analysis['website_usage_counts'],
            'browser_events_total': web_analysis['browser_events_count'],
            'keyboard_mouse_events': window_analysis['keyboard_mouse_events'],
            'summary': {
                'productivity_score': productivity_score,
                'apps_used_count': apps_used,
                'websites_visited_count': websites_visited
            },
            'activitywatch_data': {
                'window_events_count': len(window_data),
                'web_events_count': len(web_data),
                'data_collection_time': end_time.isoformat(),
                'time_range_hours': 1
            }
        }
        
        logging.info(f"ActivityWatch data collected: {total_active_minutes}min active, {apps_used} apps, {websites_visited} websites")
        return comprehensive_data
        
    def get_basic_activity_data(self) -> Dict[str, Any]:
        """Fallback basic activity monitoring when ActivityWatch is not available"""
        try:
            current_time = datetime.now()
            
            # Get basic system metrics
            cpu_percent = psutil.cpu_percent(interval=1)
            memory_percent = psutil.virtual_memory().percent
            active_processes = len(psutil.pids())
            
            # Simple activity estimation based on system metrics
            estimated_activity_rate = min(100, int(cpu_percent + (memory_percent * 0.3)))
            estimated_active_minutes = int(estimated_activity_rate * 0.6)  # Conservative estimate
            
            basic_data = {
                'date': current_time.date().isoformat(),
                'timestamp': current_time.isoformat(),
                'activitywatch_available': False,
                'total_active_time_minutes': estimated_active_minutes,
                'total_tracked_time_minutes': 60,
                'activity_rate_percentage': estimated_activity_rate,
                'our_app_usage_minutes': {'system_monitor': estimated_active_minutes},
                'browser_activity_counts': {},
                'browser_events_total': 0,
                'keyboard_mouse_events': [],
                'summary': {
                    'productivity_score': min(80, estimated_activity_rate),  # Cap at 80 for basic monitoring
                    'apps_used_count': 1,
                    'websites_visited_count': 0
                },
                'system_metrics': {
                    'cpu_percent': cpu_percent,
                    'memory_percent': memory_percent,
                    'active_processes': active_processes
                }
            }
            
            logging.info(f"Basic activity data collected: {estimated_active_minutes}min estimated active time")
            return basic_data
            
        except Exception as e:
            logging.error(f"Basic activity data collection error: {e}")
            current_time = datetime.now()
            return {
                'date': current_time.date().isoformat(),
                'timestamp': current_time.isoformat(),
                'activitywatch_available': False,
                'total_active_time_minutes': 30,  # Safe fallback
                'total_tracked_time_minutes': 60,
                'activity_rate_percentage': 50,
                'our_app_usage_minutes': {'unknown': 30},
                'browser_activity_counts': {},
                'browser_events_total': 0,
                'keyboard_mouse_events': [],
                'summary': {
                    'productivity_score': 50,
                    'apps_used_count': 1,
                    'websites_visited_count': 0
                },
                'error': str(e)
            }