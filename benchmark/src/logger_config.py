"""Logging configuration for SEQUEL2SQL Benchmark"""

import logging
import sys
from datetime import datetime
from logging.handlers import RotatingFileHandler
from pathlib import Path

from rich.console import Console
from rich.logging import RichHandler

from .config import get_logs_dir


def setup_logger(run_timestamp: str) -> logging.Logger:
    """
    Setup dual logging: console (rich) + rotating file.

    Args:
        run_timestamp: Timestamp string for the log filename (e.g., "2026-02-02_14-30-45")

    Returns:
        Configured logger instance
    """
    # Create logger
    logger = logging.getLogger("sequel2sql")
    logger.setLevel(logging.DEBUG)

    # Remove existing handlers to avoid duplicates
    logger.handlers.clear()

    # Console handler with Rich
    console_handler = RichHandler(
        rich_tracebacks=True,
        markup=True,
        show_time=True,
        show_path=False,
        console=Console(stderr=True),
    )
    console_handler.setLevel(logging.INFO)
    console_format = logging.Formatter("%(message)s", datefmt="[%X]")
    console_handler.setFormatter(console_format)

    # File handler with rotation
    logs_dir = get_logs_dir()
    logs_dir.mkdir(parents=True, exist_ok=True)

    log_file = logs_dir / f"benchmark_{run_timestamp}.log"
    file_handler = RotatingFileHandler(
        log_file,
        maxBytes=10 * 1024 * 1024,  # 10 MB
        backupCount=5,
        encoding="utf-8",
    )
    file_handler.setLevel(logging.DEBUG)
    file_format = logging.Formatter(
        "%(asctime)s | %(levelname)-8s | %(name)s:%(lineno)d | %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )
    file_handler.setFormatter(file_format)

    # Add handlers
    logger.addHandler(console_handler)
    logger.addHandler(file_handler)

    logger.info(f"Logging initialized - Log file: {log_file}")

    return logger


def get_logger() -> logging.Logger:
    """Get the configured logger instance."""
    return logging.getLogger("sequel2sql")


if __name__ == "__main__":
    # Test logging
    timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
    logger = setup_logger(timestamp)

    logger.debug("This is a DEBUG message")
    logger.info("This is an INFO message")
    logger.warning("This is a WARNING message")
    logger.error("This is an ERROR message")
    logger.critical("This is a CRITICAL message")

    print("\n✓ Logging test complete!")
