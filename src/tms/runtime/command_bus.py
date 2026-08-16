from collections.abc import Callable
from typing import Any


class CommandBus:
    """Small synchronous command registry used only to hand UI intent to controllers.

    `command_name` deliberately avoids the generic name `name`, because many valid
    business commands carry a payload field named `name` (for example a dataset name).
    """

    def __init__(self) -> None:
        self._handlers: dict[str, Callable[..., Any]] = {}

    def register(self, command_name: str, handler: Callable[..., Any]) -> None:
        self._handlers[command_name] = handler

    def dispatch(self, command_name: str, **payload: Any) -> Any:
        if command_name not in self._handlers:
            raise KeyError(f"No command handler for {command_name}")
        return self._handlers[command_name](**payload)
