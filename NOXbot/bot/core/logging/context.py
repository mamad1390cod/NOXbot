"""
Logging context management for request tracking and correlation.

Provides:
- Request ID generation and propagation
- Correlation ID for multi-step operations
- User/Admin context binding
- Context-aware logging
"""

import uuid
import hashlib
from contextvars import ContextVar
from typing import Optional, Dict, Any
from datetime import datetime


# Context variables for request tracking
request_id_var: ContextVar[Optional[str]] = ContextVar('request_id', default=None)
correlation_id_var: ContextVar[Optional[str]] = ContextVar('correlation_id', default=None)
user_context_var: ContextVar[Optional[Dict[str, Any]]] = ContextVar('user_context', default=None)


def generate_request_id() -> str:
    """Generate a unique request ID for tracking."""
    timestamp = datetime.utcnow().strftime('%Y%m%d%H%M%S')
    random_part = uuid.uuid4().hex[:6].upper()
    return f"REQ-{timestamp}-{random_part}"


def generate_correlation_id() -> str:
    """Generate a correlation ID for multi-step operations."""
    return f"COR-{uuid.uuid4().hex[:12].upper()}"


def generate_error_id() -> str:
    """Generate a user-friendly error ID."""
    timestamp = datetime.utcnow().strftime('%Y%m%d%H%M%S')
    random_part = uuid.uuid4().hex[:6].upper()
    return f"ERR-{timestamp}-{random_part}"


def set_request_id(request_id: Optional[str] = None) -> str:
    """Set the current request ID (generates one if not provided)."""
    if request_id is None:
        request_id = generate_request_id()
    request_id_var.set(request_id)
    return request_id


def get_request_id() -> Optional[str]:
    """Get the current request ID."""
    return request_id_var.get()


def set_correlation_id(correlation_id: Optional[str] = None) -> str:
    """Set the correlation ID for multi-step operations."""
    if correlation_id is None:
        correlation_id = generate_correlation_id()
    correlation_id_var.set(correlation_id)
    return correlation_id


def get_correlation_id() -> Optional[str]:
    """Get the current correlation ID."""
    return correlation_id_var.get()


def set_user_context(
    user_id: Optional[str] = None,
    chat_id: Optional[int] = None,
    username: Optional[str] = None,
    is_admin: bool = False,
    **extra_fields
) -> Dict[str, Any]:
    """Set user context for logging."""
    context = {
        'user_id': user_id,
        'chat_id': chat_id,
        'username': username,
        'is_admin': is_admin,
        **extra_fields
    }
    user_context_var.set(context)
    return context


def get_user_context() -> Optional[Dict[str, Any]]:
    """Get the current user context."""
    return user_context_var.get()


def clear_context():
    """Clear all context variables."""
    request_id_var.set(None)
    correlation_id_var.set(None)
    user_context_var.set(None)


def get_log_context() -> Dict[str, Any]:
    """Get all context information for logging."""
    context = {}
    
    req_id = get_request_id()
    if req_id:
        context['request_id'] = req_id
    
    cor_id = get_correlation_id()
    if cor_id:
        context['correlation_id'] = cor_id
    
    user_ctx = get_user_context()
    if user_ctx:
        context.update(user_ctx)
    
    return context


class RequestContext:
    """Context manager for request-scoped logging context."""
    
    def __init__(self, request_id: Optional[str] = None, **user_info):
        self.request_id = request_id
        self.user_info = user_info
        self._old_request_id = None
        self._old_user_context = None
    
    def __enter__(self):
        self._old_request_id = get_request_id()
        self._old_user_context = get_user_context()
        
        set_request_id(self.request_id)
        if self.user_info:
            set_user_context(**self.user_info)
        
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        request_id_var.set(self._old_request_id)
        user_context_var.set(self._old_user_context)
        return False


class CorrelationContext:
    """Context manager for correlation-scoped logging."""
    
    def __init__(self, correlation_id: Optional[str] = None):
        self.correlation_id = correlation_id
        self._old_correlation_id = None
    
    def __enter__(self):
        self._old_correlation_id = get_correlation_id()
        set_correlation_id(self.correlation_id)
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        correlation_id_var.set(self._old_correlation_id)
        return False
