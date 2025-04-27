#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
TempusLoom - Logging Utility
Configure application logging
"""

import os
import sys
import logging
import logging.handlers
from pathlib import Path
from datetime import datetime


def setup_logger(log_level=logging.INFO, log_to_file=True):
    """Set up application logger
    
    Args:
        log_level: Logging level
        log_to_file: Whether to log to file
    
    Returns:
        Logger instance
    """
    # Create logger
    logger = logging.getLogger("tempusloom")
    logger.setLevel(log_level)
    
    # Create console handler
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(log_level)
    
    # Create formatter
    formatter = logging.Formatter(
        '%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )
    console_handler.setFormatter(formatter)
    
    # Add console handler to logger
    logger.addHandler(console_handler)
    
    # Add file handler if requested
    if log_to_file:
        # Determine log file path
        log_dir = _get_log_directory()
        os.makedirs(log_dir, exist_ok=True)
        
        # Create log filename with timestamp
        timestamp = datetime.now().strftime("%Y%m%d")
        log_file = log_dir / f"tempusloom_{timestamp}.log"
        
        # Create file handler
        file_handler = logging.handlers.RotatingFileHandler(
            log_file, 
            maxBytes=10*1024*1024,  # 10MB
            backupCount=5,
            encoding='utf-8'
        )
        file_handler.setLevel(log_level)
        file_handler.setFormatter(formatter)
        
        # Add file handler to logger
        logger.addHandler(file_handler)
        
        logger.info(f"Log file: {log_file}")
    
    logger.info("Logger initialized")
    return logger


def _get_log_directory():
    """Get the log directory path"""
    home = Path.home()
    
    if os.name == 'nt':  # Windows
        log_dir = Path(os.getenv('APPDATA')) / "TempusLoom" / "logs"
    elif os.name == 'posix':  # macOS/Linux
        if sys.platform == 'darwin':  # macOS
            log_dir = home / "Library" / "Logs" / "TempusLoom"
        else:  # Linux
            log_dir = Path(os.getenv('XDG_STATE_HOME', home / ".local" / "state")) / "TempusLoom" / "logs"
    else:
        # Fallback to home directory
        log_dir = home / ".tempusloom" / "logs"
    
    return log_dir 