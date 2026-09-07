"""
Structured logging formatters.

Provides:
- JSON formatter for production/file logging
- Colored console formatter for development
- Context-aware formatting
"""

import json
import logging
import traceback
from datetime import datetime, timezone
from typing import Any, Dict, Optional

from .context import get_log_context


class StructuredJSONFormatter(logging.Formatter):
    """
    JSON formatter for structured logging.
    
    Outputs logs in JSON format with:
    - Timestamp (ISO 8601)
    - Level
    - Logger name
    - Message
    - Context (request_id, user_id, etc.)
    - Exception details (if any)
    - Extra fields
    """
    
    def __init__(self, include_timestamp: bool = True):
        super().__init__()
        self.include_timestamp = include_timestamp
    
    def format(self, record: logging.LogRecord) -> str:
        """Format log record as JSON."""
        log_data = {
            'level': record.levelname,
            'logger': record.name,
            'message': record.getMessage(),
            'module': record.module,
            'function': record.funcName,
            'line': record.lineno,
        }
        
        # Add timestamp
        if self.include_timestamp:
            log_data['timestamp'] = datetime.fromtimestamp(
                record.created, tz=timezone.utc
            ).isoformat()
        
        # Add context (request_id, user_id, etc.)
        context = get_log_context()
        if context:
            log_data['context'] = context
        
        # Add exception info if present
        if record.exc_info:
            log_data['exception'] = {
                'type': record.exc_info[0].__name__ if record.exc_info[0] else None,
                'message': str(record.exc_info[1]) if record.exc_info[1] else None,
                'traceback': self.formatException(record.exc_info) if record.exc_info else None,
            }
        
        # Add extra fields (custom attributes)
        for key, value in record.__dict__.items():
            if key not in {
                'name', 'msg', 'args', 'created', 'relativeCreated',
                'exc_info', 'exc_text', 'stack_info', 'lineno', 'funcName',
                'filename', 'module', 'pathname', 'thread', 'threadName',
                'process', 'processName', 'levelname', 'levelno', 'message',
                'msecs',
            }:
                log_data[key] = value
        
        return json.dumps(log_data, ensure_ascii=False, default=str)


class ColoredConsoleFormatter(logging.Formatter):
    """
    Colored console formatter for development.
    
    Outputs human-readable logs with colors:
    - DEBUG: Cyan
    - INFO: Green
    - WARNING: Yellow
    - ERROR: Red
    - CRITICAL: Magenta (bold)
    """
    
    # ANSI color codes
    COLORS = {
        'DEBUG': '\033[36m',     # Cyan
        'INFO': '\033[32m',      # Green
        'WARNING': '\033[33m',   # Yellow
        'ERROR': '\033[31m',     # Red
        'CRITICAL': '\033[35m',  # Magenta
    }
    RESET = '\033[0m'
    BOLD = '\033[1m'
    
    def __init__(self, use_colors: bool = True):
        super().__init__()
        self.use_colors = use_colors
    
    def format(self, record: logging.LogRecord) -> str:
        """Format log record for console output."""
        # Base format
        timestamp = datetime.fromtimestamp(record.created).strftime('%H:%M:%S')
        level = record.levelname
        
        # Apply colors
        if self.use_colors:
            color = self.COLORS.get(level, '')
            reset = self.RESET
            if level == 'CRITICAL':
                level = f"{self.BOLD}{color}{level}{reset}"
            else:
                level = f"{color}{level}{reset}"
        
        # Build message
        msg = record.getMessage()
        
        # Add context if available
        context = get_log_context()
        context_str = ''
        if context:
            parts = []
            if 'request_id' in context:
                parts.append(f"req={context['request_id']}")
            if 'user_id' in context:
                parts.append(f"user={context['user_id'][:8]}...")
            if 'correlation_id' in context:
                parts.append(f"cor={context['correlation_id']}")
            if parts:
                context_str = f" [{', '.join(parts)}]"
        
        # Format exception if present
        exc_str = ''
        if record.exc_info:
            exc_str = '\n' + self.formatException(record.exc_info)
        
        return f"{timestamp} | {level:8} | {record.name:20} | {msg}{context_str}{exc_str}"


class SimpleConsoleFormatter(logging.Formatter):
    """Simple console formatter without colors (for non-TTY outputs)."""
    
    def format(self, record: logging.LogRecord) -> str:
        """Format log record as simple text."""
        timestamp = datetime.fromtimestamp(record.created).strftime('%Y-%m-%d %H:%M:%S')
        msg = record.getMessage()
        
        # Add context
        context = get_log_context()
        context_str = ''
        if context:
            parts = []
            if 'request_id' in context:
                parts.append(f"request_id={context['request_id']}")
            if 'user_id' in context:
                parts.append(f"user_id={context['user_id']}")
            if parts:
                context_str = f" | {' | '.join(parts)}"
        
        exc_str = ''
        if record.exc_info:
            exc_str = '\n' + self.formatException(record.exc_info)
        
        return f"{timestamp} | {record.levelname:8} | {record.name:20} | {msg}{context_str}{exc_str}"
