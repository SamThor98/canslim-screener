"""
Logging configuration for CANSLIM Stock Screener.
"""
import logging
import sys
from config import config


def setup_logging():
    """
    Configure logging for the application.
    Sets up console handler with appropriate format and level.
    """
    # Create root logger
    logger = logging.getLogger()
    logger.setLevel(getattr(logging, config.log_level.upper()))
    
    # Remove existing handlers to avoid duplicates
    logger.handlers.clear()
    
    # Create console handler
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(getattr(logging, config.log_level.upper()))
    
    # Create formatter
    formatter = logging.Formatter(config.log_format)
    console_handler.setFormatter(formatter)
    
    # Add handler to logger
    logger.addHandler(console_handler)
    
    return logger


def get_logger(name: str) -> logging.Logger:
    """
    Get a logger instance for a module.
    
    Args:
        name: Logger name (typically __name__)
    
    Returns:
        Configured logger instance
    """
    return logging.getLogger(name)
