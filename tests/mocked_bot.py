"""A Bot whose Telegram session is mocked, for offline handler tests.

``feed_update`` on a real ``Dispatcher`` needs a ``Bot``; every API call the
handlers make (``answer``, ``edit_text``, ``send_message`` ...) is intercepted
here and answered with a plausible object instead of hitting api.telegram.org.
That lets the test-suite *actually run* the handler code paths — the only way
to catch ``AttributeError``/``TypeError`` bugs that a static scan cannot see.
"""

from __future__ import annotations

import datetime as dt
from typing import Any

from aiogram import Bot
from aiogram.client.default import DefaultBotProperties
from aiogram.client.session.base import BaseSession
from aiogram.enums import ParseMode
from aiogram.methods import TelegramMethod
from aiogram.methods.base import TelegramType
from aiogram.types import Chat, Message, PhotoSize, User as TgUser

BOT_ID = 8726649647
BOT_USERNAME = "NOX_kastom_bot"


class MockedSession(BaseSession):
    """Records outgoing API calls and returns canned results."""

    def __init__(self) -> None:
        super().__init__()
        self.calls: list[TelegramMethod[Any]] = []

    async def close(self) -> None:  # pragma: no cover - nothing to close
        pass

    async def stream_content(self, *args: Any, **kwargs: Any):  # pragma: no cover
        yield b""

    async def make_request(
        self,
        bot: Bot,
        method: TelegramMethod[TelegramType],
        timeout: int | None = None,
    ) -> TelegramType:
        self.calls.append(method)
        return self._result_for(bot, method)

    # --- canned results ---------------------------------------------------- #
    @staticmethod
    def _fake_message(bot: Bot, method: TelegramMethod[Any]) -> Message:
        chat_id = getattr(method, "chat_id", 1) or 1
        text = getattr(method, "text", None) or getattr(method, "caption", None)
        photo = None
        if getattr(method, "photo", None) is not None:
            photo = [PhotoSize(file_id="f", file_unique_id="u", width=1, height=1)]
        message = Message(
            message_id=1,
            date=dt.datetime.now(dt.timezone.utc),
            chat=Chat(id=int(chat_id) if str(chat_id).lstrip("-").isdigit() else 1, type="private"),
            from_user=TgUser(id=BOT_ID, is_bot=True, first_name="NOX", username=BOT_USERNAME),
            text=text if photo is None else None,
            caption=text if photo is not None else None,
            photo=photo,
        )
        return message.as_(bot)

    def _result_for(self, bot: Bot, method: TelegramMethod[Any]) -> Any:
        name = type(method).__name__
        if name == "GetMe":
            return TgUser(id=BOT_ID, is_bot=True, first_name="NOX shoop", username=BOT_USERNAME)
        if name in {
            "SendMessage",
            "SendPhoto",
            "SendVideo",
            "SendDocument",
            "EditMessageText",
            "EditMessageCaption",
            "EditMessageMedia",
            "EditMessageReplyMarkup",
            "CopyMessage",
            "ForwardMessage",
        }:
            return self._fake_message(bot, method)
        if name in {"GetChat"}:
            return Chat(id=1, type="private")
        # answerCallbackQuery, deleteMessage, setMyCommands, ...
        return True


def make_mocked_bot() -> tuple[Bot, MockedSession]:
    session = MockedSession()
    bot = Bot(
        token=f"{BOT_ID}:TEST-TOKEN-FOR-OFFLINE-TESTS",
        session=session,
        default=DefaultBotProperties(parse_mode=ParseMode.HTML),
    )
    return bot, session
