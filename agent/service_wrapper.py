
#!/usr/bin/env python3
"""
Service Wrapper for WFH Monitoring Agent v2.0
Cross-platform service wrapper with configuration management and better error handling
"""

import sys
import time
import logging
import os
from pathlib import Path

def setup_service_logging():
    """Setup logging specifically for service mode"""
    log_dir = Path(__file__).parent / "logs"
    log_dir.mkdir(exist_ok=True)
    
    log_file = log_dir / "service.log"
    
    # Configure logging with rotation
    try:
        from logging.handlers import RotatingFileHandler
        
        file_handler = RotatingFileHandler(
            log_file,
            maxBytes=10 * 1024 * 1024,  # 10MB
            backupCount=5,
            encoding='utf-8'
        )
        
        console_handler = logging.StreamHandler(sys.stdout)
        
        formatter = logging.Formatter(
            '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
        )
        
        file_handler.setFormatter(formatter)
        console_handler.setFormatter(formatter)
        
        # Configure root logger
        root_logger = logging.getLogger()
        root_logger.setLevel(logging.INFO)
        root_logger.addHandler(file_handler)
        root_logger.addHandler(console_handler)
        
    except ImportError:
        # Fallback for systems without RotatingFileHandler
        logging.basicConfig(
            level=logging.INFO,
            format='%(asctime)s - %(levelname)s - %(message)s',
            handlers=[
                logging.FileHandler(log_file, encoding='utf-8'),
                logging.StreamHandler(sys.stdout)
            ]
        )

def run_as_service():
    """Run the agent in service mode with proper error handling and recovery"""
    setup_service_logging()
    
    restart_count = 0
    max_restarts = 10
    restart_delay = 30
    
    while restart_count < max_restarts:
        try:
            logging.info("=" * 60)
            logging.info(f"Starting WFH Monitoring Agent Service (attempt {restart_count + 1})")
            logging.info("=" * 60)
            
            # Import the modular agent
            from agent import MonitoringAgent
            
            # Initialize with config file (will use environment variables from config)
            config_file = "config.json"
            config_path = Path(__file__).parent / config_file
            
            if not config_path.exists():
                logging.warning(f"Config file {config_file} not found, creating default...")
                # The ConfigManager will create a default config using environment variables
                
            # Create and start agent
            agent = MonitoringAgent(config_file)
            
            # Start agent (this will block until stopped)
            success = agent.start()
            
            if success:
                logging.info("Agent stopped gracefully")
                break  # Graceful shutdown, don't restart
            else:
                logging.error("Agent failed to start properly")
                restart_count += 1
                
        except KeyboardInterrupt:
            logging.info("Service stopped by user (Ctrl+C)")
            break
            
        except ImportError as e:
            logging.error(f"Import error: {e}")
            logging.error("Please ensure all required modules are installed:")
            logging.error("pip install -r agent_requirements.txt")
            break  # Don't restart for import errors
            
        except Exception as e:
            restart_count += 1
            logging.error(f"Service error (attempt {restart_count}/{max_restarts}): {e}")
            
            import traceback
            logging.error(f"Full traceback:\n{traceback.format_exc()}")
            
            if restart_count < max_restarts:
                logging.info(f"Restarting service in {restart_delay} seconds...")
                time.sleep(restart_delay)
                
                # Increase delay for subsequent restarts (exponential backoff)
                restart_delay = min(300, restart_delay * 1.5)  # Max 5 minutes
            else:
                logging.error(f"Maximum restart attempts ({max_restarts}) reached, stopping service")
                break
                
    logging.info("Service wrapper exiting")

def main():
    """Main entry point with platform detection"""
    try:
        # Check for required environment variables
        required_env_vars = ["WFH_SERVER_URL", "WFH_AUTH_TOKEN"]
        missing_vars = []
        
        for var in required_env_vars:
            if not os.getenv(var):
                missing_vars.append(var)
                
        if missing_vars:
            print("ERROR: Missing required environment variables:")
            for var in missing_vars:
                print(f"  {var}")
            print("\nPlease set these environment variables before running the service.")
            print("Example:")
            print("  export WFH_SERVER_URL='https://your-server-url.com'")
            print("  export WFH_AUTH_TOKEN='your-agent-token'")
            sys.exit(1)
            
        # Platform-specific service startup
        platform = sys.platform.lower()
        if platform.startswith('win'):
            logging.info("Detected Windows platform")
        elif platform.startswith('linux'):
            logging.info("Detected Linux platform")
        elif platform.startswith('darwin'):
            logging.info("Detected macOS platform")
        else:
            logging.warning(f"Unknown platform: {platform}")
            
        # Start the service
        run_as_service()
        
    except Exception as e:
        print(f"Service wrapper startup error: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()
