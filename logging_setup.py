import os
import logging
from datetime import datetime
from pathlib import Path

def setup_logging(level_name="INFO", log_file=None):
    """
    Set up logging configuration for the application
    
    Args:
        level_name: Logging level as string (DEBUG, INFO, WARNING, ERROR, CRITICAL)
        log_file: Optional path to log file
        
    Returns:
        Logger object
    """
    # Convert level name to logging level
    level = getattr(logging, level_name.upper(), logging.INFO)
    
    # Create logs directory if it doesn't exist
    logs_dir = Path("logs")
    logs_dir.mkdir(exist_ok=True)
    
    # If no log file specified, create a default one with timestamp
    if not log_file:
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        log_file = logs_dir / f"elysium_{timestamp}.log"
    
    # Configure logging format
    format_string = '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    logging.basicConfig(
        level=level,
        format=format_string,
        handlers=[
            logging.StreamHandler(),  # Output to console
            logging.FileHandler(log_file)  # Output to file
        ]
    )
    
    logger = logging.getLogger('elysium')
    logger.info(f"Logging initialized at level {level_name}")
    logger.info(f"Log file: {log_file}")
    
    return logger