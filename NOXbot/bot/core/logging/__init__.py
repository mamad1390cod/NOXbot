"""
Professional Logging System for NOXbot.

Centralized, structured logging with:
- Request/correlation ID tracking
- User context propagation
- Sensitive data masking
- Event-based logging
- Performance tracking
- Category-based log separation

Usage:
    from bot.core.logging import setup_logging, log_event, log_payment
    
    # Setup (call once at startup)
    setup_logging(log_level='INFO', log_dir='logs/')
    
    # Log events
    log_event('user_registered', user_id='123', custom_id='456')
    log_payment('payment_created', payment_id='789', amount=1000)
    log_wallet('wallet_debit', user_id='123', amount=500, balance_before=1000, balance_after=500)
"""

from .context import (
    generate_request_id,
    generate_correlation_id,
    generate_error_id,
    set_request_id,
    get_request_id,
    set_correlation_id,
    get_correlation_id,
    set_user_context,
    get_user_context,
    clear_context,
    get_log_context,
    RequestContext,
    CorrelationContext,
)

from .sensitive import (
    mask_sensitive_value,
    mask_text,
    sanitize_dict,
    SensitiveDataFilter,
)

from .formatters import (
    StructuredJSONFormatter,
    ColoredConsoleFormatter,
    SimpleConsoleFormatter,
)

from .logger import (
    setup_logging,
    log_event,
    log_payment,
    log_wallet,
    log_custom,
    log_security,
    log_audit,
    log_operation,
)


__all__ = [
    # Context management
    'generate_request_id',
    'generate_correlation_id',
    'generate_error_id',
    'set_request_id',
    'get_request_id',
    'set_correlation_id',
    'get_correlation_id',
    'set_user_context',
    'get_user_context',
    'clear_context',
    'get_log_context',
    'RequestContext',
    'CorrelationContext',
    
    # Sensitive data
    'mask_sensitive_value',
    'mask_text',
    'sanitize_dict',
    'SensitiveDataFilter',
    
    # Formatters
    'StructuredJSONFormatter',
    'ColoredConsoleFormatter',
    'SimpleConsoleFormatter',
    
    # Logging API
    'setup_logging',
    'log_event',
    'log_payment',
    'log_wallet',
    'log_custom',
    'log_security',
    'log_audit',
    'log_operation',
]
