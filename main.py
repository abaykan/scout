#!/usr/bin/env python3
"""
S.C.O.U.T (Scope Change Observation & Unified Tracking) - Bug Bounty Monitoring Tool
Main entry point for the application
"""

import argparse
import sys
from src.monitor import SCOUTMonitor
import logging

def setup_logging():
    """Setup basic logging configuration"""
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        handlers=[
            logging.FileHandler('scout.log'),
            logging.StreamHandler(sys.stdout)
        ]
    )

def main():
    """Main entry point for S.C.O.U.T"""
    parser = argparse.ArgumentParser(description='S.C.O.U.T (Scope Change Observation & Unified Tracking) - Bug Bounty Monitoring Tool')
    parser.add_argument('--config', default='config.json', help='Path to config file')
    
    args = parser.parse_args()
    
    setup_logging()
    logger = logging.getLogger(__name__)
    
    try:
        # Initialize monitor
        monitor = SCOUTMonitor(args.config)
        
        # Run monitoring once
        logger.info("Running one-time monitoring...")
        monitor.run_once()
        logger.info("One-time monitoring completed")
            
    except KeyboardInterrupt:
        logger.info("S.C.O.U.T stopped by user")
    except Exception as e:
        logger.error(f"S.C.O.U.T error: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()