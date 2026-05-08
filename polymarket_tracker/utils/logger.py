"""Logging configuration."""

import sys
from loguru import logger


def setup_logging(debug: bool = False):
    """Configure logging for the application."""
    
    # Remove default handler
    logger.remove()
    
    # Add console handler with colors
    log_format = (
        "<green>{time:YYYY-MM-DD HH:mm:ss}</green> | "
        "<level>{level: <8}</level> | "
        "<cyan>{name}</cyan>:<cyan>{function}</cyan>:<cyan>{line}</cyan> | "
        "<level>{message}</level>"
    )
    
    logger.add(
        sys.stdout,
        format=log_format,
        level="DEBUG" if debug else "INFO",
        colorize=True,
    )
    
    # Add file handler for errors
    logger.add(
        "logs/polymarket_tracker.log",
        format=log_format,
        level="ERROR",
        rotation="10 MB",
        retention="7 days",
    )
    
    return logger
