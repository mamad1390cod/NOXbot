"""Safe ``callback_data`` construction.

Why
---
Telegram rejects any inline button whose ``callback_data`` is longer than
**64 bytes** with ``Bad Request: BUTTON_DATA_INVALID``. The failure is *not*
local to the button: the whole ``sendMessage`` / ``editMessageText`` call fails,
so the user sees the previous screen and *every* button of that keyboard looks
dead. This project uses 36-char UUID primary keys, so any callback that carries
two ids (``acustom:pick:<custom_id>:<reg_id>``) blows the limit instantly.

How
---
``cb()`` builds callback data and guarantees the result fits:

* if the joined payload fits in 64 bytes it is returned unchanged (so existing
  ``F.data.startswith(...)`` filters and ``data.split(":")`` parsing keep
  working exactly as before);
* otherwise the payload is stored in a bounded, content-addressed registry and
  a short ``ct:<hash>`` reference is returned. ``CallbackTokenMiddleware``
  (registered as an *outer* middleware, i.e. before filters run) swaps the
  reference back to the full payload, so handlers never notice.

``ValueCodec`` gives a stable, restart-safe short code for a fixed set of
strings (used for RBAC permission names, which are long and would otherwise
push role callbacks over the limit).
"""

from __future__ import annotations

import hashlib
import logging
from collections import OrderedDict
from typing import Iterable

logger = logging.getLogger(__name__)

#: Telegram hard limit for callback_data, in UTF-8 bytes.
CALLBACK_DATA_LIMIT = 64

#: Prefix used for payloads that had to be stored out-of-band.
TOKEN_PREFIX = "ct:"


class CallbackTokenStore:
    """Bounded content-addressed store for oversized callback payloads.

    Content-addressed (token = hash of the payload) so re-rendering the same
    keyboard reuses the same token instead of growing the store.
    """

    def __init__(self, maxsize: int = 5000) -> None:
        self._maxsize = maxsize
        self._data: OrderedDict[str, str] = OrderedDict()

    @staticmethod
    def _token_for(payload: str) -> str:
        digest = hashlib.sha1(payload.encode("utf-8")).hexdigest()[:16]
        return f"{TOKEN_PREFIX}{digest}"

    def put(self, payload: str) -> str:
        token = self._token_for(payload)
        if token in self._data:
            self._data.move_to_end(token)
        else:
            self._data[token] = payload
            if len(self._data) > self._maxsize:
                self._data.popitem(last=False)
        return token

    def resolve(self, token: str) -> str | None:
        payload = self._data.get(token)
        if payload is not None:
            self._data.move_to_end(token)
        return payload

    def __len__(self) -> int:  # pragma: no cover - trivial
        return len(self._data)


#: Process-wide store used by :func:`cb` and the expansion middleware.
token_store = CallbackTokenStore()


def cb(*parts: object, sep: str = ":") -> str:
    """Join ``parts`` into callback data that always fits Telegram's limit."""
    payload = sep.join("" if p is None else str(p) for p in parts)
    if len(payload.encode("utf-8")) <= CALLBACK_DATA_LIMIT:
        return payload
    token = token_store.put(payload)
    logger.warning(
        "callback_data %r is %d bytes (>%d); using token %s",
        payload,
        len(payload.encode("utf-8")),
        CALLBACK_DATA_LIMIT,
        token,
    )
    return token


def is_token(data: str | None) -> bool:
    return bool(data) and data.startswith(TOKEN_PREFIX)  # type: ignore[union-attr]


def expand(data: str | None) -> str | None:
    """Return the real payload for a token, or ``data`` itself when it is not one.

    ``None`` means the token is unknown (store evicted it or the bot restarted).
    """
    if not is_token(data):
        return data
    return token_store.resolve(data)  # type: ignore[arg-type]


class ValueCodec:
    """Stable bidirectional short codes for a fixed set of string values.

    The code is derived from the value itself (not from its position), so codes
    stay valid when new values are added or the enum is reordered — old buttons
    keep working after a deploy.
    """

    def __init__(self, values: Iterable[str], length: int = 6) -> None:
        self._length = length
        self._to_code: dict[str, str] = {}
        self._from_code: dict[str, str] = {}
        for value in values:
            code = self._hash(value)
            if code in self._from_code and self._from_code[code] != value:
                raise ValueError(f"short-code collision between {value!r} and {self._from_code[code]!r}")
            self._to_code[value] = code
            self._from_code[code] = value

    def _hash(self, value: str) -> str:
        return hashlib.sha1(value.encode("utf-8")).hexdigest()[: self._length]

    def encode(self, value: str) -> str:
        return self._to_code.get(value, self._hash(value))

    def decode(self, code: str) -> str | None:
        return self._from_code.get(code)


def permission_codec() -> ValueCodec:
    """Short codes for :class:`bot.models.rbac.Permission` values (lazy import)."""
    from bot.models.rbac import Permission

    global _PERMISSION_CODEC
    if _PERMISSION_CODEC is None:
        _PERMISSION_CODEC = ValueCodec([p.value for p in Permission])
    return _PERMISSION_CODEC


_PERMISSION_CODEC: ValueCodec | None = None
