#!/usr/bin/env python3
"""
Main runner for FPL Bot
"""

import os
import sys
import logging
from dotenv import load_dotenv

# Add current directory to path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from fpl_bot import FPLBot

def setup_logging():
    """Setup logging configuration"""
    logging.basicConfig(
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        level=logging.INFO,
        handlers=[
            logging.FileHandler('fpl_bot.log'),
            logging.StreamHandler(sys.stdout)
        ]
    )

def main():
    """Main function"""
    # Setup logging
    setup_logging()
    logger = logging.getLogger(__name__)
    
    # Set bot token directly (avoiding .env file issues)
    token = "8115853672:AAHJpEUjW7OnYfMkGmrIs7Qc3u2mKYhXxIc"
    
    if not token:
        logger.error("Bot token not configured")
        return 1
    
    try:
        # Create and run bot
        logger.info("Starting FPL Fantasy Football Bot...")
        bot = FPLBot(token)
        bot.run()
    except KeyboardInterrupt:
        logger.info("Bot stopped by user")
        return 0
    except Exception as e:
        logger.error(f"Fatal error: {e}")
        return 1

if __name__ == '__main__':
    sys.exit(main())
