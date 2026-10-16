"""
Centralized Logging Configuration

Provides consistent logging across the entire application.

Naming note: this module is ``utils.logging``. Inside it, ``import logging``
still resolves to the standard library (absolute imports, and ``utils/`` is not
on sys.path itself), so the clash is harmless at runtime -- import it as
``from utils.logging import get_logger`` to keep the two apart when reading.
"""

import logging
import logging.handlers
import sys
from pathlib import Path
from typing import Optional
from utils.config import get_config
from utils.constants import LOG_DIR, LOG_FORMAT

# Global logger instance
_logger: Optional[logging.Logger] = None


def setup_logging(
    name: str = "qubika",
    level: Optional[str] = None,
    log_file: Optional[str] = None,
) -> logging.Logger:
    """
    Set up logging with console and optional file handlers.
    
    Args:
        name: Logger name
        level: Logging level (DEBUG, INFO, WARNING, ERROR, CRITICAL)
        log_file: Optional file path for logging
    
    Returns:
        Configured logger instance
    """
    config = get_config()
    level = level or config.log_level
    
    logger = logging.getLogger(name)
    logger.setLevel(getattr(logging, level))
    
    # Avoid duplicate handlers
    if logger.handlers:
        return logger
    
    # Console handler
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(getattr(logging, level))
    console_formatter = logging.Formatter(LOG_FORMAT)
    console_handler.setFormatter(console_formatter)
    logger.addHandler(console_handler)
    
    # File handler (optional)
    if log_file or (config.debug and log_file is None):
        log_file = log_file or f"{LOG_DIR}/{name}.log"
        Path(LOG_DIR).mkdir(parents=True, exist_ok=True)
        
        file_handler = logging.handlers.RotatingFileHandler(
            log_file,
            maxBytes=10_000_000,  # 10MB
            backupCount=5
        )
        file_handler.setLevel(getattr(logging, level))
        file_formatter = logging.Formatter(LOG_FORMAT)
        file_handler.setFormatter(file_formatter)
        logger.addHandler(file_handler)
    
    return logger


def get_logger(name: str) -> logging.Logger:
    """
    Get a logger instance with the given name.
    
    Args:
        name: Logger name (typically __name__)
    
    Returns:
        Logger instance
    """
    return setup_logging(name)


def configure_app_logging(level: Optional[str] = None) -> logging.Logger:
    """
    Configure main application logger.
    
    Args:
        level: Logging level
    
    Returns:
        Root logger
    """
    global _logger
    config = get_config()
    _logger = setup_logging("qubika", level or config.log_level)
    return _logger


def get_app_logger() -> logging.Logger:
    """Get the main application logger."""
    global _logger
    if _logger is None:
        _logger = configure_app_logging()
    return _logger


# Convenience decorators

def log_execution(logger: Optional[logging.Logger] = None):
    """
    Decorator to log function execution with timing.
    
    Args:
        logger: Optional logger instance (defaults to app logger)
    """
    import functools
    import time
    
    def decorator(func):
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            log = logger or get_app_logger()
            func_name = func.__name__
            
            log.debug(f"Executing: {func_name}")
            start_time = time.time()
            
            try:
                result = func(*args, **kwargs)
                elapsed = time.time() - start_time
                log.debug(f"Completed: {func_name} ({elapsed:.2f}s)")
                return result
            except Exception as e:
                elapsed = time.time() - start_time
                log.error(f"Failed: {func_name} ({elapsed:.2f}s) - {e}", exc_info=True)
                raise
        
        return wrapper
    return decorator


def suppress_logs(module_name: str, level: int = logging.WARNING) -> None:
    """
    Suppress logs from a specific module.
    
    Args:
        module_name: Name of module to suppress (e.g., "urllib3")
        level: Minimum level to log
    """
    logging.getLogger(module_name).setLevel(level)


__all__ = [
    "setup_logging",
    "get_logger",
    "configure_app_logging",
    "get_app_logger",
    "log_execution",
    "suppress_logs",
]
