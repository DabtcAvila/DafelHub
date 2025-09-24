"""
Enterprise Logger
Structured logging with multiple transports, correlation IDs, and log rotation
@module dafelhub.monitoring.logger
"""

import json
import logging
import logging.handlers
import uuid
import threading
import time
import traceback
import asyncio
import psutil
import socket
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Optional, Union, List, Callable
from enum import Enum
from contextlib import contextmanager
from dataclasses import dataclass, asdict


class LogLevel(Enum):
    """Log levels matching Winston configuration"""
    ERROR = 'error'
    WARN = 'warn'
    INFO = 'info'
    HTTP = 'http'
    VERBOSE = 'verbose'  
    DEBUG = 'debug'
    SILLY = 'silly'


@dataclass
class LogContext:
    """Structured log context with enterprise fields"""
    correlation_id: Optional[str] = None
    user_id: Optional[str] = None
    connection_id: Optional[str] = None
    request_id: Optional[str] = None
    session_id: Optional[str] = None
    duration: Optional[float] = None
    operation: Optional[str] = None
    status: Optional[str] = None
    error_type: Optional[str] = None
    component: Optional[str] = None
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary, filtering None values"""
        return {k: v for k, v in asdict(self).items() if v is not None}


class CorrelationIdFilter(logging.Filter):
    """Inject correlation ID into log records"""
    
    def __init__(self):
        super().__init__()
        self.local = threading.local()
    
    def filter(self, record):
        # Get correlation ID from thread local or generate new one
        correlation_id = getattr(self.local, 'correlation_id', None)
        if not correlation_id:
            correlation_id = str(uuid.uuid4())
            self.local.correlation_id = correlation_id
        
        record.correlation_id = correlation_id
        return True
    
    def set_correlation_id(self, correlation_id: str):
        """Set correlation ID for current thread"""
        self.local.correlation_id = correlation_id
    
    def get_correlation_id(self) -> str:
        """Get correlation ID for current thread"""
        return getattr(self.local, 'correlation_id', str(uuid.uuid4()))


class EnterpriseFormatter(logging.Formatter):
    """Enterprise JSON formatter with structured metadata"""
    
    def __init__(self, service_name: str = "dafelhub", version: str = "1.0.0"):
        super().__init__()
        self.service_name = service_name
        self.version = version
        self.hostname = socket.gethostname()
        self.pid = str(psutil.Process().pid)
        
    def format(self, record: logging.LogRecord) -> str:
        """Format log record as structured JSON"""
        # Base log structure
        log_entry = {
            "timestamp": datetime.fromtimestamp(record.created, tz=timezone.utc).isoformat(),
            "level": record.levelname.lower(),
            "message": record.getMessage(),
            "service": self.service_name,
            "version": self.version,
            "hostname": self.hostname,
            "pid": self.pid,
            "thread": record.thread,
            "thread_name": record.threadName,
            "logger_name": record.name,
            "module": record.module,
            "function": record.funcName,
            "line": record.lineno,
            "correlation_id": getattr(record, 'correlation_id', str(uuid.uuid4()))
        }
        
        # Add exception info if present
        if record.exc_info:
            log_entry["exception"] = {
                "type": record.exc_info[0].__name__ if record.exc_info[0] else None,
                "message": str(record.exc_info[1]) if record.exc_info[1] else None,
                "stack_trace": traceback.format_exception(*record.exc_info)
            }
        
        # Add custom context if present
        if hasattr(record, 'context') and record.context:
            if isinstance(record.context, LogContext):
                log_entry["context"] = record.context.to_dict()
            elif isinstance(record.context, dict):
                log_entry["context"] = record.context
        
        # Add system metrics in production
        if hasattr(record, 'include_system_metrics') and record.include_system_metrics:
            try:
                process = psutil.Process()
                memory = process.memory_info()
                log_entry["system"] = {
                    "memory": {
                        "rss": round(memory.rss / 1024 / 1024, 2),  # MB
                        "vms": round(memory.vms / 1024 / 1024, 2),  # MB
                        "percent": round(process.memory_percent(), 2)
                    },
                    "cpu": {
                        "percent": round(process.cpu_percent(), 2),
                        "num_threads": process.num_threads()
                    }
                }
            except Exception:
                pass  # Ignore system metrics errors
        
        return json.dumps(log_entry, ensure_ascii=False)


class Logger:
    """
    Enterprise Logger with structured logging, multiple transports, and correlation IDs
    
    Features:
    - Structured JSON logging with correlation IDs
    - Multiple transports (console, file, rotating file)
    - Log rotation and archiving (5MB files, 5 file retention)
    - System resource monitoring
    - Performance profiling capabilities
    - Thread-safe operations
    - Configurable log levels and formats
    """
    
    _instance: Optional['Logger'] = None
    _lock = threading.Lock()
    
    def __init__(self, 
                 service_name: str = "dafelhub",
                 version: str = "1.0.0",
                 log_level: LogLevel = LogLevel.INFO,
                 log_dir: str = "logs",
                 max_file_size: int = 5 * 1024 * 1024,  # 5MB
                 backup_count: int = 5,
                 include_system_metrics: bool = True):
        
        self.service_name = service_name
        self.version = version
        self.log_level = log_level
        self.log_dir = Path(log_dir)
        self.max_file_size = max_file_size
        self.backup_count = backup_count
        self.include_system_metrics = include_system_metrics
        
        # Ensure log directory exists
        self.log_dir.mkdir(exist_ok=True)
        
        # Create correlation ID filter
        self.correlation_filter = CorrelationIdFilter()
        
        # Initialize logger
        self._setup_logger()
    
    @classmethod
    def get_instance(cls, **kwargs) -> 'Logger':
        """Get singleton instance with thread safety"""
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = cls(**kwargs)
        return cls._instance
    
    def _setup_logger(self):
        """Setup logger with multiple transports"""
        # Create main logger
        self.logger = logging.getLogger(self.service_name)
        self.logger.setLevel(getattr(logging, self.log_level.value.upper()))
        
        # Clear existing handlers
        self.logger.handlers.clear()
        
        # Add correlation ID filter to all handlers
        formatter = EnterpriseFormatter(self.service_name, self.version)
        
        # Console handler for development
        console_handler = logging.StreamHandler()
        console_handler.setLevel(logging.DEBUG)
        console_handler.setFormatter(formatter)
        console_handler.addFilter(self.correlation_filter)
        self.logger.addHandler(console_handler)
        
        # Rotating file handler for all logs
        combined_file = self.log_dir / "combined.log"
        combined_handler = logging.handlers.RotatingFileHandler(
            combined_file,
            maxBytes=self.max_file_size,
            backupCount=self.backup_count,
            encoding='utf-8'
        )
        combined_handler.setLevel(logging.DEBUG)
        combined_handler.setFormatter(formatter)
        combined_handler.addFilter(self.correlation_filter)
        self.logger.addHandler(combined_handler)
        
        # Error file handler for errors only
        error_file = self.log_dir / "error.log"
        error_handler = logging.handlers.RotatingFileHandler(
            error_file,
            maxBytes=self.max_file_size,
            backupCount=self.backup_count,
            encoding='utf-8'
        )
        error_handler.setLevel(logging.ERROR)
        error_handler.setFormatter(formatter)
        error_handler.addFilter(self.correlation_filter)
        self.logger.addHandler(error_handler)
        
        # HTTP/Access log handler
        http_file = self.log_dir / "http.log"
        self.http_logger = logging.getLogger(f"{self.service_name}.http")
        self.http_logger.setLevel(logging.INFO)
        http_handler = logging.handlers.RotatingFileHandler(
            http_file,
            maxBytes=self.max_file_size,
            backupCount=self.backup_count,
            encoding='utf-8'
        )
        http_handler.setFormatter(formatter)
        http_handler.addFilter(self.correlation_filter)
        self.http_logger.addHandler(http_handler)
        self.http_logger.propagate = False
    
    def _log(self, level: LogLevel, message: str, context: Optional[Union[LogContext, Dict]] = None, **kwargs):
        """Internal logging method"""
        # Convert string level to logging level
        level_map = {
            LogLevel.ERROR: logging.ERROR,
            LogLevel.WARN: logging.WARNING,
            LogLevel.INFO: logging.INFO,
            LogLevel.HTTP: logging.INFO,
            LogLevel.VERBOSE: logging.INFO,
            LogLevel.DEBUG: logging.DEBUG,
            LogLevel.SILLY: logging.DEBUG
        }
        
        log_level = level_map.get(level, logging.INFO)
        
        # Create extra dict for structured data
        extra = {
            'context': context,
            'include_system_metrics': self.include_system_metrics and level == LogLevel.ERROR
        }
        extra.update(kwargs)
        
        # Choose logger based on level
        if level == LogLevel.HTTP:
            self.http_logger.log(log_level, message, extra=extra)
        else:
            self.logger.log(log_level, message, extra=extra)
    
    def error(self, message: str, context: Optional[Union[LogContext, Dict]] = None, **kwargs):
        """Log error message"""
        self._log(LogLevel.ERROR, message, context, **kwargs)
    
    def warn(self, message: str, context: Optional[Union[LogContext, Dict]] = None, **kwargs):
        """Log warning message"""
        self._log(LogLevel.WARN, message, context, **kwargs)
    
    def info(self, message: str, context: Optional[Union[LogContext, Dict]] = None, **kwargs):
        """Log info message"""
        self._log(LogLevel.INFO, message, context, **kwargs)
    
    def http(self, message: str, context: Optional[Union[LogContext, Dict]] = None, **kwargs):
        """Log HTTP request/response"""
        self._log(LogLevel.HTTP, message, context, **kwargs)
    
    def verbose(self, message: str, context: Optional[Union[LogContext, Dict]] = None, **kwargs):
        """Log verbose message"""
        self._log(LogLevel.VERBOSE, message, context, **kwargs)
    
    def debug(self, message: str, context: Optional[Union[LogContext, Dict]] = None, **kwargs):
        """Log debug message"""
        self._log(LogLevel.DEBUG, message, context, **kwargs)
    
    def silly(self, message: str, context: Optional[Union[LogContext, Dict]] = None, **kwargs):
        """Log silly/trace message"""
        self._log(LogLevel.SILLY, message, context, **kwargs)
    
    def child(self, context: Union[LogContext, Dict]) -> 'ChildLogger':
        """Create child logger with additional context"""
        return ChildLogger(self, context)
    
    @contextmanager
    def correlation_context(self, correlation_id: str = None):
        """Context manager for correlation ID"""
        if correlation_id is None:
            correlation_id = str(uuid.uuid4())
        
        old_id = self.correlation_filter.get_correlation_id()
        self.correlation_filter.set_correlation_id(correlation_id)
        try:
            yield correlation_id
        finally:
            self.correlation_filter.set_correlation_id(old_id)
    
    async def profile_async(self, 
                           label: str, 
                           func: Callable, 
                           context: Optional[Union[LogContext, Dict]] = None,
                           *args, **kwargs):
        """Profile async function execution"""
        profile_id = str(uuid.uuid4())
        start_time = time.time()
        
        profile_context = LogContext(
            correlation_id=self.correlation_filter.get_correlation_id(),
            operation=label,
            component="profiler"
        )
        if isinstance(context, LogContext):
            profile_context.user_id = context.user_id
            profile_context.request_id = context.request_id
            profile_context.session_id = context.session_id
        
        self.debug(f"Starting profile: {label}", {
            **profile_context.to_dict(),
            "profile_id": profile_id,
            "profile_label": label
        })
        
        try:
            if asyncio.iscoroutinefunction(func):
                result = await func(*args, **kwargs)
            else:
                result = func(*args, **kwargs)
            
            duration = time.time() - start_time
            profile_context.duration = duration
            profile_context.status = "success"
            
            self.debug(f"Profile complete: {label}", {
                **profile_context.to_dict(),
                "profile_id": profile_id,
                "profile_label": label,
                "duration_ms": duration * 1000
            })
            
            return result
            
        except Exception as error:
            duration = time.time() - start_time
            profile_context.duration = duration
            profile_context.status = "failure"
            profile_context.error_type = type(error).__name__
            
            self.error(f"Profile failed: {label}", {
                **profile_context.to_dict(),
                "profile_id": profile_id,
                "profile_label": label,
                "duration_ms": duration * 1000,
                "error_message": str(error)
            })
            
            raise
    
    def profile(self, 
               label: str, 
               func: Callable, 
               context: Optional[Union[LogContext, Dict]] = None,
               *args, **kwargs):
        """Profile function execution"""
        profile_id = str(uuid.uuid4())
        start_time = time.time()
        
        profile_context = LogContext(
            correlation_id=self.correlation_filter.get_correlation_id(),
            operation=label,
            component="profiler"
        )
        if isinstance(context, LogContext):
            profile_context.user_id = context.user_id
            profile_context.request_id = context.request_id
            profile_context.session_id = context.session_id
        
        self.debug(f"Starting profile: {label}", {
            **profile_context.to_dict(),
            "profile_id": profile_id,
            "profile_label": label
        })
        
        try:
            result = func(*args, **kwargs)
            
            duration = time.time() - start_time
            profile_context.duration = duration
            profile_context.status = "success"
            
            self.debug(f"Profile complete: {label}", {
                **profile_context.to_dict(),
                "profile_id": profile_id,
                "profile_label": label,
                "duration_ms": duration * 1000
            })
            
            return result
            
        except Exception as error:
            duration = time.time() - start_time
            profile_context.duration = duration
            profile_context.status = "failure"
            profile_context.error_type = type(error).__name__
            
            self.error(f"Profile failed: {label}", {
                **profile_context.to_dict(),
                "profile_id": profile_id,
                "profile_label": label,
                "duration_ms": duration * 1000,
                "error_message": str(error)
            })
            
            raise
    
    @contextmanager
    def timer_context(self, label: str, context: Optional[Union[LogContext, Dict]] = None):
        """Context manager for timing operations"""
        start_time = time.time()
        try:
            yield
        finally:
            duration = time.time() - start_time
            timer_context = context or {}
            if isinstance(timer_context, LogContext):
                timer_context.duration = duration
                self.info(f"Timer complete: {label}", timer_context)
            else:
                timer_context["duration_ms"] = duration * 1000
                self.info(f"Timer complete: {label}", timer_context)
    
    def start_timer(self) -> Callable[[], float]:
        """Start a timer and return function to get elapsed time"""
        start_time = time.time()
        return lambda: time.time() - start_time
    
    def set_level(self, level: LogLevel):
        """Set logging level dynamically"""
        self.log_level = level
        self.logger.setLevel(getattr(logging, level.value.upper()))
    
    def get_level(self) -> LogLevel:
        """Get current logging level"""
        return self.log_level
    
    def add_transport(self, handler: logging.Handler):
        """Add custom transport handler"""
        handler.addFilter(self.correlation_filter)
        self.logger.addHandler(handler)
    
    def remove_transport(self, handler: logging.Handler):
        """Remove transport handler"""
        self.logger.removeHandler(handler)
    
    def clear_transports(self):
        """Clear all transport handlers"""
        self.logger.handlers.clear()
        
    def flush(self):
        """Flush all handlers"""
        for handler in self.logger.handlers:
            if hasattr(handler, 'flush'):
                handler.flush()


class ChildLogger:
    """Child logger with inherited context"""
    
    def __init__(self, parent: Logger, context: Union[LogContext, Dict]):
        self.parent = parent
        self.context = context
    
    def _merge_context(self, additional_context: Optional[Union[LogContext, Dict]] = None):
        """Merge child context with additional context"""
        if additional_context is None:
            return self.context
        
        if isinstance(self.context, LogContext) and isinstance(additional_context, LogContext):
            merged = LogContext(**self.context.to_dict())
            for key, value in additional_context.to_dict().items():
                if value is not None:
                    setattr(merged, key, value)
            return merged
        elif isinstance(self.context, dict) and isinstance(additional_context, dict):
            return {**self.context, **additional_context}
        else:
            # Convert to dict and merge
            base_dict = self.context.to_dict() if isinstance(self.context, LogContext) else self.context
            add_dict = additional_context.to_dict() if isinstance(additional_context, LogContext) else additional_context
            return {**base_dict, **add_dict}
    
    def error(self, message: str, context: Optional[Union[LogContext, Dict]] = None, **kwargs):
        self.parent.error(message, self._merge_context(context), **kwargs)
    
    def warn(self, message: str, context: Optional[Union[LogContext, Dict]] = None, **kwargs):
        self.parent.warn(message, self._merge_context(context), **kwargs)
    
    def info(self, message: str, context: Optional[Union[LogContext, Dict]] = None, **kwargs):
        self.parent.info(message, self._merge_context(context), **kwargs)
    
    def http(self, message: str, context: Optional[Union[LogContext, Dict]] = None, **kwargs):
        self.parent.http(message, self._merge_context(context), **kwargs)
    
    def verbose(self, message: str, context: Optional[Union[LogContext, Dict]] = None, **kwargs):
        self.parent.verbose(message, self._merge_context(context), **kwargs)
    
    def debug(self, message: str, context: Optional[Union[LogContext, Dict]] = None, **kwargs):
        self.parent.debug(message, self._merge_context(context), **kwargs)
    
    def silly(self, message: str, context: Optional[Union[LogContext, Dict]] = None, **kwargs):
        self.parent.silly(message, self._merge_context(context), **kwargs)


# Global logger instance
_global_logger: Optional[Logger] = None


def get_logger(**kwargs) -> Logger:
    """Get global logger instance"""
    global _global_logger
    if _global_logger is None:
        _global_logger = Logger.get_instance(**kwargs)
    return _global_logger