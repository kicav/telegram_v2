from __future__ import annotations

from .handlers.account import AccountCommands
from .handlers.data import DataCommands
from .handlers.job import JobCommands
from .handlers.workflow import WorkflowCommands


class CommandHandlers:
    """Thin registry facade for V1.1 domain command handlers.

    UI code talks only to CommandBus.  Splitting handlers by domain keeps the command
    boundary easy to audit while preserving the locked execution domains.
    """

    def __init__(self, context) -> None:
        self.ctx = context
        self.accounts = AccountCommands(context)
        self.data = DataCommands(context)
        self.workflows = WorkflowCommands(context)
        self.jobs = JobCommands(context, self.workflows, self.data)

    def register_all(self) -> None:
        bus = self.ctx.commands
        self.accounts.register(bus)
        self.data.register(bus)
        self.workflows.register(bus)
        self.jobs.register(bus)

    async def prepare_shutdown(self, timeout: float = 3.0) -> None:
        await self.workflows.prepare_shutdown(timeout)

    def is_action_active(self, job_id: int) -> bool:
        return self.workflows.is_action_active(job_id)
