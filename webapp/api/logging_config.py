"""
Logging configuration for the Win Probability Chart API.

Design Pattern: Configuration Pattern for logging
Algorithm: Python logging module with environment-based configuration
Big O: O(1) for log operations
"""

import os
import logging
import sys
from pathlib import Path
from typing import Optional

# Check if debug mode is enabled
DEBUG_MODE = os.environ.get("DEBUG", "false").lower() in ("true", "1", "yes", "on")

# Log file directory (in webapp directory)
LOG_DIR = Path(__file__).parent.parent / "logs"
LOG_DIR.mkdir(exist_ok=True)

def setup_logging(debug: Optional[bool] = None) -> logging.Logger:
    """
    Set up logging configuration for the application.
    
    Args:
        debug: Override debug mode (if None, uses DEBUG environment variable)
    
    Returns:
        Configured logger instance
    """
    if debug is None:
        debug = DEBUG_MODE
    
    # Create logger
    logger = logging.getLogger("winprob_api")
    logger.setLevel(logging.DEBUG if debug else logging.INFO)
    
    # Remove existing handlers to avoid duplicates
    logger.handlers.clear()
    
    # Create console handler
    console_handler = logging.StreamHandler(sys.stderr)
    console_handler.setLevel(logging.DEBUG if debug else logging.INFO)
    
    # Create formatter
    if debug:
        # Verbose format for debug mode
        formatter = logging.Formatter(
            '%(asctime)s | %(levelname)-8s | %(name)s | %(funcName)s:%(lineno)d | %(message)s',
            datefmt='%Y-%m-%d %H:%M:%S'
        )
    else:
        # Simple format for normal mode
        formatter = logging.Formatter(
            '%(asctime)s | %(levelname)-8s | %(message)s',
            datefmt='%Y-%m-%d %H:%M:%S'
        )
    
    console_handler.setFormatter(formatter)
    logger.addHandler(console_handler)
    
    # Add file handler for persistent logging
    log_file = LOG_DIR / "winprob_api.log"
    file_handler = logging.FileHandler(log_file, encoding='utf-8')
    file_handler.setLevel(logging.DEBUG if debug else logging.INFO)
    file_handler.setFormatter(formatter)
    logger.addHandler(file_handler)
    
    if debug:
        logger.debug(f"Logging to file: {log_file}")
    
    # Prevent propagation to root logger
    logger.propagate = False
    
    if debug:
        logger.debug("Debug mode enabled - verbose logging active")
    
    return logger

def get_logger(name: str = "winprob_api") -> logging.Logger:
    """
    Get a logger instance for a specific module.
    
    Always returns the configured "winprob_api" logger to ensure all logs
    use the same handler configuration.
    
    Args:
        name: Logger name (ignored, kept for API compatibility)
    
    Returns:
        Logger instance (always "winprob_api" logger with handlers)
    """
    # Always return the configured "winprob_api" logger
    # This ensures all modules use the same logger with handlers attached
    return logging.getLogger("winprob_api")

# Initialize logging on import
_logger = setup_logging()

