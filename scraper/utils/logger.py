"""
Fundametrics Scraper - Advanced Logging Utility
=========================================

Production-ready logging setup using Loguru with:
- Console and file logging
- Automatic log rotation
- JSON logging support
- Contextual logging
- Performance tracking
"""

import sys
from pathlib import Path
from typing import Optional
from loguru import logger
import yaml


class LoggerSetup:
    """Configure and manage application logging"""
    
    def __init__(self, config_path: Optional[str] = None):
        """
        Initialize logger with configuration
        
        Args:
            config_path: Path to settings.yaml file
        """
        self.config = self._load_config(config_path)
        self._setup_logger()
    
    def _load_config(self, config_path: Optional[str] = None) -> dict:
        """Load logging configuration from YAML"""
        if config_path is None:
            config_path = Path(__file__).parent.parent.parent / "config" / "settings.yaml"
        
        try:
            with open(config_path, 'r') as f:
                config = yaml.safe_load(f)
                return config.get('logging', {})
        except FileNotFoundError:
            # Return default config if file not found
            return self._default_config()
    
    def _default_config(self) -> dict:
        """Default logging configuration"""
        return {
            'level': 'INFO',
            'format': '<green>{time:YYYY-MM-DD HH:mm:ss}</green> | <level>{level: <8}</level> | <cyan>{name}</cyan>:<cyan>{function}</cyan>:<cyan>{line}</cyan> - <level>{message}</level>',
            'console': {'enabled': True, 'colorize': True},
            'file': {
                'enabled': True,
                'path': './logs/fundametrics-scraper.log',
                'rotation': '500 MB',
                'retention': '30 days',
                'compression': 'zip'
            },
            'error_file': {
                'enabled': True,
                'path': './logs/errors.log',
                'level': 'ERROR',
                'rotation': '100 MB',
                'retention': '90 days'
            },
            'json': {
                'enabled': False,
                'path': './logs/fundametrics-scraper.json'
            }
        }
    
    def _setup_logger(self):
        """Configure loguru logger"""
        # Remove default handler
        logger.remove()
        
        # Get log level
        log_level = self.config.get('level', 'INFO')
        log_format = self.config.get('format')
        
        # Console logging
        console_config = self.config.get('console', {})
        if console_config.get('enabled', True):
            logger.add(
                sys.stderr,
                format=log_format,
                level=log_level,
                colorize=console_config.get('colorize', True),
                backtrace=True,
                diagnose=True
            )
        
        # File logging
        file_config = self.config.get('file', {})
        if file_config.get('enabled', True):
            log_path = Path(file_config.get('path', './logs/fundametrics-scraper.log'))
            log_path.parent.mkdir(parents=True, exist_ok=True)
            
            logger.add(
                log_path,
                format=log_format,
                level=log_level,
                rotation=file_config.get('rotation', '500 MB'),
                retention=file_config.get('retention', '30 days'),
                compression=file_config.get('compression', 'zip'),
                backtrace=True,
                diagnose=True
            )
        
        # Error file logging
        error_config = self.config.get('error_file', {})
        if error_config.get('enabled', True):
            error_path = Path(error_config.get('path', './logs/errors.log'))
            error_path.parent.mkdir(parents=True, exist_ok=True)
            
            logger.add(
                error_path,
                format=log_format,
                level=error_config.get('level', 'ERROR'),
                rotation=error_config.get('rotation', '100 MB'),
                retention=error_config.get('retention', '90 days'),
                backtrace=True,
                diagnose=True
            )
        
        # JSON logging (for log aggregation systems)
        json_config = self.config.get('json', {})
        if json_config.get('enabled', False):
            json_path = Path(json_config.get('path', './logs/fundametrics-scraper.json'))
            json_path.parent.mkdir(parents=True, exist_ok=True)
            
            logger.add(
                json_path,
                format="{message}",
                level=log_level,
                serialize=True,  # JSON format
                rotation=file_config.get('rotation', '500 MB'),
                retention=file_config.get('retention', '30 days')
            )
    
    def get_logger(self, name: Optional[str] = None):
        """
        Get a logger instance
        
        Args:
            name: Logger name (usually __name__)
        
        Returns:
            Configured logger instance
        """
        if name:
            return logger.bind(name=name)
        return logger


# Global logger instance
_logger_setup = None


def setup_logging(config_path: Optional[str] = None):
    """
    Initialize logging system
    
    Args:
        config_path: Path to settings.yaml file
    """
    global _logger_setup
    _logger_setup = LoggerSetup(config_path)
    logger.info("Logging system initialized")


def get_logger(name: Optional[str] = None):
    """
    Get a logger instance
    
    Args:
        name: Logger name (usually __name__)
    
    Returns:
        Configured logger instance
    
    Example:
        >>> from scraper.utils.logger import get_logger
        >>> log = get_logger(__name__)
        >>> log.info("Starting scraper")
    """
    global _logger_setup
    if _logger_setup is None:
        setup_logging()
    return _logger_setup.get_logger(name)


# Convenience functions
def log_function_call(func):
    """
    Decorator to log function calls
    
    Example:
        >>> @log_function_call
        >>> def scrape_stock(symbol):
        >>>     pass
    """
    from functools import wraps
    
    @wraps(func)
    def wrapper(*args, **kwargs):
        log = get_logger(func.__module__)
        log.debug(f"Calling {func.__name__} with args={args}, kwargs={kwargs}")
        try:
            result = func(*args, **kwargs)
            log.debug(f"{func.__name__} completed successfully")
            return result
        except Exception as e:
            log.error(f"{func.__name__} failed: {e}")
            raise
    
    return wrapper


def log_execution_time(func):
    """
    Decorator to log function execution time
    
    Example:
        >>> @log_execution_time
        >>> def slow_function():
        >>>     time.sleep(2)
    """
    from functools import wraps
    import time
    
    @wraps(func)
    def wrapper(*args, **kwargs):
        log = get_logger(func.__module__)
        start_time = time.time()
        try:
            result = func(*args, **kwargs)
            elapsed = time.time() - start_time
            log.info(f"{func.__name__} executed in {elapsed:.2f}s")
            return result
        except Exception as e:
            elapsed = time.time() - start_time
            log.error(f"{func.__name__} failed after {elapsed:.2f}s: {e}")
            raise
    
    return wrapper


# Example usage
if __name__ == "__main__":
    # Initialize logging
    setup_logging()
    
    # Get logger
    log = get_logger(__name__)
    
    # Test different log levels
    log.debug("This is a debug message")
    log.info("This is an info message")
    log.warning("This is a warning message")
    log.error("This is an error message")
    log.critical("This is a critical message")
    
    # Test decorator
    @log_execution_time
    def test_function():
        import time
        time.sleep(1)
        return "Done"
    
    test_function()
