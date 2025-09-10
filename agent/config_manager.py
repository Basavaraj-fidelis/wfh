#!/usr/bin/env python3
"""
Configuration Manager for WFH Monitoring Agent
Handles loading and validation of configuration from file and environment variables
"""

import os
import json
import logging
from pathlib import Path
from typing import Dict, Any, Optional
import re

class ConfigManager:
    def __init__(self, config_file: str = "config.json"):
        self.config_file = Path(__file__).parent / config_file
        self.config = {}
        self.load_config()
        
    def load_config(self) -> None:
        """Load configuration from file and environment variables"""
        try:
            # Load base configuration from file
            if self.config_file.exists():
                with open(self.config_file, 'r') as f:
                    content = f.read()
                    # Replace environment variable placeholders
                    content = self._substitute_env_vars(content)
                    self.config = json.loads(content)
            else:
                # Use default configuration if file doesn't exist
                self.config = self._get_default_config()
                logging.warning(f"Config file {self.config_file} not found, using defaults")
                
            # Validate required configuration
            self._validate_config()
            
        except Exception as e:
            logging.error(f"Failed to load configuration: {e}")
            self.config = self._get_default_config()
            
    def _substitute_env_vars(self, content: str) -> str:
        """Replace ${VAR_NAME} with environment variable values"""
        def replace_var(match):
            var_name = match.group(1)
            return os.getenv(var_name, match.group(0))  # Keep placeholder if env var not found
            
        return re.sub(r'\$\{([^}]+)\}', replace_var, content)
        
    def _get_default_config(self) -> Dict[str, Any]:
        """Return default configuration"""
        return {
            "server": {
                "url": os.getenv("WFH_SERVER_URL", "http://localhost:8000"),
                "auth_token": os.getenv("WFH_AUTH_TOKEN", "agent-secret-token-change-this"),
                "timeout": 30,
                "retry_attempts": 3,
                "retry_delay": 5
            },
            "intervals": {
                "heartbeat_minutes": 5,
                "activity_collection_minutes": 30,
                "data_sync_minutes": 10,
                "scheduler_check_seconds": 30
            },
            "activitywatch": {
                "base_url": "http://localhost:5600",
                "timeout": 10,
                "data_retention_hours": 24,
                "bucket_patterns": {
                    "window": ["window", "app"],
                    "web": ["web", "browser", "chrome", "firefox"]
                }
            },
            "local_storage": {
                "database_name": "agent_data.db",
                "cleanup_days": 7,
                "max_screenshot_size_mb": 5
            },
            "logging": {
                "level": "INFO",
                "max_file_size_mb": 10,
                "backup_count": 5
            }
        }
        
    def _validate_config(self) -> None:
        """Validate required configuration fields"""
        required_fields = [
            ("server", "url"),
            ("server", "auth_token"),
            ("intervals", "heartbeat_minutes"),
            ("intervals", "activity_collection_minutes"),
            ("intervals", "data_sync_minutes")
        ]
        
        for section, field in required_fields:
            if section not in self.config or field not in self.config[section]:
                raise ValueError(f"Missing required configuration: {section}.{field}")
                
        # Validate server URL format
        server_url = self.config["server"]["url"]
        if not (server_url.startswith("http://") or server_url.startswith("https://")):
            raise ValueError("Server URL must start with http:// or https://")
            
    def get(self, section: str, key: str, default: Any = None) -> Any:
        """Get configuration value"""
        return self.config.get(section, {}).get(key, default)
        
    def get_section(self, section: str) -> Dict[str, Any]:
        """Get entire configuration section"""
        return self.config.get(section, {})
        
    def get_server_url(self) -> str:
        """Get server URL with trailing slash removed"""
        return self.get("server", "url").rstrip('/')
        
    def get_auth_token(self) -> str:
        """Get authentication token"""
        return self.get("server", "auth_token")
        
    def save_config(self, config_dict: Dict[str, Any]) -> None:
        """Save configuration to file"""
        try:
            with open(self.config_file, 'w') as f:
                json.dump(config_dict, f, indent=2)
            self.config = config_dict
            logging.info(f"Configuration saved to {self.config_file}")
        except Exception as e:
            logging.error(f"Failed to save configuration: {e}")