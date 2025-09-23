"""
DafelHub Logging Configuration
Enterprise-grade logging with structured output and multiple handlers.
"""

import json
import logging
import logging.handlers
import sys
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, Optional

from rich.console import Console
from rich.logging import RichHandler

from dafelhub.core.config import settings


class JSONFormatter(logging.Formatter):
    """
    JSON formatter for structured logging
    """
    
    def format(self, record: logging.LogRecord) -> str:
        """
        Format log record as JSON
        """
        log_entry = {
            "timestamp": datetime.fromtimestamp(record.created).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
            "module": record.module,
            "function": record.funcName,
            "line": record.lineno,
        }
        
        if record.exc_info:
            log_entry["exception"] = self.formatException(record.exc_info)
            
        if hasattr(record, "extra_data"):
            log_entry["extra"] = record.extra_data
            
        return json.dumps(log_entry, ensure_ascii=False)


class DafelHubLogger:
    """
    Enterprise logging configuration
    """
    
    def __init__(self):
        self.console = Console()
        self.log_dir = Path("logs")
        self.log_dir.mkdir(exist_ok=True)
        
    def setup_logging(self) -> None:
        """
        Setup logging configuration
        """
        # Root logger
        root_logger = logging.getLogger()
        root_logger.setLevel(getattr(logging, settings.LOG_LEVEL.upper()))
        
        # Remove default handlers
        for handler in root_logger.handlers[:]:
            root_logger.removeHandler(handler)
            
        # Console handler with Rich
        console_handler = RichHandler(
            console=self.console,
            rich_tracebacks=True,
            show_path=True,
            show_time=True,
        )
        console_handler.setLevel(getattr(logging, settings.LOG_LEVEL.upper()))
        
        # File handler for all logs
        file_handler = logging.handlers.RotatingFileHandler(
            self.log_dir / "dafelhub.log",
            maxBytes=10 * 1024 * 1024,  # 10MB
            backupCount=5,
        )
        file_handler.setLevel(logging.INFO)
        file_handler.setFormatter(JSONFormatter())
        
        # Error file handler
        error_handler = logging.handlers.RotatingFileHandler(
            self.log_dir / "error.log",
            maxBytes=10 * 1024 * 1024,  # 10MB
            backupCount=5,
        )
        error_handler.setLevel(logging.ERROR)
        error_handler.setFormatter(JSONFormatter())
        
        # Add handlers
        root_logger.addHandler(console_handler)
        root_logger.addHandler(file_handler)
        root_logger.addHandler(error_handler)
        
        # Set specific logger levels
        logging.getLogger("uvicorn").setLevel(logging.INFO)
        logging.getLogger("sqlalchemy").setLevel(logging.WARNING)
        logging.getLogger("httpx").setLevel(logging.WARNING)
        
        # Application logger
        app_logger = logging.getLogger("dafelhub")
        app_logger.setLevel(getattr(logging, settings.LOG_LEVEL.upper()))


# Global logger instance
_logger_instance: Optional[DafelHubLogger] = None


def get_logger(name: str) -> logging.Logger:
    """
    Get logger instance with proper configuration
    """
    global _logger_instance
    
    if _logger_instance is None:
        _logger_instance = DafelHubLogger()
        _logger_instance.setup_logging()
    
    return logging.getLogger(name)


class LoggerMixin:
    """
    Mixin to add logging capabilities to classes
    """
    
    @property
    def logger(self) -> logging.Logger:
        """
        Get logger for this class
        """
        return get_logger(self.__class__.__module__ + "." + self.__class__.__name__)
    
    def log_with_context(
        self, 
        level: int, 
        message: str, 
        extra_data: Optional[Dict[str, Any]] = None
    ) -> None:
        """
        Log with additional context data
        """
        record = self.logger.makeRecord(
            name=self.logger.name,
            level=level,
            fn="",
            lno=0,
            msg=message,
            args=(),
            exc_info=None,
        )
        
        if extra_data:
            record.extra_data = extra_data
            
        self.logger.handle(record)