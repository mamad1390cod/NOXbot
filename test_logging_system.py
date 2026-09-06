"""
Tests for the professional logging system.

Tests cover:
- Context management (request_id, correlation_id, user_context)
- Sensitive data masking
- Structured JSON formatting
- Event logging API
- Wallet/Payment/Custom/Security logging
- Error ID generation
- Log rotation
"""

import json
import logging
import pytest
from io import StringIO
from unittest.mock import Mock, patch

from bot.core.logging import (
    # Context
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
    
    # Sensitive data
    mask_sensitive_value,
    mask_text,
    sanitize_dict,
    SensitiveDataFilter,
    
    # Formatters
    StructuredJSONFormatter,
    ColoredConsoleFormatter,
    
    # Logging API
    setup_logging,
    log_event,
    log_payment,
    log_wallet,
    log_custom,
    log_security,
    log_audit,
)


class TestContextManagement:
    """Test request/correlation ID and user context management."""
    
    def test_generate_request_id(self):
        """Test request ID generation."""
        req_id = generate_request_id()
        assert req_id.startswith('REQ-')
        assert len(req_id) > 10
    
    def test_generate_correlation_id(self):
        """Test correlation ID generation."""
        cor_id = generate_correlation_id()
        assert cor_id.startswith('COR-')
        assert len(cor_id) > 10
    
    def test_generate_error_id(self):
        """Test error ID generation."""
        err_id = generate_error_id()
        assert err_id.startswith('ERR-')
        assert len(err_id) > 10
    
    def test_set_and_get_request_id(self):
        """Test setting and getting request ID."""
        req_id = set_request_id()
        assert req_id is not None
        assert get_request_id() == req_id
        
        # Clear
        clear_context()
        assert get_request_id() is None
    
    def test_set_and_get_correlation_id(self):
        """Test setting and getting correlation ID."""
        cor_id = set_correlation_id()
        assert cor_id is not None
        assert get_correlation_id() == cor_id
        
        # Clear
        clear_context()
        assert get_correlation_id() is None
    
    def test_set_and_get_user_context(self):
        """Test setting and getting user context."""
        context = set_user_context(
            user_id='123',
            chat_id=456,
            username='testuser',
            is_admin=True,
        )
        
        assert context['user_id'] == '123'
        assert context['chat_id'] == 456
        assert context['username'] == 'testuser'
        assert context['is_admin'] is True
        
        retrieved = get_user_context()
        assert retrieved == context
        
        # Clear
        clear_context()
        assert get_user_context() is None
    
    def test_request_context_manager(self):
        """Test RequestContext context manager."""
        with RequestContext(request_id='REQ-TEST', user_id='123'):
            assert get_request_id() == 'REQ-TEST'
            assert get_user_context()['user_id'] == '123'
        
        # After context manager, should be cleared
        assert get_request_id() is None
        assert get_user_context() is None
    
    def test_correlation_context_manager(self):
        """Test CorrelationContext context manager."""
        with CorrelationContext(correlation_id='COR-TEST'):
            assert get_correlation_id() == 'COR-TEST'
        
        # After context manager, should be cleared
        assert get_correlation_id() is None
    
    def test_get_log_context(self):
        """Test getting all context information."""
        set_request_id('REQ-123')
        set_correlation_id('COR-456')
        set_user_context(user_id='789')
        
        context = get_log_context()
        assert context['request_id'] == 'REQ-123'
        assert context['correlation_id'] == 'COR-456'
        assert context['user_id'] == '789'
        
        clear_context()


class TestSensitiveDataMasking:
    """Test sensitive data masking."""
    
    def test_mask_sensitive_value_token(self):
        """Test masking token values."""
        result = mask_sensitive_value('token', 'abc123xyz789')
        assert result == 'abc1********'  # First 4 chars + 8 asterisks
    
    def test_mask_sensitive_value_password(self):
        """Test masking password values."""
        result = mask_sensitive_value('password', 'secret123')
        assert result == 'secr*****'
    
    def test_mask_sensitive_value_short(self):
        """Test masking short sensitive values."""
        result = mask_sensitive_value('api_key', 'abc')
        assert result == '****'
    
    def test_mask_sensitive_value_non_sensitive(self):
        """Test non-sensitive values are not masked."""
        result = mask_sensitive_value('username', 'testuser')
        assert result == 'testuser'
    
    def test_mask_text_bot_token(self):
        """Test masking bot tokens in text."""
        text = "Bot token: 123456789:ABCdefGHIjklMNOpqrsTUVwxyz"
        result = mask_text(text)
        assert '[BOT_TOKEN_REDACTED]' in result
        assert '123456789' not in result
    
    def test_mask_text_card_number(self):
        """Test masking card numbers in text."""
        text = "Card: 1234 5678 9012 3456"
        result = mask_text(text)
        assert '[CARD_NUMBER_REDACTED]' in result
    
    def test_mask_text_email(self):
        """Test masking email addresses."""
        text = "Email: testuser@example.com"
        result = mask_text(text)
        assert 'tes***@example.com' in result
    
    def test_mask_text_phone(self):
        """Test masking phone numbers."""
        text = "Phone: 09123456789"
        result = mask_text(text)
        assert '[PHONE_REDACTED]' in result
    
    def test_sanitize_dict(self):
        """Test sanitizing dictionary."""
        data = {
            'username': 'testuser',
            'password': 'secret123',
            'token': 'abc123xyz',
            'nested': {
                'api_key': 'key123',
                'normal': 'value',
            }
        }
        
        result = sanitize_dict(data)
        assert result['username'] == 'testuser'
        assert result['password'] == 'secr*****'  # First 4 + 5 asterisks
        assert result['token'] == 'abc1*****'  # First 4 + 5 asterisks
        assert result['nested']['api_key'] == 'key1**'  # First 4 + 2 asterisks
        assert result['nested']['normal'] == 'value'
    
    def test_sensitive_data_filter(self):
        """Test SensitiveDataFilter."""
        filter_obj = SensitiveDataFilter()
        
        record = logging.LogRecord(
            name='test',
            level=logging.INFO,
            pathname='test.py',
            lineno=1,
            msg='Token: 123456789:ABCdefGHIjklMNOpqrsTUVwxyz',
            args=(),
            exc_info=None,
        )
        
        filter_obj.filter(record)
        assert '[BOT_TOKEN_REDACTED]' in record.msg


class TestStructuredJSONFormatter:
    """Test JSON formatter."""
    
    def test_format_basic(self):
        """Test basic JSON formatting."""
        formatter = StructuredJSONFormatter()
        
        record = logging.LogRecord(
            name='test.logger',
            level=logging.INFO,
            pathname='test.py',
            lineno=42,
            msg='Test message',
            args=(),
            exc_info=None,
        )
        record.funcName = 'test_func'
        record.module = 'test_module'
        
        result = formatter.format(record)
        data = json.loads(result)
        
        assert data['level'] == 'INFO'
        assert data['logger'] == 'test.logger'
        assert data['message'] == 'Test message'
        assert data['module'] == 'test_module'
        assert data['function'] == 'test_func'
        assert data['line'] == 42
        assert 'timestamp' in data
    
    def test_format_with_context(self):
        """Test JSON formatting with context."""
        formatter = StructuredJSONFormatter()
        
        set_request_id('REQ-123')
        set_user_context(user_id='456')
        
        record = logging.LogRecord(
            name='test',
            level=logging.INFO,
            pathname='test.py',
            lineno=1,
            msg='Test',
            args=(),
            exc_info=None,
        )
        
        result = formatter.format(record)
        data = json.loads(result)
        
        assert 'context' in data
        assert data['context']['request_id'] == 'REQ-123'
        assert data['context']['user_id'] == '456'
        
        clear_context()
    
    def test_format_with_exception(self):
        """Test JSON formatting with exception."""
        formatter = StructuredJSONFormatter()
        
        try:
            raise ValueError("Test error")
        except ValueError:
            import sys
            exc_info = sys.exc_info()
        
        record = logging.LogRecord(
            name='test',
            level=logging.ERROR,
            pathname='test.py',
            lineno=1,
            msg='Error occurred',
            args=(),
            exc_info=exc_info,
        )
        
        result = formatter.format(record)
        data = json.loads(result)
        
        assert 'exception' in data
        assert data['exception']['type'] == 'ValueError'
        assert data['exception']['message'] == 'Test error'
        assert 'traceback' in data['exception']


class TestEventLogging:
    """Test event logging API."""
    
    def test_log_event(self, caplog):
        """Test basic event logging."""
        with caplog.at_level(logging.INFO):
            log_event('test_event', user_id='123', action='test')
        
        assert 'event=test_event' in caplog.text
    
    def test_log_payment(self, caplog):
        """Test payment event logging."""
        with caplog.at_level(logging.INFO):
            log_payment(
                'payment_created',
                payment_id='pay_123',
                user_id='456',
                amount=1000,
                method='wallet',
            )
        
        assert 'event=payment_created' in caplog.text
    
    def test_log_wallet(self, caplog):
        """Test wallet event logging."""
        with caplog.at_level(logging.INFO):
            log_wallet(
                'wallet_debit',
                user_id='123',
                amount=500,
                balance_before=1000,
                balance_after=500,
                transaction_id='txn_789',
            )
        
        assert 'event=wallet_debit' in caplog.text
    
    def test_log_wallet_integrity_error(self, caplog):
        """Test wallet integrity error detection."""
        with caplog.at_level(logging.CRITICAL):
            log_wallet(
                'wallet_debit',
                user_id='123',
                amount=500,
                balance_before=1000,
                balance_after=600,  # Wrong! Should be 500
                transaction_id='txn_789',
            )
        
        assert 'wallet_integrity_error' in caplog.text
    
    def test_log_wallet_negative_balance(self, caplog):
        """Test negative balance detection."""
        with caplog.at_level(logging.CRITICAL):
            log_wallet(
                'wallet_debit',
                user_id='123',
                amount=500,
                balance_before=100,
                balance_after=-400,  # Negative!
                transaction_id='txn_789',
            )
        
        assert 'wallet_negative_balance' in caplog.text
    
    def test_log_custom(self, caplog):
        """Test custom event logging."""
        with caplog.at_level(logging.INFO):
            log_custom(
                'custom_created',
                custom_id='cus_123',
                admin_id='adm_456',
            )
        
        assert 'event=custom_created' in caplog.text
    
    def test_log_security(self, caplog):
        """Test security event logging."""
        with caplog.at_level(logging.WARNING):
            log_security(
                'unauthorized_access_attempt',
                user_id='123',
                resource='admin_panel',
            )
        
        assert 'event=unauthorized_access_attempt' in caplog.text
    
    def test_log_audit(self, caplog):
        """Test audit event logging."""
        with caplog.at_level(logging.INFO):
            log_audit(
                'admin_create_custom',
                admin_id='adm_123',
                target_type='custom',
                target_id='cus_456',
            )
        
        assert 'event=admin_action' in caplog.text


class TestSetupLogging:
    """Test logging setup."""
    
    def test_setup_logging_console_only(self):
        """Test setup with console only."""
        setup_logging(log_level='INFO', log_dir=None)
        
        logger = logging.getLogger('test')
        assert logger.getEffectiveLevel() == logging.INFO
    
    def test_setup_logging_with_files(self, tmp_path):
        """Test setup with file logging."""
        log_dir = tmp_path / 'logs'
        setup_logging(log_level='INFO', log_dir=str(log_dir))
        
        # Log something
        logger = logging.getLogger('test')
        logger.info('Test message')
        
        # Check files exist
        assert (log_dir / 'app.log').exists()
        assert (log_dir / 'error.log').exists()


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
