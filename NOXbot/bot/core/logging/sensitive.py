"""
Sensitive data masking and redaction for logging.

Ensures sensitive information is never logged in plain text:
- API tokens
- Passwords
- Card numbers
- CVV
- Private keys
- Authorization headers
"""

import re
from typing import Any, Dict, List, Union


# Patterns that indicate sensitive data
SENSITIVE_KEYS = {
    'token', 'bot_token', 'api_token', 'access_token', 'refresh_token',
    'password', 'passwd', 'pwd', 'secret', 'api_key', 'apikey',
    'private_key', 'privatekey', 'secret_key', 'secretkey',
    'card_number', 'cardnumber', 'pan',
    'cvv', 'cvc', 'cvv2', 'cvc2',
    'authorization', 'auth', 'bearer',
    'cookie', 'session', 'session_id', 'sessionid',
    'wallet_seed', 'seed', 'mnemonic',
    'pin', 'otp', '2fa',
}

# Regex patterns for sensitive data
SENSITIVE_PATTERNS = [
    # Bot token: 123456789:ABCdefGHIjklMNOpqrsTUVwxyz (8-10 digits, 25-40 alphanumeric chars)
    (re.compile(r'\d{8,10}:[A-Za-z0-9_-]{25,40}'), '[BOT_TOKEN_REDACTED]'),
    
    # Credit card numbers (16 digits, with or without spaces/dashes)
    (re.compile(r'\b(?:\d[ -]*?){13,16}\b'), '[CARD_NUMBER_REDACTED]'),
    
    # Email addresses (partial masking)
    (re.compile(r'\b([a-zA-Z0-9._%+-]+)@([a-zA-Z0-9.-]+\.[a-zA-Z]{2,})\b'), 
     lambda m: f"{m.group(1)[:3]}***@{m.group(2)}"),
    
    # Phone numbers (Iranian format)
    (re.compile(r'\b(?:\+98|0)?9\d{9}\b'), '[PHONE_REDACTED]'),
]


def mask_sensitive_value(key: str, value: Any) -> Any:
    """Mask a value if the key indicates sensitive data."""
    if key.lower() in SENSITIVE_KEYS:
        if isinstance(value, str) and len(value) > 4:
            # Show first 4 chars, mask the rest
            return value[:4] + '*' * (len(value) - 4)
        elif isinstance(value, str):
            return '****'
        else:
            return '[REDACTED]'
    return value


def mask_text(text: str) -> str:
    """Mask sensitive patterns in text."""
    if not isinstance(text, str):
        return text
    
    for pattern, replacement in SENSITIVE_PATTERNS:
        if callable(replacement):
            text = pattern.sub(replacement, text)
        else:
            text = pattern.sub(replacement, text)
    
    return text


def sanitize_dict(data: Dict[str, Any], max_depth: int = 5) -> Dict[str, Any]:
    """Recursively sanitize a dictionary, masking sensitive values."""
    if max_depth <= 0:
        return data
    
    sanitized = {}
    for key, value in data.items():
        if isinstance(value, dict):
            sanitized[key] = sanitize_dict(value, max_depth - 1)
        elif isinstance(value, list):
            sanitized[key] = [
                sanitize_dict(item, max_depth - 1) if isinstance(item, dict) 
                else mask_text(str(item)) if isinstance(item, str) 
                else item
                for item in value
            ]
        elif isinstance(value, str):
            # Check if key is sensitive
            masked_value = mask_sensitive_value(key, value)
            # Also mask patterns in the value
            if masked_value == value:
                masked_value = mask_text(value)
            sanitized[key] = masked_value
        else:
            sanitized[key] = value
    
    return sanitized


def sanitize_log_record(record_dict: Dict[str, Any]) -> Dict[str, Any]:
    """Sanitize a log record dictionary."""
    return sanitize_dict(record_dict)


class SensitiveDataFilter:
    """Logging filter that masks sensitive data in log messages."""
    
    def filter(self, record) -> bool:
        """Filter and sanitize log record."""
        # Sanitize the message
        if hasattr(record, 'msg') and isinstance(record.msg, str):
            record.msg = mask_text(record.msg)
        
        # Sanitize args if present
        if hasattr(record, 'args') and record.args:
            if isinstance(record.args, dict):
                record.args = sanitize_dict(record.args)
            elif isinstance(record.args, tuple):
                record.args = tuple(
                    mask_text(str(arg)) if isinstance(arg, str) else arg
                    for arg in record.args
                )
        
        return True
