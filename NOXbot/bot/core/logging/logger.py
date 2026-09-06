"""
Centralized logging configuration and event logging API.

Provides:
- Centralized logger setup
- Event logging helpers
- Category-based logging (payment, wallet, security, etc.)
- Performance tracking
"""

import logging
import sys
import time
from functools import wraps
from pathlib import Path
from typing import Any, Callable, Dict, Optional, TypeVar

from .context import (
    get_log_context,
    get_request_id,
    get_correlation_id,
    generate_error_id,
)
from .sensitive import sanitize_dict
from .formatters import (
    StructuredJSONFormatter,
    ColoredConsoleFormatter,
    SimpleConsoleFormatter,
)


F = TypeVar('F', bound=Callable)


# ============================================================================
# Logger Configuration
# ============================================================================

def setup_logging(
    log_level: str = 'INFO',
    log_dir: Optional[str] = None,
    max_bytes: int = 10 * 1024 * 1024,  # 10 MB
    backup_count: int = 5,
    use_json: bool = False,
    use_colors: bool = True,
) -> None:
    """
    Configure the logging system.
    
    Args:
        log_level: Minimum log level (DEBUG, INFO, WARNING, ERROR, CRITICAL)
        log_dir: Directory for log files (None = console only)
        max_bytes: Max size per log file before rotation
        backup_count: Number of backup files to keep
        use_json: Use JSON formatter for console (default: colored text)
        use_colors: Use colors in console output
    """
    root_logger = logging.getLogger()
    root_logger.setLevel(getattr(logging, log_level.upper(), logging.INFO))
    
    # Clear existing handlers
    root_logger.handlers.clear()
    
    # Console handler
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(logging.DEBUG)
    
    if use_json:
        console_handler.setFormatter(StructuredJSONFormatter())
    elif use_colors and sys.stdout.isatty():
        console_handler.setFormatter(ColoredConsoleFormatter(use_colors=True))
    else:
        console_handler.setFormatter(SimpleConsoleFormatter())
    
    root_logger.addHandler(console_handler)
    
    # File handlers (if log_dir specified)
    if log_dir:
        from logging.handlers import RotatingFileHandler
        
        log_path = Path(log_dir)
        log_path.mkdir(parents=True, exist_ok=True)
        
        # Main log file (JSON)
        main_handler = RotatingFileHandler(
            log_path / 'app.log',
            maxBytes=max_bytes,
            backupCount=backup_count,
            encoding='utf-8',
        )
        main_handler.setFormatter(StructuredJSONFormatter())
        root_logger.addHandler(main_handler)
        
        # Error log file (ERROR and above)
        error_handler = RotatingFileHandler(
            log_path / 'error.log',
            maxBytes=max_bytes,
            backupCount=backup_count,
            encoding='utf-8',
        )
        error_handler.setLevel(logging.ERROR)
        error_handler.setFormatter(StructuredJSONFormatter())
        root_logger.addHandler(error_handler)
    
    # Reduce noise from third-party libraries
    logging.getLogger('aiogram').setLevel(logging.WARNING)
    logging.getLogger('aiohttp').setLevel(logging.WARNING)
    logging.getLogger('apscheduler').setLevel(logging.WARNING)


# ============================================================================
# Event Logging API
# ============================================================================

def log_event(
    event: str,
    level: int = logging.INFO,
    logger_name: str = 'noxbot.events',
    **kwargs
) -> None:
    """
    Log a structured event.
    
    Args:
        event: Event name (e.g., 'payment_created', 'wallet_debit')
        level: Log level
        logger_name: Logger name
        **kwargs: Event-specific fields
    
    Example:
        log_event(
            'wallet_debit',
            user_id='123',
            amount=1000,
            transaction_id='txn_456',
            balance_before=5000,
            balance_after=4000,
        )
    """
    logger = logging.getLogger(logger_name)
    
    # Build log record with event and context
    log_data = {
        'event': event,
        **sanitize_dict(kwargs),
    }
    
    # Add context
    context = get_log_context()
    if context:
        log_data.update(context)
    
    # Format message
    msg = f"event={event}"
    if kwargs:
        pairs = [f"{k}={v}" for k, v in kwargs.items() if not isinstance(v, (dict, list))]
        if pairs:
            msg += f" | {' '.join(pairs[:5])}"  # Limit to 5 pairs for readability
    
    logger.log(level, msg, extra=log_data)


def log_payment(
    event: str,
    payment_id: Optional[str] = None,
    user_id: Optional[str] = None,
    amount: Optional[int] = None,
    method: Optional[str] = None,
    status: Optional[str] = None,
    order_id: Optional[str] = None,
    **kwargs
) -> None:
    """Log a payment-related event."""
    log_event(
        event,
        category='payment',
        payment_id=payment_id,
        user_id=user_id,
        amount=amount,
        method=method,
        status=status,
        order_id=order_id,
        logger_name='noxbot.payment',
        **kwargs
    )


def log_wallet(
    event: str,
    user_id: Optional[str] = None,
    amount: Optional[int] = None,
    balance_before: Optional[int] = None,
    balance_after: Optional[int] = None,
    transaction_id: Optional[str] = None,
    operation_type: Optional[str] = None,
    **kwargs
) -> None:
    """Log a wallet-related event."""
    # Check for integrity issues
    if balance_before is not None and balance_after is not None and amount is not None:
        expected = balance_before - abs(amount) if amount < 0 else balance_before + amount
        if expected != balance_after:
            log_event(
                'wallet_integrity_error',
                level=logging.CRITICAL,
                user_id=user_id,
                amount=amount,
                balance_before=balance_before,
                balance_after=balance_after,
                expected=expected,
                transaction_id=transaction_id,
                logger_name='noxbot.security',
                category='security',
            )
    
    # Check for negative balance
    if balance_after is not None and balance_after < 0:
        log_event(
            'wallet_negative_balance',
            level=logging.CRITICAL,
            user_id=user_id,
            balance_after=balance_after,
            transaction_id=transaction_id,
            logger_name='noxbot.security',
            category='security',
        )
    
    log_event(
        event,
        category='wallet',
        user_id=user_id,
        amount=amount,
        balance_before=balance_before,
        balance_after=balance_after,
        transaction_id=transaction_id,
        operation_type=operation_type,
        logger_name='noxbot.wallet',
        **kwargs
    )


def log_custom(
    event: str,
    custom_id: Optional[str] = None,
    admin_id: Optional[str] = None,
    user_id: Optional[str] = None,
    status_before: Optional[str] = None,
    status_after: Optional[str] = None,
    **kwargs
) -> None:
    """Log a custom tournament event."""
    log_event(
        event,
        category='custom',
        custom_id=custom_id,
        admin_id=admin_id,
        user_id=user_id,
        status_before=status_before,
        status_after=status_after,
        logger_name='noxbot.custom',
        **kwargs
    )


def log_security(
    event: str,
    severity: str = 'warning',
    **kwargs
) -> None:
    """Log a security-related event."""
    level_map = {
        'info': logging.INFO,
        'warning': logging.WARNING,
        'error': logging.ERROR,
        'critical': logging.CRITICAL,
    }
    level = level_map.get(severity.lower(), logging.WARNING)
    
    log_event(
        event,
        level=level,
        category='security',
        logger_name='noxbot.security',
        **kwargs
    )


def log_audit(
    action: str,
    admin_id: Optional[str] = None,
    target_type: Optional[str] = None,
    target_id: Optional[str] = None,
    before: Optional[Dict[str, Any]] = None,
    after: Optional[Dict[str, Any]] = None,
    reason: Optional[str] = None,
    **kwargs
) -> None:
    """Log an admin audit event."""
    log_event(
        'admin_action',
        category='audit',
        action=action,
        admin_id=admin_id,
        target_type=target_type,
        target_id=target_id,
        before=before,
        after=after,
        reason=reason,
        logger_name='noxbot.audit',
        **kwargs
    )


# ============================================================================
# Performance Tracking
# ============================================================================

def log_operation(
    operation_name: str,
    log_level: int = logging.INFO,
    logger_name: str = 'noxbot.performance',
):
    """
    Decorator to log operation start, success, failure, and duration.
    
    Example:
        @log_operation('wallet_debit')
        async def deduct_wallet(user_id, amount):
            ...
    """
    def decorator(func: F) -> F:
        @wraps(func)
        async def async_wrapper(*args, **kwargs):
            start_time = time.time()
            log_event(
                f'{operation_name}_started',
                level=logging.DEBUG,
                logger_name=logger_name,
            )
            
            try:
                result = await func(*args, **kwargs)
                duration_ms = (time.time() - start_time) * 1000
                
                log_event(
                    f'{operation_name}_completed',
                    level=log_level,
                    logger_name=logger_name,
                    duration_ms=round(duration_ms, 2),
                )
                
                # Warn if operation took too long (> 1 second)
                if duration_ms > 1000:
                    log_event(
                        f'{operation_name}_slow',
                        level=logging.WARNING,
                        logger_name=logger_name,
                        duration_ms=round(duration_ms, 2),
                    )
                
                return result
            
            except Exception as e:
                duration_ms = (time.time() - start_time) * 1000
                error_id = generate_error_id()
                
                log_event(
                    f'{operation_name}_failed',
                    level=logging.ERROR,
                    logger_name=logger_name,
                    duration_ms=round(duration_ms, 2),
                    error_id=error_id,
                    error_type=type(e).__name__,
                    error_message=str(e),
                    exc_info=True,
                )
                
                raise
        
        @wraps(func)
        def sync_wrapper(*args, **kwargs):
            start_time = time.time()
            log_event(
                f'{operation_name}_started',
                level=logging.DEBUG,
                logger_name=logger_name,
            )
            
            try:
                result = func(*args, **kwargs)
                duration_ms = (time.time() - start_time) * 1000
                
                log_event(
                    f'{operation_name}_completed',
                    level=log_level,
                    logger_name=logger_name,
                    duration_ms=round(duration_ms, 2),
                )
                
                return result
            
            except Exception as e:
                duration_ms = (time.time() - start_time) * 1000
                error_id = generate_error_id()
                
                log_event(
                    f'{operation_name}_failed',
                    level=logging.ERROR,
                    logger_name=logger_name,
                    duration_ms=round(duration_ms, 2),
                    error_id=error_id,
                    error_type=type(e).__name__,
                    error_message=str(e),
                    exc_info=True,
                )
                
                raise
        
        # Return appropriate wrapper based on function type
        import asyncio
        if asyncio.iscoroutinefunction(func):
            return async_wrapper
        else:
            return sync_wrapper
    
    return decorator
