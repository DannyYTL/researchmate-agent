"""
Structured logging configuration for ResearchMate.

Provides consistent logging across all modules with configurable levels.
"""

import logging
import os
import sys
from typing import Optional


def setup_logger(
    name: str = "researchmate",
    level: Optional[str] = None,
    format_string: Optional[str] = None,
) -> logging.Logger:
    """
    Set up a logger with consistent formatting.

    Args:
        name: Logger name (typically module name)
        level: Logging level (DEBUG, INFO, WARNING, ERROR). Defaults to env var LOG_LEVEL
        format_string: Custom format string. Uses default if not provided

    Returns:
        Configured logger instance
    """
    # Get log level from environment or use provided level
    if level is None:
        level = os.getenv("LOG_LEVEL", "INFO").upper()

    # Default format: timestamp | level | module | message
    if format_string is None:
        format_string = "%(asctime)s | %(levelname)-8s | %(name)s | %(message)s"

    # Create logger
    logger = logging.getLogger(name)
    logger.setLevel(getattr(logging, level))

    # Remove existing handlers to avoid duplicates
    logger.handlers.clear()

    # Console handler
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(getattr(logging, level))

    # Formatter
    formatter = logging.Formatter(format_string, datefmt="%Y-%m-%d %H:%M:%S")
    console_handler.setFormatter(formatter)

    # Add handler
    logger.addHandler(console_handler)

    # Prevent propagation to root logger
    logger.propagate = False

    return logger


# Default logger instance
logger = setup_logger()
