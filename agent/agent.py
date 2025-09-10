
#!/usr/bin/env python3
"""
WFH Employee Monitoring Agent - Modular Version with Enhanced ActivityWatch Integration
Improved architecture with configuration management, modular components, and better error handling
"""

import os
import sys
import time
import logging
import schedule
import threading
import getpass
import socket
from datetime import datetime
from pathlib import Path

# Import modular components
from config_manager import ConfigManager
from database_manager import DatabaseManager
from activity_collector import ActivityCollector
from network_manager import NetworkManager
from screenshot_manager import ScreenshotManager

class MonitoringAgent:
    def __init__(self, config_file: str = "config.json"):
        # Initialize components in order
        self.config = ConfigManager(config_file)
        self.setup_logging()
        
        # Get user information
        self.username = getpass.getuser()
        self.hostname = socket.gethostname()
        self.employee_info = self.config.get_employee_info()
        self.is_running = False
        
        # Initialize managers
        self.db = DatabaseManager(self.config)
        self.activity_collector = ActivityCollector(self.config)
        self.network = NetworkManager(self.config, self.db)
        self.screenshot = ScreenshotManager(self.config)
        
        # Get intervals from config
        intervals = self.config.get_section("intervals")
        self.heartbeat_interval = intervals.get("heartbeat_minutes", 5)
        self.activity_interval = intervals.get("activity_collection_minutes", 30)
        self.sync_interval = intervals.get("data_sync_minutes", 10)
        self.scheduler_check = intervals.get("scheduler_check_seconds", 30)
        
        logging.info("WFH Monitoring Agent v2.0 initialized")
        logging.info(f"Server: {self.config.get_server_url()}")
        logging.info(f"User: {self.username}@{self.hostname}")
        logging.info(f"Intervals - Heartbeat: {self.heartbeat_interval}m, "
                    f"Activity: {self.activity_interval}m, Sync: {self.sync_interval}m")
        
    def setup_logging(self):
        """Setup enhanced logging configuration"""
        try:
            log_config = self.config.get_section("logging")
            log_level = getattr(logging, log_config.get("level", "INFO").upper())
            
            # Create logs directory
            log_dir = Path(__file__).parent / "logs"
            log_dir.mkdir(exist_ok=True)
            
            log_file = log_dir / "agent.log"
            
            # Configure logging with rotation
            from logging.handlers import RotatingFileHandler
            
            file_handler = RotatingFileHandler(
                log_file,
                maxBytes=log_config.get("max_file_size_mb", 10) * 1024 * 1024,
                backupCount=log_config.get("backup_count", 5),
                encoding='utf-8'
            )
            
            console_handler = logging.StreamHandler(sys.stdout)
            
            # Enhanced format with more context
            formatter = logging.Formatter(
                '%(asctime)s - %(name)s - %(levelname)s - [%(funcName)s:%(lineno)d] - %(message)s'
            )
            
            file_handler.setFormatter(formatter)
            console_handler.setFormatter(formatter)
            
            # Configure root logger
            root_logger = logging.getLogger()
            root_logger.setLevel(log_level)
            root_logger.addHandler(file_handler)
            root_logger.addHandler(console_handler)
            
            logging.info("Enhanced logging system initialized")
            
        except Exception as e:
            # Fallback to basic logging
            logging.basicConfig(
                level=logging.INFO,
                format='%(asctime)s - %(levelname)s - %(message)s',
                handlers=[
                    logging.FileHandler('agent.log', encoding='utf-8'),
                    logging.StreamHandler(sys.stdout)
                ]
            )
            logging.error(f"Failed to setup enhanced logging, using basic: {e}")
            
    def test_connections(self) -> bool:
        """Test all connections before starting main operations"""
        logging.info("Testing system connections...")
        
        # Test server connection
        server_ok, server_msg = self.network.test_server_connection()
        if server_ok:
            logging.info(f"✓ Server connection: {server_msg}")
        else:
            logging.error(f"✗ Server connection: {server_msg}")
            
        # Test ActivityWatch availability
        aw_available = self.activity_collector.is_activitywatch_available()
        if aw_available:
            logging.info("✓ ActivityWatch integration: Available")
        else:
            logging.warning("⚠ ActivityWatch integration: Not available, using basic monitoring")
            
        # Test database
        try:
            stats = self.db.get_database_stats()
            logging.info(f"✓ Local database: {stats.get('database_size_mb', 0)}MB, "
                        f"{stats.get('heartbeats_unsent', 0)} unsent heartbeats, "
                        f"{stats.get('activity_data_unsent', 0)} unsent activity logs")
        except Exception as e:
            logging.error(f"✗ Database error: {e}")
            return False
            
        # Test screenshot capability
        try:
            test_screenshot = self.screenshot.capture_screenshot(self.username)
            if test_screenshot:
                logging.info("✓ Screenshot capability: Working")
                # Clean up test screenshot
                try:
                    os.remove(test_screenshot)
                except:
                    pass
            else:
                logging.warning("⚠ Screenshot capability: Failed")
        except Exception as e:
            logging.error(f"✗ Screenshot test error: {e}")
            
        return server_ok  # Must have server connection to proceed
        
    def collect_and_store_heartbeat(self):
        """Collect and store heartbeat data"""
        try:
            logging.debug("Collecting heartbeat data...")
            
            record_id = self.db.store_heartbeat(
                username=self.username,
                hostname=self.hostname,
                employee_info=self.employee_info,
                status="online"
            )
            
            if record_id:
                logging.info(f"Heartbeat stored (ID: {record_id})")
            else:
                logging.error("Failed to store heartbeat")
                
        except Exception as e:
            logging.error(f"Heartbeat collection error: {e}")
            
    def collect_and_store_activity(self):
        """Collect comprehensive activity data and store locally"""
        try:
            logging.info("Collecting comprehensive activity data...")
            
            # Get comprehensive activity data from ActivityWatch
            activity_data = self.activity_collector.get_comprehensive_activity_data()
            
            # Capture screenshot
            screenshot_path = self.screenshot.capture_screenshot(self.username)
            
            # Store in database
            record_id = self.db.store_activity_data(
                username=self.username,
                hostname=self.hostname,
                employee_info=self.employee_info,
                source="activitywatch_v2",
                activity_data=activity_data,
                productivity_hours=activity_data.get('total_active_time_minutes', 0) / 60,
                screenshot_path=screenshot_path
            )
            
            if record_id:
                productivity_score = activity_data.get('summary', {}).get('productivity_score', 0)
                active_minutes = activity_data.get('total_active_time_minutes', 0)
                apps_count = activity_data.get('summary', {}).get('apps_used_count', 0)
                websites_count = activity_data.get('summary', {}).get('websites_visited_count', 0)
                
                logging.info(f"Activity data stored (ID: {record_id}) - "
                           f"Productivity: {productivity_score}%, "
                           f"Active: {active_minutes}min, "
                           f"Apps: {apps_count}, Websites: {websites_count}")
                           
                if screenshot_path:
                    screenshot_info = self.screenshot.verify_screenshot_quality(screenshot_path)
                    if screenshot_info.get('valid'):
                        logging.info(f"Screenshot saved: {Path(screenshot_path).name} "
                                   f"({screenshot_info.get('file_size_mb', 0)}MB)")
            else:
                logging.error("Failed to store activity data")
                
        except Exception as e:
            logging.error(f"Activity collection error: {e}")
            
    def synchronize_with_server(self):
        """Synchronize stored data with server"""
        try:
            logging.info("Synchronizing data with server...")
            
            sync_results = self.network.sync_stored_data(self.username, self.hostname)
            
            total_sent = sync_results['heartbeats_sent'] + sync_results['activity_logs_sent']
            total_failed = sync_results['heartbeats_failed'] + sync_results['activity_logs_failed']
            
            if total_sent > 0:
                logging.info(f"Sync completed: {sync_results['heartbeats_sent']} heartbeats, "
                           f"{sync_results['activity_logs_sent']} activity logs sent")
                           
            if total_failed > 0:
                logging.warning(f"Sync issues: {sync_results['heartbeats_failed']} heartbeats, "
                              f"{sync_results['activity_logs_failed']} activity logs failed")
                              
                # Log first few errors for debugging
                for error in sync_results['errors'][:3]:  # Limit to first 3 errors
                    logging.debug(f"Sync error: {error}")
                    
        except Exception as e:
            logging.error(f"Synchronization error: {e}")
            
    def perform_maintenance(self):
        """Perform periodic maintenance tasks"""
        try:
            logging.debug("Performing maintenance tasks...")
            
            # Clean up old data
            self.db.cleanup_old_data()
            
            # Clean up old screenshots
            deleted_screenshots = self.screenshot.cleanup_old_screenshots(
                days=self.config.get("local_storage", "cleanup_days", 7)
            )
            
            if deleted_screenshots > 0:
                logging.info(f"Maintenance: Cleaned up {deleted_screenshots} old screenshots")
                
            # Log storage statistics
            db_stats = self.db.get_database_stats()
            screenshot_stats = self.screenshot.get_storage_stats()
            
            logging.info(f"Storage stats - DB: {db_stats.get('database_size_mb', 0)}MB, "
                        f"Screenshots: {screenshot_stats.get('total_files', 0)} files "
                        f"({screenshot_stats.get('total_size_mb', 0)}MB)")
                        
        except Exception as e:
            logging.error(f"Maintenance error: {e}")
            
    def schedule_tasks(self):
        """Schedule all monitoring tasks with configurable intervals"""
        logging.info("Scheduling monitoring tasks...")
        
        # Schedule heartbeat collection
        schedule.every(self.heartbeat_interval).minutes.do(self.collect_and_store_heartbeat)
        
        # Schedule activity data collection
        schedule.every(self.activity_interval).minutes.do(self.collect_and_store_activity)
        
        # Schedule server synchronization
        schedule.every(self.sync_interval).minutes.do(self.synchronize_with_server)
        
        # Schedule maintenance (daily)
        schedule.every().day.at("02:00").do(self.perform_maintenance)
        
        # Run initial collections
        logging.info("Running initial data collection...")
        self.collect_and_store_heartbeat()
        self.collect_and_store_activity()
        
        logging.info(f"Tasks scheduled successfully - checking every {self.scheduler_check}s")
        
    def run_scheduler(self):
        """Run the task scheduler with proper error handling"""
        logging.info("Starting task scheduler...")
        
        error_count = 0
        max_errors = 5
        
        while self.is_running:
            try:
                schedule.run_pending()
                time.sleep(self.scheduler_check)
                error_count = 0  # Reset error count on successful iteration
                
            except Exception as e:
                error_count += 1
                logging.error(f"Scheduler error ({error_count}/{max_errors}): {e}")
                
                if error_count >= max_errors:
                    logging.critical(f"Too many scheduler errors ({error_count}), stopping agent")
                    self.stop()
                    break
                    
                # Exponential backoff for errors
                sleep_time = min(300, 30 * (2 ** (error_count - 1)))  # Max 5 minutes
                logging.info(f"Retrying in {sleep_time} seconds...")
                time.sleep(sleep_time)
                
        logging.info("Task scheduler stopped")
        
    def start(self):
        """Start the monitoring agent with comprehensive error handling"""
        try:
            self.is_running = True
            logging.info("=" * 60)
            logging.info("Starting WFH Monitoring Agent v2.0...")
            logging.info("=" * 60)
            
            # Test all connections first
            if not self.test_connections():
                logging.error("Critical connection tests failed, cannot start agent")
                return False
                
            # Schedule tasks
            self.schedule_tasks()
            
            # Start scheduler in a separate thread
            scheduler_thread = threading.Thread(target=self.run_scheduler, daemon=True)
            scheduler_thread.start()
            
            logging.info("Agent is running successfully! Press Ctrl+C to stop.")
            logging.info("Monitor the logs for activity updates...")
            
            # Keep main thread alive with periodic status updates
            last_status_update = 0
            status_interval = 3600  # 1 hour
            
            while self.is_running:
                time.sleep(60)  # Check every minute
                
                current_time = time.time()
                if current_time - last_status_update > status_interval:
                    # Log periodic status
                    db_stats = self.db.get_database_stats()
                    logging.info(f"Status update - Unsent: {db_stats.get('heartbeats_unsent', 0)} heartbeats, "
                               f"{db_stats.get('activity_data_unsent', 0)} activity logs")
                    last_status_update = current_time
                    
            return True
                
        except KeyboardInterrupt:
            logging.info("Agent stopped by user (Ctrl+C)")
            self.stop()
            return True
        except Exception as e:
            logging.error(f"Agent startup error: {e}")
            import traceback
            logging.error(traceback.format_exc())
            self.stop()
            return False
            
    def stop(self):
        """Stop the monitoring agent and cleanup resources"""
        logging.info("Stopping WFH Monitoring Agent...")
        
        self.is_running = False
        
        # Cleanup resources
        try:
            if hasattr(self, 'network'):
                self.network.close()
        except Exception as e:
            logging.error(f"Error closing network manager: {e}")
            
        logging.info("Agent stopped successfully")
        logging.info("=" * 60)

if __name__ == "__main__":
    # Configuration
    SERVER_URL = "https://bac533f9-caab-40a5-985b-77e95b5b3548-00-26yof333ddv5c.spock.replit.dev"
    AUTH_TOKEN = "agent-secret-token-change-this-in-production"
    
    # Create and start agent
    agent = MonitoringAgent(SERVER_URL, AUTH_TOKEN)
    agent.start()
