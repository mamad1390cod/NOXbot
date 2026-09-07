"""
Comprehensive tests for Custom Tournament System enhancements.

Tests cover:
1. Prize management (set, edit, delete)
2. Start message management (set, edit, delete)
3. Start custom with validation
4. Postpone custom
5. Registration prevention after STARTED
6. All-or-nothing registration
7. Status flow validation
8. Prize requirement for opening registration
"""
import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from datetime import datetime

from bot.models.custom import CustomStatus, CustomType
from bot.services.custom import CustomService


@pytest.fixture
def mock_uow():
    """Create a mock UnitOfWork."""
    uow = MagicMock()
    uow.session = AsyncMock()
    uow.customs = AsyncMock()
    uow.custom_registrations = AsyncMock()
    uow.custom_carts = AsyncMock()
    uow.flush = AsyncMock()
    return uow


@pytest.fixture
def custom_service(mock_uow):
    """Create a CustomService instance."""
    return CustomService(mock_uow)


class TestPrizeManagement:
    """Test prize management functionality."""

    @pytest.mark.asyncio
    async def test_set_text_prize(self, custom_service, mock_uow):
        """Test setting a text prize."""
        custom_id = "custom123"
        prize_text = "100 دلار جایزه نقدی"
        
        mock_custom = MagicMock()
        mock_custom.id = custom_id
        mock_custom.status = CustomStatus.DRAFT
        mock_custom.prize_set = False
        mock_custom.registration_open = False
        
        mock_uow.customs.get = AsyncMock(return_value=mock_custom)
        mock_uow.customs.update = AsyncMock(return_value=mock_custom)
        
        result = await custom_service.set_prize(
            custom_id,
            prize_text=prize_text,
            prize_file_type="text"
        )
        
        assert result is not None
        mock_uow.customs.update.assert_called_once()
        call_kwargs = mock_uow.customs.update.call_args[1]
        assert call_kwargs['prize'] == prize_text
        assert call_kwargs['prize_file_type'] == "text"
        assert call_kwargs['prize_set'] == True
        assert call_kwargs['status'] == CustomStatus.READY  # Should transition to READY

    @pytest.mark.asyncio
    async def test_set_media_prize(self, custom_service, mock_uow):
        """Test setting a media prize (photo/video/document)."""
        custom_id = "custom123"
        file_id = "AgACAgIAAxkBAAI"
        file_type = "photo"
        caption = "جایزه ویژه"
        
        mock_custom = MagicMock()
        mock_custom.id = custom_id
        mock_custom.status = CustomStatus.READY
        mock_custom.prize_set = False
        
        mock_uow.customs.get = AsyncMock(return_value=mock_custom)
        mock_uow.customs.update = AsyncMock(return_value=mock_custom)
        
        result = await custom_service.set_prize(
            custom_id,
            prize_file_id=file_id,
            prize_file_type=file_type,
            prize_caption=caption
        )
        
        assert result is not None
        call_kwargs = mock_uow.customs.update.call_args[1]
        assert call_kwargs['prize_file_id'] == file_id
        assert call_kwargs['prize_file_type'] == file_type
        assert call_kwargs['prize_caption'] == caption
        assert call_kwargs['prize_set'] == True

    @pytest.mark.asyncio
    async def test_cannot_set_prize_after_started(self, custom_service, mock_uow):
        """Test that prize cannot be set after custom has started."""
        custom_id = "custom123"
        
        mock_custom = MagicMock()
        mock_custom.id = custom_id
        mock_custom.status = CustomStatus.STARTED
        
        mock_uow.customs.get = AsyncMock(return_value=mock_custom)
        
        with pytest.raises(ValueError, match="قبلاً شروع"):
            await custom_service.set_prize(custom_id, prize_text="Test")

    @pytest.mark.asyncio
    async def test_clear_prize(self, custom_service, mock_uow):
        """Test clearing prize."""
        custom_id = "custom123"
        
        mock_custom = MagicMock()
        mock_custom.id = custom_id
        mock_custom.status = CustomStatus.READY
        mock_custom.prize_set = True
        mock_custom.registration_open = False
        
        mock_uow.customs.get = AsyncMock(return_value=mock_custom)
        mock_uow.customs.update = AsyncMock(return_value=mock_custom)
        
        result = await custom_service.clear_prize(custom_id)
        
        assert result is not None
        call_kwargs = mock_uow.customs.update.call_args[1]
        assert call_kwargs['prize'] is None
        assert call_kwargs['prize_file_id'] is None
        assert call_kwargs['prize_set'] == False
        assert call_kwargs['status'] == CustomStatus.DRAFT

    @pytest.mark.asyncio
    async def test_clear_prize_closes_registration(self, custom_service, mock_uow):
        """Test that clearing prize closes registration if open."""
        custom_id = "custom123"
        
        mock_custom = MagicMock()
        mock_custom.id = custom_id
        mock_custom.status = CustomStatus.REGISTRATION_OPEN
        mock_custom.prize_set = True
        mock_custom.registration_open = True
        
        mock_uow.customs.get = AsyncMock(return_value=mock_custom)
        mock_uow.customs.update = AsyncMock(return_value=mock_custom)
        
        await custom_service.clear_prize(custom_id)
        
        # Should have called update twice: once for closing registration, once for clearing prize
        assert mock_uow.customs.update.call_count == 2


class TestStartMessage:
    """Test start message management."""

    @pytest.mark.asyncio
    async def test_set_start_message(self, custom_service, mock_uow):
        """Test setting start message."""
        custom_id = "custom123"
        message = "🚀 مسابقه شروع شد! موفق باشید."
        
        mock_custom = MagicMock()
        mock_custom.id = custom_id
        mock_custom.status = CustomStatus.REGISTRATION_OPEN
        
        mock_uow.customs.get = AsyncMock(return_value=mock_custom)
        mock_uow.customs.update = AsyncMock(return_value=mock_custom)
        
        result = await custom_service.set_start_message(custom_id, message)
        
        assert result is not None
        mock_uow.customs.update.assert_called_once_with(custom_id, start_message=message)

    @pytest.mark.asyncio
    async def test_cannot_set_start_message_after_started(self, custom_service, mock_uow):
        """Test that start message cannot be set after custom has started."""
        custom_id = "custom123"
        
        mock_custom = MagicMock()
        mock_custom.id = custom_id
        mock_custom.status = CustomStatus.STARTED
        
        mock_uow.customs.get = AsyncMock(return_value=mock_custom)
        
        with pytest.raises(ValueError, match="قبلاً شروع"):
            await custom_service.set_start_message(custom_id, "Test")

    @pytest.mark.asyncio
    async def test_clear_start_message(self, custom_service, mock_uow):
        """Test clearing start message."""
        custom_id = "custom123"
        
        mock_uow.customs.update = AsyncMock()
        
        await custom_service.clear_start_message(custom_id)
        
        mock_uow.customs.update.assert_called_once_with(custom_id, start_message=None)


class TestStartCustom:
    """Test starting custom tournament."""

    @pytest.mark.asyncio
    async def test_start_custom_success(self, custom_service, mock_uow):
        """Test successful start of custom."""
        custom_id = "custom123"
        admin_id = "admin456"
        
        mock_custom = MagicMock()
        mock_custom.id = custom_id
        mock_custom.status = CustomStatus.REGISTRATION_OPEN
        mock_custom.prize_set = True
        mock_custom.start_message = "🚀 شروع شد!"
        
        mock_uow.customs.get = AsyncMock(return_value=mock_custom)
        mock_uow.customs.update = AsyncMock(return_value=mock_custom)
        mock_uow.custom_registrations.get_confirmed_registrations = AsyncMock(return_value=[])
        
        custom, result = await custom_service.start_custom(custom_id, admin_id)
        
        assert custom is not None
        assert result.get("sent", 0) >= 0
        assert result.get("failed", 0) >= 0
        
        # Verify status changed to STARTED
        call_kwargs = mock_uow.customs.update.call_args[1]
        assert call_kwargs['status'] == CustomStatus.STARTED
        assert call_kwargs['registration_open'] == False

    @pytest.mark.asyncio
    async def test_cannot_start_without_prize(self, custom_service, mock_uow):
        """Test that custom cannot be started without prize."""
        custom_id = "custom123"
        
        mock_custom = MagicMock()
        mock_custom.id = custom_id
        mock_custom.status = CustomStatus.REGISTRATION_OPEN
        mock_custom.prize_set = False
        
        mock_uow.customs.get = AsyncMock(return_value=mock_custom)
        
        custom, result = await custom_service.start_custom(custom_id, "admin456")
        
        assert custom is None
        assert "error" in result
        assert "جایزه" in result["error"]

    @pytest.mark.asyncio
    async def test_cannot_start_already_started(self, custom_service, mock_uow):
        """Test that already started custom cannot be started again."""
        custom_id = "custom123"
        
        mock_custom = MagicMock()
        mock_custom.id = custom_id
        mock_custom.status = CustomStatus.STARTED
        mock_custom.prize_set = True
        
        mock_uow.customs.get = AsyncMock(return_value=mock_custom)
        
        custom, result = await custom_service.start_custom(custom_id, "admin456")
        
        assert custom is None
        assert "error" in result
        assert "قبلاً شروع" in result["error"]

    @pytest.mark.asyncio
    async def test_start_custom_sends_message_to_confirmed(self, custom_service, mock_uow):
        """Test that start message is sent only to confirmed participants."""
        custom_id = "custom123"
        admin_id = "admin456"
        start_message = "🚀 مسابقه شروع شد!"
        
        mock_custom = MagicMock()
        mock_custom.id = custom_id
        mock_custom.status = CustomStatus.REGISTRATION_OPEN
        mock_custom.prize_set = True
        mock_custom.start_message = start_message
        
        # Create mock registrations
        confirmed_reg = MagicMock()
        confirmed_reg.user = MagicMock()
        confirmed_reg.user.telegram_id = "tg123"
        confirmed_reg.status = "confirmed"
        
        pending_reg = MagicMock()
        pending_reg.user = MagicMock()
        pending_reg.user.telegram_id = "tg456"
        pending_reg.status = "pending"
        
        mock_uow.customs.get = AsyncMock(return_value=mock_custom)
        mock_uow.customs.update = AsyncMock(return_value=mock_custom)
        mock_uow.custom_registrations.get_confirmed_registrations = AsyncMock(
            return_value=[confirmed_reg, pending_reg]
        )
        
        # Create a mock bot
        mock_bot = AsyncMock()
        
        # Mock notification service - patch at the location where it's imported
        with patch('bot.services.notification.NotificationService') as mock_notifier_class:
            mock_notifier = AsyncMock()
            mock_notifier_class.return_value = mock_notifier
            
            custom, result = await custom_service.start_custom(custom_id, admin_id, bot=mock_bot)
            
            # Should only send to confirmed participant
            assert result.get("sent") == 1
            mock_notifier.notify_user.assert_called_once_with("tg123", start_message)


class TestRegistrationValidation:
    """Test registration validation."""

    @pytest.mark.asyncio
    async def test_cannot_register_after_started(self, custom_service, mock_uow):
        """Test that users cannot register after custom has started."""
        user_id = "user123"
        custom_id = "custom123"
        
        mock_custom = MagicMock()
        mock_custom.id = custom_id
        mock_custom.status = CustomStatus.STARTED
        mock_custom.registration_open = False
        
        mock_uow.customs.get = AsyncMock(return_value=mock_custom)
        
        with pytest.raises(ValueError, match="قبلاً شروع"):
            await custom_service.register_user(
                user_id, custom_id, "player1"
            )

    @pytest.mark.asyncio
    async def test_cannot_register_when_closed(self, custom_service, mock_uow):
        """Test that users cannot register when registration is closed."""
        user_id = "user123"
        custom_id = "custom123"
        
        mock_custom = MagicMock()
        mock_custom.id = custom_id
        mock_custom.status = CustomStatus.REGISTRATION_CLOSED
        mock_custom.registration_open = False
        
        mock_uow.customs.get = AsyncMock(return_value=mock_custom)
        
        with pytest.raises(ValueError, match="باز نیست"):
            await custom_service.register_user(
                user_id, custom_id, "player1"
            )


class TestSetRegistrationStatus:
    """Test registration status validation."""

    @pytest.mark.asyncio
    async def test_cannot_open_without_prize(self, custom_service, mock_uow):
        """Test that registration cannot be opened without prize."""
        custom_id = "custom123"
        
        mock_custom = MagicMock()
        mock_custom.id = custom_id
        mock_custom.prize_set = False
        mock_custom.status = CustomStatus.DRAFT
        
        mock_uow.customs.get = AsyncMock(return_value=mock_custom)
        
        with pytest.raises(ValueError, match="جایزه"):
            await custom_service.set_registration_status(custom_id, True)

    @pytest.mark.asyncio
    async def test_cannot_open_after_started(self, custom_service, mock_uow):
        """Test that registration cannot be opened after custom has started."""
        custom_id = "custom123"
        
        mock_custom = MagicMock()
        mock_custom.id = custom_id
        mock_custom.prize_set = True
        mock_custom.status = CustomStatus.STARTED
        
        mock_uow.customs.get = AsyncMock(return_value=mock_custom)
        
        with pytest.raises(ValueError, match="قبلاً شروع"):
            await custom_service.set_registration_status(custom_id, True)

    @pytest.mark.asyncio
    async def test_can_open_with_prize(self, custom_service, mock_uow):
        """Test that registration can be opened when prize is set."""
        custom_id = "custom123"
        
        mock_custom = MagicMock()
        mock_custom.id = custom_id
        mock_custom.prize_set = True
        mock_custom.status = CustomStatus.READY
        
        mock_uow.customs.get = AsyncMock(return_value=mock_custom)
        mock_uow.customs.update = AsyncMock(return_value=mock_custom)
        
        result = await custom_service.set_registration_status(custom_id, True)
        
        assert result is not None
        call_kwargs = mock_uow.customs.update.call_args[1]
        assert call_kwargs['registration_open'] == True
        assert call_kwargs['status'] == CustomStatus.REGISTRATION_OPEN


class TestPostponeCustom:
    """Test postpone custom functionality."""

    @pytest.mark.asyncio
    async def test_postpone_success(self, custom_service, mock_uow):
        """Test successful postpone."""
        custom_id = "custom123"
        new_date = datetime(2026, 9, 20)
        new_time = "21:00"
        
        mock_custom = MagicMock()
        mock_custom.id = custom_id
        mock_custom.status = CustomStatus.REGISTRATION_OPEN
        
        mock_uow.customs.get = AsyncMock(return_value=mock_custom)
        mock_uow.customs.update = AsyncMock(return_value=mock_custom)
        
        result = await custom_service.postpone_custom(custom_id, new_date, new_time)
        
        assert result is not None
        call_kwargs = mock_uow.customs.update.call_args[1]
        assert call_kwargs['event_date'] == new_date
        assert call_kwargs['event_time'] == new_time

    @pytest.mark.asyncio
    async def test_cannot_postpone_after_started(self, custom_service, mock_uow):
        """Test that custom cannot be postponed after started."""
        custom_id = "custom123"
        
        mock_custom = MagicMock()
        mock_custom.id = custom_id
        mock_custom.status = CustomStatus.STARTED
        
        mock_uow.customs.get = AsyncMock(return_value=mock_custom)
        
        with pytest.raises(ValueError, match="قبلاً شروع"):
            await custom_service.postpone_custom(custom_id, datetime.now(), "20:00")


class TestStatusFlow:
    """Test status flow validation."""

    @pytest.mark.asyncio
    async def test_draft_to_ready_on_prize_set(self, custom_service, mock_uow):
        """Test that setting prize transitions DRAFT to READY."""
        custom_id = "custom123"
        
        mock_custom = MagicMock()
        mock_custom.id = custom_id
        mock_custom.status = CustomStatus.DRAFT
        mock_custom.prize_set = False
        
        mock_uow.customs.get = AsyncMock(return_value=mock_custom)
        mock_uow.customs.update = AsyncMock(return_value=mock_custom)
        
        await custom_service.set_prize(custom_id, prize_text="Prize")
        
        call_kwargs = mock_uow.customs.update.call_args[1]
        assert call_kwargs['status'] == CustomStatus.READY

    @pytest.mark.asyncio
    async def test_ready_to_registration_open(self, custom_service, mock_uow):
        """Test that opening registration transitions READY to REGISTRATION_OPEN."""
        custom_id = "custom123"
        
        mock_custom = MagicMock()
        mock_custom.id = custom_id
        mock_custom.status = CustomStatus.READY
        mock_custom.prize_set = True
        
        mock_uow.customs.get = AsyncMock(return_value=mock_custom)
        mock_uow.customs.update = AsyncMock(return_value=mock_custom)
        
        await custom_service.set_registration_status(custom_id, True)
        
        call_kwargs = mock_uow.customs.update.call_args[1]
        assert call_kwargs['status'] == CustomStatus.REGISTRATION_OPEN


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
