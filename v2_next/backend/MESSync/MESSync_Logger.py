"""
Centralized Logging Configuration
- JSON Formatting for machine readability
- Daily Rotation for application logs
- Separate Error Logs
"""

import logging
import json
import sys
from pathlib import Path
from logging.handlers import TimedRotatingFileHandler
from datetime import datetime
from .MESSync_Constants import PROJECT_ROOT

# Log Directory setup integrated with SmartFactoryLogger
from .. import config
# Use the main system's system log directory
# Use the main system's system log directory
LOG_DIR = config.APP_DATA_DIR / "logs" / "system"
LOG_DIR.mkdir(parents=True, exist_ok=True)

class JSONFormatter(logging.Formatter):
    """
    Format logs as JSON objects
    """
    def format(self, record):
        log_obj = {
            "ts": datetime.fromtimestamp(record.created).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
            "module": record.module,
            "line": record.lineno,
        }
        
        # Standard attributes to exclude from 'extra' fields
        standard_attrs = {
            'name', 'msg', 'args', 'levelname', 'levelno', 'pathname', 'filename', 
            'module', 'exc_info', 'exc_text', 'stack_info', 'lineno', 'funcName', 
            'created', 'msecs', 'relativeCreated', 'thread', 'threadName', 
            'processName', 'process', 'message', 'taskName'
        }

        # Add extra fields (whatever is in record.__dict__ but not standard)
        for key, value in record.__dict__.items():
            if key not in standard_attrs and not key.startswith('_'):
                log_obj[key] = value
            
        # Add exception info if present
        if record.exc_info:
            log_obj["exc_info"] = self.formatException(record.exc_info)
            
        return json.dumps(log_obj, ensure_ascii=False)

_configured_loggers = {}

def get_logger(name: str) -> logging.Logger:
    """
    Get a configured logger instance (Singleton pattern per name)
    """
    if name in _configured_loggers:
        return _configured_loggers[name]

    logger = logging.getLogger(name)
    
    # Prevent duplicate handlers if already configured by another means
    if logger.handlers:
        _configured_loggers[name] = logger
        return logger
        
    logger.setLevel(logging.INFO)
    
    # 1. JSON Formatter
    json_formatter = JSONFormatter()
    
    # 2. Console Handler (Standard Text for easier reading during dev)
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(logging.INFO)
    # Use standard format for console to keep it readable for humans
    console_formatter = logging.Formatter(
        '[%(asctime)s] [%(levelname)s] %(name)s - %(message)s'
    )
    console_handler.setFormatter(console_formatter)
    
    # 3. Application Log Handler (Daily Rotation, JSON)
    app_log_file = LOG_DIR / "mes_application.log"
    # match existing handler if possible? No, we are creating new.
    # delay=True prevents opening the file until the first log is emitted.
    # This helps avoid WinError 32 during rotation if multiple processes/threads race.
    app_handler = TimedRotatingFileHandler(
        filename=app_log_file,
        when="midnight",
        interval=1,
        backupCount=30, # Keep 30 days
        encoding="utf-8",
        delay=True 
    )
    app_handler.setLevel(logging.INFO)
    app_handler.setFormatter(json_formatter)
    
    # 4. Error Log Handler (Separate file, JSON)
    error_log_file = LOG_DIR / "mes_error.log"
    error_handler = logging.FileHandler(
        filename=error_log_file,
        encoding="utf-8",
        delay=True
    )
    error_handler.setLevel(logging.ERROR)
    error_handler.setFormatter(json_formatter)
    
    # Add Handlers
    logger.addHandler(console_handler)
    logger.addHandler(app_handler)
    logger.addHandler(error_handler)
    
    # Cache the configured logger
    _configured_loggers[name] = logger
    
    return logger

def _cleanup_loggers():
    """Close all handlers on exit"""
    for logger in _configured_loggers.values():
        for handler in logger.handlers:
            try:
                handler.close()
            except:
                pass

import atexit
atexit.register(_cleanup_loggers)
