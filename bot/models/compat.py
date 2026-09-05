"""Keeps the ORM working when a model is added outside this package.

The problem
-----------
``back_populates`` needs **both** sides of a relationship to be declared. A
model that lives in its own file, e.g.::

    class TopUpRequest(Base, UUIDMixin, TimestampMixin):
        user_id = mapped_column(ForeignKey("users.id"))
        user = relationship("User", back_populates="topup_requests")

only works if ``User`` also declares ``topup_requests``. When it does not,
SQLAlchemy refuses to configure *any* mapper::

    Mapper 'Mapper[User(users)]' has no property 'topup_requests'

and from that moment every single query in the bot fails - the whole thing
looks dead even though only one file is out of sync.

The fix
-------
Just before SQLAlchemy configures the mappers, walk every declared
relationship, find the ones whose ``back_populates`` counterpart is missing,
and create that counterpart automatically (one-to-many on the parent side,
derived from the foreign keys). Each repair is logged as a warning so the
missing declaration can be added properly later.

This never invents a relationship out of thin air: it only completes a link
that a model explicitly asked for.
"""

from __future__ import annotations

import logging
from typing import Any

from sqlalchemy import event, inspect
from sqlalchemy.orm import Mapper, relationship

from bot.models.base import Base

logger = logging.getLogger(__name__)

#: "User.topup_requests" -> "TopUpRequest.user", filled by :func:`heal_back_populates`.
HEALED_RELATIONSHIPS: dict[str, str] = {}


def _mapped_classes() -> list[type]:
    classes: list[type] = []
    for value in Base.registry._class_registry.values():  # noqa: SLF001 - no public API
        if isinstance(value, type) and hasattr(value, "__mapper__"):
            classes.append(value)
    return classes


def _resolve(argument: Any) -> type | None:
    """Turn a relationship target (class, string or callable) into a class."""
    if isinstance(argument, type):
        return argument
    if callable(argument):
        try:
            resolved = argument()
            return resolved if isinstance(resolved, type) else None
        except Exception:  # pragma: no cover - lazy callables can need config
            return None
    if isinstance(argument, str):
        name = argument.split("[")[-1].strip("]'\" ")
        target = Base.registry._class_registry.get(name)  # noqa: SLF001
        return target if isinstance(target, type) else None
    return None


def heal_back_populates() -> dict[str, str]:
    """Create every missing ``back_populates`` counterpart. Returns the repairs."""
    repaired: dict[str, str] = {}

    for cls in _mapped_classes():
        mapper = cls.__mapper__
        for prop in list(mapper._props.values()):  # noqa: SLF001 - pre-configuration view
            back = getattr(prop, "back_populates", None)
            if not back or not hasattr(prop, "argument"):
                continue

            target = _resolve(prop.argument)
            if target is None or hasattr(target, back):
                continue

            # `cls` declares "target.<back>" but the target does not have it.
            # cls holds the foreign key, so the target side is the "one" side.
            try:
                fk_columns = [
                    column
                    for column in inspect(cls).local_table.columns
                    if any(fk.column.table is inspect(target).local_table for fk in column.foreign_keys)
                ]
                kwargs: dict[str, Any] = {
                    "back_populates": prop.key,
                    "uselist": True,
                    "cascade": "all, delete-orphan",
                }
                if len(fk_columns) > 1 or getattr(prop, "_user_defined_foreign_keys", None):
                    kwargs["foreign_keys"] = list(
                        getattr(prop, "_user_defined_foreign_keys", None) or fk_columns
                    )
                setattr(target, back, relationship(cls, **kwargs))
            except Exception as exc:  # noqa: BLE001 - reported, never hidden
                logger.error(
                    "could not complete %s.%s <-> %s.%s: %s",
                    cls.__name__, prop.key, target.__name__, back, exc,
                )
                continue

            repaired[f"{target.__name__}.{back}"] = f"{cls.__name__}.{prop.key}"
            logger.warning(
                "%s.%s was missing (needed by %s.%s) - created automatically; "
                "declare it in %s for clarity",
                target.__name__, back, cls.__name__, prop.key, target.__module__,
            )

    HEALED_RELATIONSHIPS.update(repaired)
    return repaired


@event.listens_for(Mapper, "before_configured")
def _heal_before_configure() -> None:
    """Run the repair right before SQLAlchemy validates the mappers."""
    heal_back_populates()
