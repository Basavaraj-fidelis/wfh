#!/usr/bin/env python3
"""
Main entry point for WFH Monitoring Agent v2.0
Simple script to run the agent with configuration management
"""

import os
import sys
from pathlib import Path

def main():
    """Main entry point for the monitoring agent"""
    try:
        # Check for required environment variables
        server_url = os.getenv('WFH_SERVER_URL')
        auth_token = os.getenv('WFH_AUTH_TOKEN')
        
        if not server_url or not auth_token:
            print("ERROR: Missing required environment variables:")
            if not server_url:
                print("  WFH_SERVER_URL - The URL of your WFH monitoring server")
            if not auth_token:
                print("  WFH_AUTH_TOKEN - The authentication token for the agent")
            print("\nPlease set these environment variables before running the agent.")
            print("Example:")
            print("  export WFH_SERVER_URL='https://your-server-url.com'")
            print("  export WFH_AUTH_TOKEN='your-agent-token'")
            sys.exit(1)
            
        # Import and run the agent
        from agent import MonitoringAgent
        
        # Create and start agent with config file
        agent = MonitoringAgent("config.json")
        success = agent.start()
        
        if success:
            print("Agent stopped successfully")
            sys.exit(0)
        else:
            print("Agent failed to start")
            sys.exit(1)
            
    except KeyboardInterrupt:
        print("\nAgent stopped by user")
        sys.exit(0)
    except ImportError as e:
        print(f"Import error: {e}")
        print("Please install required dependencies:")
        print("  pip install -r agent_requirements.txt")
        sys.exit(1)
    except Exception as e:
        print(f"Error starting agent: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()