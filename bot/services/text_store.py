"""Synchronous text store for keyboard builders and other sync contexts.

The async SettingsService owns the authoritative cache (``_CACHE``). This
module mirrors it into a process-wide dict that synchronous keyboard builders
can read without awaiting. ``sync_from_async()`` refreshes the mirror after
``load_cache()``/``set()``.

Handlers that already have a ``uow`` should prefer the async
``TextResolver``/``SettingsService``; this store is for sync helpers such as
``bot/keyboards/common.py``.
"""

from bot.services.settings_registry import spec_for

# Mirror of the authoritative settings cache (populated at startup and after
# every write via sync_from_async).
_CACHE: dict[str, str] = {}


def sync_from_cache(cache: dict[str, str]) -> None:
    """Replace the mirror with the current authoritative cache."""
    _CACHE.clear()
    _CACHE.update(cache)


def get(key: str, default: str = "") -> str:
    return _CACHE.get(key, default)


def t(key: str, **vars) -> str:
    """Resolve a template synchronously (best-effort)."""
    spec = spec_for(key)
    default = spec.default if spec else ""
    template = _CACHE.get(key, default) or ""
    if not template:
        return ""
    try:
        return template.format_map(vars)
    except (KeyError, ValueError):
        return template


def button(key: str) -> str:
    spec = spec_for(key)
    default = spec.default if spec else key
    return _CACHE.get(key, default) or default


def feature(feature_key: str) -> bool:
    val = _CACHE.get(feature_key, "true")
    return val.lower() in ("true", "1", "yes", "on")