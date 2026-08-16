from __future__ import annotations


class GroupMembershipUtility:
    def __init__(self, gateway, governor) -> None:
        self.gateway = gateway
        self.governor = governor

    async def join(self, account_id: int, reference: str):
        async with self.governor.mutation_lock(account_id):
            return await self.gateway.join_group(account_id, reference)

    async def leave(self, account_id: int, group) -> None:
        async with self.governor.mutation_lock(account_id):
            await self.gateway.leave_group(account_id, group)
