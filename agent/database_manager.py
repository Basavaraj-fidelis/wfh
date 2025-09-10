#!/usr/bin/env python3
"""
Database Manager for WFH Monitoring Agent
Handles local SQLite database operations with proper resource management
"""

import sqlite3
import json
import logging
import threading
from datetime import datetime, timedelta
from typing import Dict, List, Any, Optional, Tuple
from pathlib import Path
import time

class DatabaseManager:
    def __init__(self, config_manager):
        self.config = config_manager
        self.db_config = config_manager.get_section("local_storage")
        self.db_name = self.db_config.get("database_name", "agent_data.db")
        self.cleanup_days = self.db_config.get("cleanup_days", 7)
        
        self.db_path = Path(__file__).parent / self.db_name
        self._lock = threading.Lock()
        
        # Initialize database
        self._initialize_database()
        
        logging.info(f"DatabaseManager initialized with database: {self.db_path}")
        
    def _get_connection(self) -> sqlite3.Connection:
        """Get a new database connection with proper configuration"""
        conn = sqlite3.connect(
            self.db_path,
            timeout=20.0,
            isolation_level=None  # Use autocommit mode
        )
        conn.execute('PRAGMA foreign_keys = ON')
        conn.execute('PRAGMA journal_mode = WAL')  # Better for concurrent access
        conn.execute('PRAGMA synchronous = NORMAL')  # Balance between safety and performance
        return conn
        
    def _initialize_database(self):
        """Initialize database schema with proper indexes"""
        try:
            with self._lock:
                conn = self._get_connection()
                try:
                    # Create tables with improved schema
                    conn.executescript('''
                        CREATE TABLE IF NOT EXISTS heartbeats (
                            id INTEGER PRIMARY KEY AUTOINCREMENT,
                            timestamp TEXT NOT NULL,
                            username TEXT NOT NULL,
                            hostname TEXT NOT NULL,
                            status TEXT NOT NULL DEFAULT 'online',
                            location_data TEXT,
                            sent_to_server BOOLEAN DEFAULT FALSE,
                            created_at TEXT DEFAULT CURRENT_TIMESTAMP
                        );
                        
                        CREATE TABLE IF NOT EXISTS activity_data (
                            id INTEGER PRIMARY KEY AUTOINCREMENT,
                            timestamp TEXT NOT NULL,
                            username TEXT NOT NULL,
                            hostname TEXT NOT NULL,
                            source TEXT NOT NULL,
                            activity_data TEXT NOT NULL,
                            productivity_hours REAL DEFAULT 0,
                            screenshot_path TEXT,
                            location_data TEXT,
                            sent_to_server BOOLEAN DEFAULT FALSE,
                            created_at TEXT DEFAULT CURRENT_TIMESTAMP
                        );
                        
                        CREATE TABLE IF NOT EXISTS sync_status (
                            id INTEGER PRIMARY KEY AUTOINCREMENT,
                            table_name TEXT NOT NULL,
                            record_id INTEGER NOT NULL,
                            sync_attempts INTEGER DEFAULT 0,
                            last_sync_attempt TEXT,
                            sync_error TEXT,
                            created_at TEXT DEFAULT CURRENT_TIMESTAMP
                        );
                        
                        -- Create indexes for better performance
                        CREATE INDEX IF NOT EXISTS idx_heartbeats_timestamp ON heartbeats(timestamp);
                        CREATE INDEX IF NOT EXISTS idx_heartbeats_sent ON heartbeats(sent_to_server);
                        CREATE INDEX IF NOT EXISTS idx_heartbeats_username ON heartbeats(username);
                        
                        CREATE INDEX IF NOT EXISTS idx_activity_timestamp ON activity_data(timestamp);
                        CREATE INDEX IF NOT EXISTS idx_activity_sent ON activity_data(sent_to_server);
                        CREATE INDEX IF NOT EXISTS idx_activity_username ON activity_data(username);
                        
                        CREATE INDEX IF NOT EXISTS idx_sync_status ON sync_status(table_name, record_id);
                    ''')
                    
                    logging.info("Database schema initialized successfully")
                    
                finally:
                    conn.close()
                    
        except Exception as e:
            logging.error(f"Database initialization error: {e}")
            raise
            
    def store_heartbeat(self, username: str, hostname: str, status: str = "online", 
                       location_data: Optional[Dict[str, Any]] = None) -> Optional[int]:
        """Store heartbeat data with proper error handling"""
        try:
            with self._lock:
                conn = self._get_connection()
                try:
                    timestamp = datetime.now().isoformat()
                    location_json = json.dumps(location_data) if location_data else None
                    
                    cursor = conn.execute('''
                        INSERT INTO heartbeats (timestamp, username, hostname, status, location_data, sent_to_server)
                        VALUES (?, ?, ?, ?, ?, ?)
                    ''', (timestamp, username, hostname, status, location_json, False))
                    
                    record_id = cursor.lastrowid
                    logging.debug(f"Heartbeat stored with ID: {record_id}")
                    return record_id
                    
                finally:
                    conn.close()
                    
        except Exception as e:
            logging.error(f"Error storing heartbeat: {e}")
            return None
            
    def store_activity_data(self, username: str, hostname: str, source: str, 
                           activity_data: Dict[str, Any], productivity_hours: float = 0,
                           screenshot_path: Optional[str] = None,
                           location_data: Optional[Dict[str, Any]] = None) -> Optional[int]:
        """Store activity data with proper error handling"""
        try:
            with self._lock:
                conn = self._get_connection()
                try:
                    timestamp = datetime.now().isoformat()
                    activity_json = json.dumps(activity_data)
                    location_json = json.dumps(location_data) if location_data else None
                    
                    cursor = conn.execute('''
                        INSERT INTO activity_data (timestamp, username, hostname, source, activity_data, 
                                                 productivity_hours, screenshot_path, location_data, sent_to_server)
                        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                    ''', (timestamp, username, hostname, source, activity_json, productivity_hours, 
                          screenshot_path, location_json, False))
                    
                    record_id = cursor.lastrowid
                    logging.debug(f"Activity data stored with ID: {record_id}")
                    return record_id
                    
                finally:
                    conn.close()
                    
        except Exception as e:
            logging.error(f"Error storing activity data: {e}")
            return None
            
    def get_unsent_heartbeats(self, limit: int = 100) -> List[Tuple]:
        """Get unsent heartbeats for server transmission"""
        try:
            with self._lock:
                conn = self._get_connection()
                try:
                    cursor = conn.execute('''
                        SELECT id, timestamp, username, hostname, status, location_data
                        FROM heartbeats 
                        WHERE sent_to_server = FALSE 
                        ORDER BY timestamp ASC 
                        LIMIT ?
                    ''', (limit,))
                    
                    results = cursor.fetchall()
                    logging.debug(f"Retrieved {len(results)} unsent heartbeats")
                    return results
                    
                finally:
                    conn.close()
                    
        except Exception as e:
            logging.error(f"Error getting unsent heartbeats: {e}")
            return []
            
    def get_unsent_activity_data(self, limit: int = 50) -> List[Tuple]:
        """Get unsent activity data for server transmission"""
        try:
            with self._lock:
                conn = self._get_connection()
                try:
                    cursor = conn.execute('''
                        SELECT id, timestamp, username, hostname, source, activity_data, 
                               productivity_hours, screenshot_path, location_data
                        FROM activity_data 
                        WHERE sent_to_server = FALSE 
                        ORDER BY timestamp ASC 
                        LIMIT ?
                    ''', (limit,))
                    
                    results = cursor.fetchall()
                    logging.debug(f"Retrieved {len(results)} unsent activity records")
                    return results
                    
                finally:
                    conn.close()
                    
        except Exception as e:
            logging.error(f"Error getting unsent activity data: {e}")
            return []
            
    def mark_as_sent(self, table_name: str, record_id: int) -> bool:
        """Mark a record as successfully sent to server"""
        try:
            with self._lock:
                conn = self._get_connection()
                try:
                    conn.execute(f'''
                        UPDATE {table_name} 
                        SET sent_to_server = TRUE 
                        WHERE id = ?
                    ''', (record_id,))
                    
                    if conn.total_changes > 0:
                        logging.debug(f"Marked {table_name} record {record_id} as sent")
                        return True
                    else:
                        logging.warning(f"No record found to mark as sent: {table_name} ID {record_id}")
                        return False
                        
                finally:
                    conn.close()
                    
        except Exception as e:
            logging.error(f"Error marking record as sent: {e}")
            return False
            
    def record_sync_attempt(self, table_name: str, record_id: int, error: Optional[str] = None) -> None:
        """Record synchronization attempt for monitoring"""
        try:
            with self._lock:
                conn = self._get_connection()
                try:
                    timestamp = datetime.now().isoformat()
                    
                    # Check if sync status record exists
                    cursor = conn.execute('''
                        SELECT id, sync_attempts FROM sync_status 
                        WHERE table_name = ? AND record_id = ?
                    ''', (table_name, record_id))
                    
                    existing = cursor.fetchone()
                    
                    if existing:
                        # Update existing record
                        sync_id, attempts = existing
                        conn.execute('''
                            UPDATE sync_status 
                            SET sync_attempts = ?, last_sync_attempt = ?, sync_error = ?
                            WHERE id = ?
                        ''', (attempts + 1, timestamp, error, sync_id))
                    else:
                        # Create new record
                        conn.execute('''
                            INSERT INTO sync_status (table_name, record_id, sync_attempts, last_sync_attempt, sync_error)
                            VALUES (?, ?, ?, ?, ?)
                        ''', (table_name, record_id, 1, timestamp, error))
                        
                finally:
                    conn.close()
                    
        except Exception as e:
            logging.error(f"Error recording sync attempt: {e}")
            
    def cleanup_old_data(self) -> None:
        """Clean up old data based on retention policy"""
        try:
            cutoff_date = (datetime.now() - timedelta(days=self.cleanup_days)).isoformat()
            
            with self._lock:
                conn = self._get_connection()
                try:
                    # Clean up old sent heartbeats
                    cursor = conn.execute('''
                        DELETE FROM heartbeats 
                        WHERE sent_to_server = TRUE AND timestamp < ?
                    ''', (cutoff_date,))
                    heartbeats_deleted = cursor.rowcount
                    
                    # Clean up old sent activity data
                    cursor = conn.execute('''
                        DELETE FROM activity_data 
                        WHERE sent_to_server = TRUE AND timestamp < ?
                    ''', (cutoff_date,))
                    activity_deleted = cursor.rowcount
                    
                    # Clean up old sync status records
                    cursor = conn.execute('''
                        DELETE FROM sync_status 
                        WHERE created_at < ?
                    ''', (cutoff_date,))
                    sync_deleted = cursor.rowcount
                    
                    if heartbeats_deleted > 0 or activity_deleted > 0 or sync_deleted > 0:
                        logging.info(f"Cleanup completed: {heartbeats_deleted} heartbeats, "
                                   f"{activity_deleted} activity records, {sync_deleted} sync records deleted")
                        
                finally:
                    conn.close()
                    
        except Exception as e:
            logging.error(f"Error during data cleanup: {e}")
            
    def get_database_stats(self) -> Dict[str, Any]:
        """Get database statistics for monitoring"""
        try:
            with self._lock:
                conn = self._get_connection()
                try:
                    stats = {}
                    
                    # Count records in each table
                    for table in ['heartbeats', 'activity_data', 'sync_status']:
                        cursor = conn.execute(f'SELECT COUNT(*) FROM {table}')
                        stats[f'{table}_count'] = cursor.fetchone()[0]
                        
                        # Count unsent records
                        if table in ['heartbeats', 'activity_data']:
                            cursor = conn.execute(f'SELECT COUNT(*) FROM {table} WHERE sent_to_server = FALSE')
                            stats[f'{table}_unsent'] = cursor.fetchone()[0]
                    
                    # Database file size
                    if self.db_path.exists():
                        stats['database_size_mb'] = round(self.db_path.stat().st_size / (1024 * 1024), 2)
                    else:
                        stats['database_size_mb'] = 0
                        
                    return stats
                    
                finally:
                    conn.close()
                    
        except Exception as e:
            logging.error(f"Error getting database stats: {e}")
            return {}