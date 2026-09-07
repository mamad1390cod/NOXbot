"""Status Transition Tests — Verify order state machine correctness."""

import pytest
from bot.models.order import OrderStatus
from bot.services.order import TRANSITIONS, OrderStatusError


class TestStatusTransitions:
    """Verify that only valid status transitions are allowed."""

    def test_valid_transitions_exist(self):
        """All expected valid transitions must be defined."""
        assert OrderStatus.PENDING in TRANSITIONS
        assert OrderStatus.WAITING_PAYMENT in TRANSITIONS
        assert OrderStatus.PAYMENT_UPLOADED in TRANSITIONS
        assert OrderStatus.PAYMENT_REVIEWING in TRANSITIONS
        assert OrderStatus.APPROVED in TRANSITIONS
        assert OrderStatus.PREPARING in TRANSITIONS
        assert OrderStatus.DELIVERED in TRANSITIONS
        assert OrderStatus.COMPLETED in TRANSITIONS

    def test_terminal_states_have_no_transitions(self):
        """Terminal states (CANCELLED, REFUNDED, REJECTED) must not transition."""
        assert TRANSITIONS[OrderStatus.CANCELLED] == set()
        assert TRANSITIONS[OrderStatus.REFUNDED] == set()
        assert TRANSITIONS[OrderStatus.REJECTED] == set()

    def test_pending_can_only_go_to_waiting_or_cancelled(self):
        """PENDING → WAITING_PAYMENT or CANCELLED only."""
        allowed = TRANSITIONS[OrderStatus.PENDING]
        assert OrderStatus.WAITING_PAYMENT in allowed
        assert OrderStatus.CANCELLED in allowed
        assert OrderStatus.APPROVED not in allowed
        assert OrderStatus.COMPLETED not in allowed

    def test_approved_can_go_to_preparing_or_refunded(self):
        """APPROVED → PREPARING or REFUNDED."""
        allowed = TRANSITIONS[OrderStatus.APPROVED]
        assert OrderStatus.PREPARING in allowed
        assert OrderStatus.REFUNDED in allowed
        assert OrderStatus.COMPLETED not in allowed

    def test_delivered_can_go_to_completed_or_refunded(self):
        """DELIVERED → COMPLETED or REFUNDED."""
        allowed = TRANSITIONS[OrderStatus.DELIVERED]
        assert OrderStatus.COMPLETED in allowed
        assert OrderStatus.REFUNDED in allowed

    def test_completed_can_only_go_to_refunded(self):
        """COMPLETED → REFUNDED only."""
        allowed = TRANSITIONS[OrderStatus.COMPLETED]
        assert OrderStatus.REFUNDED in allowed
        assert len(allowed) == 1

    def test_invalid_transition_rejected(self):
        """Invalid transitions must not be in TRANSITIONS."""
        # REFUNDED → APPROVED is invalid
        assert OrderStatus.APPROVED not in TRANSITIONS[OrderStatus.REFUNDED]
        
        # CANCELLED → WAITING_PAYMENT is invalid
        assert OrderStatus.WAITING_PAYMENT not in TRANSITIONS[OrderStatus.CANCELLED]
        
        # COMPLETED → PENDING is invalid
        assert OrderStatus.PENDING not in TRANSITIONS[OrderStatus.COMPLETED]

    def test_no_self_transitions(self):
        """No status can transition to itself."""
        for status, allowed in TRANSITIONS.items():
            assert status not in allowed, f"{status} should not transition to itself"

    def test_full_happy_path(self):
        """Verify the full happy path is possible."""
        path = [
            OrderStatus.PENDING,
            OrderStatus.WAITING_PAYMENT,
            OrderStatus.PAYMENT_UPLOADED,
            OrderStatus.PAYMENT_REVIEWING,
            OrderStatus.APPROVED,
            OrderStatus.PREPARING,
            OrderStatus.DELIVERED,
            OrderStatus.COMPLETED,
        ]
        
        for i in range(len(path) - 1):
            current = path[i]
            next_status = path[i + 1]
            assert next_status in TRANSITIONS[current], (
                f"Transition {current} → {next_status} not allowed"
            )
