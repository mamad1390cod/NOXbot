"""Base service class."""

from bot.database.uow import UnitOfWork


class BaseService:
    """Base service with Unit of Work."""

    def __init__(self, uow: UnitOfWork) -> None:
        self.uow = uow