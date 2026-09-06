"""
Request context middleware for logging.

Automatically sets request_id and user context for each Telegram update,
ensuring all logs within a single update are correlated.
"""

import logging
from typing import Callable, Dict, Any, Awaitable

from aiogram import BaseMiddleware
from aiogram.types import Update, TelegramObject

from bot.core.logging import (
    set_request_id,
    set_user_context,
    clear_context,
)


logger = logging.getLogger(__name__)


class RequestContextMiddleware(BaseMiddleware):
    """
    Middleware that sets request context for each update.
    
    For each incoming update:
    1. Generates a unique request_id
    2. Extracts user information (if available)
    3. Sets the context for logging
    4. Clears context after processing
    """
    
    async def __call__(
        self,
        handler: Callable[[TelegramObject, Dict[str, Any]], Awaitable[Any]],
        event: TelegramObject,
        data: Dict[str, Any],
    ) -> Any:
        # Generate request ID
        request_id = set_request_id()
        
        # Extract user info if available
        user_info = {}
        if isinstance(event, Update):
            # Try to extract user from different update types
            user = None
            chat_id = None
            
            if event.message:
                user = event.message.from_user
                chat_id = event.message.chat.id
            elif event.callback_query:
                user = event.callback_query.from_user
                chat_id = event.callback_query.message.chat.id if event.callback_query.message else None
            elif event.inline_query:
                user = event.inline_query.from_user
            elif event.chosen_inline_result:
                user = event.chosen_inline_result.from_user
            elif event.edited_message:
                user = event.edited_message.from_user
                chat_id = event.edited_message.chat.id
            
            if user:
                user_info['user_id'] = str(user.id)
                user_info['username'] = user.username
                user_info['chat_id'] = chat_id
                
                # Check if user is admin (from data context)
                if 'user' in data and hasattr(data['user'], 'is_admin'):
                    user_info['is_admin'] = data['user'].is_admin
            
            # Set user context
            if user_info:
                set_user_context(**user_info)
        
        try:
            # Process the update
            result = await handler(event, data)
            return result
        finally:
            # Clear context after processing
            clear_context()


def register_request_context_middleware(dp) -> None:
    """Register the request context middleware with the dispatcher."""
    dp.update.outer_middleware(RequestContextMiddleware())
    logger.info("Request context middleware registered")
