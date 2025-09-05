
#!/usr/bin/env python3
"""
Windows Service Wrapper for WFH Monitoring Agent
This allows the agent to run as a proper Windows service
"""

import sys
import time
import logging
from pathlib import Path

# Configure logging for service
log_file = Path(__file__).parent / "service.log"
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler(log_file),
        logging.StreamHandler(sys.stdout)
    ]
)

def run_as_service():
    """Run the agent in service mode"""
    try:
        # Import and run the main agent
        from agent import MonitoringAgent
        
        # Configuration
        SERVER_URL = "https://e1cdd19c-fdf6-4b9f-94bf-b122742d048e-00-2ltrq5fmw548e.riker.replit.dev"
        AUTH_TOKEN = "agent-secret-token-change-this-in-production"
        
        logging.info("Starting WFH Monitoring Agent as service...")
        
        # Create and start agent
        agent = MonitoringAgent(SERVER_URL, AUTH_TOKEN)
        agent.start()
        
    except Exception as e:
        logging.error(f"Service error: {e}")
        import traceback
        logging.error(traceback.format_exc())
        
        # Wait and restart
        time.sleep(30)
        run_as_service()

if __name__ == "__main__":
    run_as_service()
