#!/usr/bin/env python3
"""
Elysium Trading Platform Telegram Bot
Main entrypoint file
"""

import os
import sys
import logging
import argparse
import traceback
from pathlib import Path
from typing import Optional

# Try to import dotenv, handle case when it's not installed
try:
    from dotenv import load_dotenv
    # Load environment variables from .env file
    load_dotenv()
except ImportError:
    print("python-dotenv not installed. Environment variables from .env will not be loaded.")
    print("Run 'pip install python-dotenv' to install it.")
    # Continue without dotenv

# Configure basic logging first so we can log import errors
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[logging.StreamHandler()]
)
logger = logging.getLogger('elysium_bot')

# Try to import project modules with error handling
try:
    # Import project modules
    from interfaces.telegram_bot import ElysiumTelegramBot
    from api.status import StatusChecker
    from utils.config import ConfigManager
except ImportError as e:
    logger.error(f"Failed to import required modules: {e}")
    logger.error(f"Make sure all requirements are installed: pip install -r requirements.txt")
    logger.error(traceback.format_exc())
    sys.exit(1)

def parse_arguments():
    """Parse command line arguments"""
    parser = argparse.ArgumentParser(description='Elysium Trading Platform Telegram Bot')
    parser.add_argument('-t', '--token', type=str,
                        help='Telegram bot token')
    parser.add_argument('-a', '--admin-ids', type=str,
                        help='Comma-separated list of admin user IDs')
    parser.add_argument('-c', '--config', type=str, default='config.json',
                        help='Path to configuration file')
    parser.add_argument('-v', '--verbose', action='store_true',
                        help='Enable verbose logging')
    parser.add_argument('--log-file', type=str, 
                        help='Log to this file instead of console')
    return parser.parse_args()

def setup_logging(verbose: bool = False, log_file: Optional[str] = None) -> logging.Logger:
    """Set up logging"""
    level = logging.DEBUG if verbose else logging.INFO
    
    # Get the root logger and clear existing handlers
    logger = logging.getLogger()
    logger.setLevel(level)
    
    # Remove existing handlers to avoid duplicate logs
    for handler in logger.handlers[:]:
        logger.removeHandler(handler)
    
    # Add handlers based on configuration
    if log_file:
        try:
            file_handler = logging.FileHandler(log_file)
            file_handler.setFormatter(logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s'))
            logger.addHandler(file_handler)
        except (IOError, PermissionError) as e:
            print(f"Warning: Could not create log file {log_file}: {e}")
            print("Falling back to console logging")
            console_handler = logging.StreamHandler()
            console_handler.setFormatter(logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s'))
            logger.addHandler(console_handler)
    else:
        console_handler = logging.StreamHandler()
        console_handler.setFormatter(logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s'))
        logger.addHandler(console_handler)
    
    return logging.getLogger('elysium_bot')

def get_token_from_sources(args, config_manager) -> Optional[str]:
    """Try to get token from various sources"""
    # First check command line argument
    if args.token:
        logger.info("Using token from command line argument")
        return args.token
    
    # Then check environment variable
    env_token = os.environ.get('TELEGRAM_TOKEN')
    if env_token:
        logger.info("Using token from TELEGRAM_TOKEN environment variable")
        return env_token
        
    # Then check config
    config_token = config_manager.get('telegram_token')
    if config_token:
        logger.info("Using token from config file")
        return config_token
    
    # Finally check dontshareconfig.py
    try:
        import dontshareconfig
        if hasattr(dontshareconfig, 'telegram_token'):
            logger.info("Using token from dontshareconfig.py")
            return dontshareconfig.telegram_token
    except ImportError:
        pass
    
    # No token found
    return None

def get_admin_ids_from_sources(args, config_manager) -> list:
    """Try to get admin IDs from various sources"""
    admin_ids = []
    
    # First check command line argument
    if args.admin_ids:
        try:
            admin_ids = [int(uid.strip()) for uid in args.admin_ids.split(',')]
            logger.info(f"Using admin IDs from command line argument: {admin_ids}")
            return admin_ids
        except ValueError:
            logger.warning("Admin IDs must be comma-separated integers. Ignoring invalid input.")
    
    # Then check environment variable
    admin_ids_str = os.environ.get('ADMIN_USER_IDS', '')
    if admin_ids_str:
        try:
            admin_ids = [int(uid.strip()) for uid in admin_ids_str.split(',')]
            logger.info(f"Using admin IDs from environment variable: {admin_ids}")
            return admin_ids
        except ValueError:
            logger.warning("Admin IDs in environment must be comma-separated integers. Ignoring invalid input.")
    
    # Then check config
    config_admin_ids = config_manager.get('admin_user_ids', [])
    if config_admin_ids:
        logger.info(f"Using admin IDs from config file: {config_admin_ids}")
        return config_admin_ids
    
    # Finally check dontshareconfig.py
    try:
        import dontshareconfig
        if hasattr(dontshareconfig, 'telegram_admin_ids'):
            logger.info(f"Using admin IDs from dontshareconfig.py: {dontshareconfig.telegram_admin_ids}")
            return dontshareconfig.telegram_admin_ids
    except ImportError:
        pass
    
    # No admin IDs found, return empty list
    return []

def check_bot_class(bot_class):
    """Check if the bot class has all the necessary methods"""
    required_methods = [
        'start', 'stop', 'cmd_start', 'cmd_help', 'cmd_status',
        'cmd_balance', 'cmd_positions', 'cmd_orders', 
        'cmd_buy', 'cmd_sell', 'cmd_close'
    ]
    
    missing_methods = []
    for method in required_methods:
        if not hasattr(bot_class, method):
            missing_methods.append(method)
    
    if missing_methods:
        logger.error(f"Bot class is missing required methods: {', '.join(missing_methods)}")
        logger.error("This might cause errors when the bot receives commands")
        return False
    
    return True

def main():
    """Main entrypoint function"""
    try:
        args = parse_arguments()
        logger = setup_logging(args.verbose, args.log_file)
        
        # Create data directory if it doesn't exist
        data_dir = Path("user_data")
        data_dir.mkdir(exist_ok=True)
        
        # Load configuration
        try:
            config_manager = ConfigManager(args.config)
        except Exception as e:
            logger.error(f"Failed to initialize config manager: {e}")
            logger.error("Will continue with default configuration")
            config_manager = ConfigManager()
        
        # Get token and admin IDs
        token = get_token_from_sources(args, config_manager)
        admin_ids = get_admin_ids_from_sources(args, config_manager)
        
        # Check for token
        if not token:
            logger.error("No Telegram bot token provided.")
            logger.error("Please use one of the following methods:")
            logger.error("1. Command line: python elysium.py --token YOUR_TOKEN")
            logger.error("2. Environment variable: export TELEGRAM_TOKEN=YOUR_TOKEN")
            logger.error("3. Config file: create config.json with {\"telegram_token\": \"YOUR_TOKEN\"}")
            logger.error("4. Create a .env file with TELEGRAM_TOKEN=YOUR_TOKEN")
            return 1
        
        # Initialize bot
        logger.info("Initializing Elysium Telegram Bot")
        
        # Check API status
        try:
            status_checker = StatusChecker()
            is_online, message = status_checker.check_api_status()
            
            if not is_online:
                logger.warning(f"API is not online: {message}")
                logger.warning("Bot will start but some functionality may not work until API is available")
        except Exception as e:
            logger.error(f"Error checking API status: {e}")
            logger.warning("Could not verify API status. Some functionality may not work.")
        
        # Create the bot instance
        try:
            bot = ElysiumTelegramBot(token=token, admin_ids=admin_ids)
            
            # Verify that the bot class has all required methods
            check_bot_class(bot)
            
            # Save token and admin IDs to config for future runs if not already there
            if not config_manager.get('telegram_token'):
                config_manager.set('telegram_token', token)
            
            if not config_manager.get('admin_user_ids') and admin_ids:
                config_manager.set('admin_user_ids', admin_ids)
        except Exception as e:
            logger.error(f"Failed to initialize bot: {e}")
            logger.error(traceback.format_exc())
            return 1
        
        # Start the bot
        try:
            logger.info("Starting Elysium Telegram Bot")
            bot.start()
        except KeyboardInterrupt:
            logger.info("Bot stopped by user (Ctrl+C)")
        except Exception as e:
            logger.error(f"Error running bot: {e}")
            logger.error(traceback.format_exc())
            return 1
    except Exception as e:
        logger.error(f"Unhandled error in main function: {e}")
        logger.error(traceback.format_exc())
        return 1
    
    return 0

if __name__ == "__main__":
    sys.exit(main())