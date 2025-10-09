from __future__ import annotations

import os 
import logging as _logging 
from logging.handlers import RotatingFileHandler
from typing import Optional 

# Guard so setup runs only once even if imported multiple times 
_CONFIGURED = False 

def setup_logging(
        level: int = _logging.INFO,
        fmt: str = "%(asctime)s %(levelname)s %(name)s %(message)s",
        logfile: Optional[str] = None,
        max_bytes: int = 5_000_000,
        backup_count: int = 3
) -> None:
    """
    Configure root logging once. Safe to call multipe times later 
    - level: logging level (e.g., _logging.INFO)
    - fmt: log line format
    - logfile: if provided, also log to a rotating file
    - max_bytes/backup_count: rotation settings
    """
    global _CONFIGURED
    if _CONFIGURED:
        return 
    
    handlers: list[_logging.Handler] = []

     # Console handler
    stream = _logging.StreamHandler()
    stream.setFormatter(_logging.Formatter(fmt))
    handlers.append(stream)

    # Optional rotating file handler
    if logfile:
        logdir = os.path.dirname(logfile)
        if logdir:
            os.makedirs(logdir, exist_ok=True)
        file_handler = RotatingFileHandler(
            logfile, maxBytes=max_bytes, backupCount=backup_count
        )
        file_handler.setFormatter(_logging.Formatter(fmt))
        handlers.append(file_handler)

    _logging.basicConfig(level=level, handlers=handlers)
    _CONFIGURED = True

def get_logger(name: Optional[str] = None) -> _logging.Logger:
    """
    Returns a logger. Ensures setup has run.
    Usage: logger = get_logger("markitdown-endpoint")
    """
    if not _CONFIGURED:
        setup_logging()
    return _logging.getLogger(name or "app")