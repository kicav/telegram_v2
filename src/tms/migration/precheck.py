from __future__ import annotations

from ..core.enums import TargetCoverage
from ..runtime.resource_governor import ResourceGovernor
from .models import PrecheckResult


class TargetPrecheck:
    def __init__(self, governor: ResourceGovernor | None = None) -> None:
        self.governor = governor

    async def run(
        self,
        gateway,
        account_id: int,
        group,
        page_limit: int = 200,
    ) -> PrecheckResult:
        ids: set[int] = set()
        coverage = TargetCoverage.COMPLETE
        try:
            if self.governor is None:
                async for page in gateway.iter_participant_pages(
                    account_id, group, 0, page_limit
                ):
                    ids.update(
                        int(member.telegram_user_id)
                        for member in page
                        if member.telegram_user_id is not None
                    )
            else:
                async with self.governor.read_slot():
                    async for page in gateway.iter_participant_pages(
                        account_id, group, 0, page_limit
                    ):
                        ids.update(
                            int(member.telegram_user_id)
                            for member in page
                            if member.telegram_user_id is not None
                        )
        except Exception:
            coverage = TargetCoverage.PARTIAL if ids else TargetCoverage.UNAVAILABLE
        return PrecheckResult(target_ids=ids, coverage=coverage)
