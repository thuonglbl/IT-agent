"""
Centralized logging configuration for migrations
Supports console and file logging with configurable levels
"""
import logging
import os
from datetime import datetime


def create_log_directory(log_path):
    """
    Ensure log directory exists.

    Args:
        log_path: Path to log file
    """
    log_dir = os.path.dirname(log_path)
    if log_dir and not os.path.exists(log_dir):
        os.makedirs(log_dir, exist_ok=True)


def setup_logger(name, config):
    """
    Setup logger with console and file handlers based on configuration.

    Args:
        name: Logger name (e.g., "migration")
        config: Configuration dictionary containing logging settings

    Returns:
        logging.Logger: Configured logger instance

    Configuration Example:
        {
            "logging": {
                "level": "INFO",           # DEBUG, INFO, WARNING, ERROR, CRITICAL
                "console": true,            # Enable console output
                "file": true,               # Enable file output
                "file_path": "logs/migration_{timestamp}.log",
                "format": "%(asctime)s [%(levelname)s] %(name)s: %(message)s"
            }
        }

    Log Levels:
        - DEBUG: Field extraction details, mapping logic
        - INFO: Processing start/end, batch progress
        - WARNING: Missing users, fallback mappings
        - ERROR: API failures, validation errors
        - CRITICAL: Fatal errors that stop migration
    """
    logger = logging.getLogger(name)

    # Get logging config with defaults
    logging_config = config.get('logging', {})
    log_level = logging_config.get('level', 'INFO').upper()
    console_enabled = logging_config.get('console', True)
    file_enabled = logging_config.get('file', True)
    log_file_path = logging_config.get('file_path', 'logs/migration_{timestamp}.log')
    log_format = logging_config.get('format', '%(asctime)s [%(levelname)s] %(name)s: %(message)s')

    # Set logger level
    logger.setLevel(getattr(logging, log_level, logging.INFO))

    # Clear existing handlers
    logger.handlers = []

    # Create formatter
    formatter = logging.Formatter(log_format)

    # Console handler
    if console_enabled:
        console_handler = logging.StreamHandler()
        console_handler.setLevel(logging.INFO)
        console_handler.setFormatter(formatter)
        logger.addHandler(console_handler)

    # File handler
    if file_enabled:
        # Replace {timestamp} with actual timestamp
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        log_file = log_file_path.replace('{timestamp}', timestamp)

        # Create log directory
        create_log_directory(log_file)

        file_handler = logging.FileHandler(log_file, encoding='utf-8')
        file_handler.setLevel(logging.DEBUG)
        file_handler.setFormatter(formatter)
        logger.addHandler(file_handler)

        logger.info(f"Log file: {os.path.abspath(log_file)}")

    return logger


def get_logger(name):
    """
    Get a child logger for a specific module.

    Args:
        name: Module name (e.g., "field_extractor", "html_builder")

    Returns:
        logging.Logger: Child logger instance
    """
    return logging.getLogger(f"migration.{name}")


class MigrationLogger:
    """
    Migration logger wrapper class.

    Provides a class-based interface for logging with child logger support.
    """

    def __init__(self, name, config):
        """
        Initialize migration logger.

        Args:
            name: Logger name
            config: Configuration dictionary
        """
        self.logger = setup_logger(name, config)
        self.name = name

    def get_child(self, child_name):
        """
        Get a child logger.

        Args:
            child_name: Child logger name

        Returns:
            logging.Logger: Child logger instance
        """
        return logging.getLogger(f"{self.name}.{child_name}")

    def debug(self, message):
        """Log debug message."""
        self.logger.debug(message)

    def info(self, message):
        """Log info message."""
        self.logger.info(message)

    def warning(self, message):
        """Log warning message."""
        self.logger.warning(message)

    def error(self, message, exc_info=False):
        """Log error message."""
        self.logger.error(message, exc_info=exc_info)

    def critical(self, message, exc_info=False):
        """Log critical message."""
        self.logger.critical(message, exc_info=exc_info)
