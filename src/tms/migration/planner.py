from __future__ import annotations

from ..core.enums import (
    ActionType,
    JobState,
    JobType,
    TargetCoverage,
    TargetMemberState,
)
from ..jobs.models import Job
from ..jobs.repository import JobRepository
from ..members.filter_spec import FilterSpec
from ..storage.database import Database
from .models import MigrationPlanSummary, PrecheckResult


class MigrationPlanner:
    def __init__(self, db: Database, jobs: JobRepository) -> None:
        self.db = db
        self.jobs = jobs

    def _source_rows(
        self,
        account_id: int,
        source_dataset_id: int,
        spec: FilterSpec,
    ) -> tuple[list, dict[int, set[str]], set[str]]:
        source_filter = {value.casefold() for value in spec.source if value.strip()}
        source_map: dict[int, set[str]] = {}
        with self.db.reader() as conn:
            rows = conn.execute(
                """SELECT
                       m.id,m.telegram_user_id,m.username,m.bot,m.deleted,
                       m.activity_status,pc.access_hash
                   FROM dataset_members dm
                   JOIN members m ON m.id=dm.member_id
                   LEFT JOIN peer_cache pc
                     ON pc.account_id=? AND pc.peer_id=m.telegram_user_id
                   WHERE dm.dataset_id=?
                   ORDER BY dm.member_id""",
                (account_id, source_dataset_id),
            ).fetchall()
            if source_filter:
                provenance_rows = conn.execute(
                    """SELECT member_id,source_label
                       FROM dataset_provenance
                       WHERE dataset_id=? AND source_label IS NOT NULL""",
                    (source_dataset_id,),
                ).fetchall()
                for provenance in provenance_rows:
                    source_map.setdefault(int(provenance["member_id"]), set()).add(
                        str(provenance["source_label"]).casefold()
                    )
        return list(rows), source_map, source_filter

    @staticmethod
    def _passes_local_filters(
        row,
        spec: FilterSpec,
        source_map: dict[int, set[str]],
        source_filter: set[str],
    ) -> bool:
        if spec.exclude_bot and bool(row["bot"]):
            return False
        if spec.exclude_deleted and bool(row["deleted"]):
            return False
        if spec.username_required and not row["username"]:
            return False
        if spec.activity and str(row["activity_status"] or "") not in spec.activity:
            return False
        if source_filter and not (source_map.get(int(row["id"]), set()) & source_filter):
            return False
        return True

    def create_plan(
        self,
        account_id: int,
        source_dataset_id: int,
        target_group_id: int,
        precheck: PrecheckResult,
        filter_spec: FilterSpec | None = None,
    ) -> tuple[int, MigrationPlanSummary]:
        """Create an INVITE plan. Kept as the V1 compatibility entry point."""
        spec = filter_spec or FilterSpec()
        processed_ids = self.jobs.processed_user_ids_for_target(target_group_id)
        rows, source_map, source_filter = self._source_rows(
            account_id, source_dataset_id, spec
        )

        total = len(rows)
        invalid = 0
        filtered = 0
        already = 0
        ready_items: list[tuple[int, str]] = []
        seen: set[int] = set()

        for row in rows:
            uid = row["telegram_user_id"]
            if uid is None or row["access_hash"] is None:
                invalid += 1
                continue
            uid = int(uid)
            if uid in seen:
                filtered += 1
                continue
            seen.add(uid)
            if not self._passes_local_filters(row, spec, source_map, source_filter):
                filtered += 1
                continue
            if uid in processed_ids or uid in spec.exclude_processed:
                filtered += 1
                continue
            if uid in spec.exclude_target:
                filtered += 1
                continue
            if uid in precheck.target_ids:
                already += 1
                continue

            target_state = (
                TargetMemberState.KNOWN_ABSENT
                if precheck.coverage == TargetCoverage.COMPLETE
                else TargetMemberState.UNKNOWN_TARGET_STATE
            )
            ready_items.append((int(row["id"]), str(target_state)))

        job = Job(
            id=None,
            job_type=JobType.MIGRATION,
            state=JobState.READY,
            account_id=account_id,
            source_dataset_id=source_dataset_id,
            target_group_id=target_group_id,
            total=len(ready_items),
        )
        job_id = self.jobs.create(job)
        self.jobs.submit_add_items(job_id, ready_items).result(timeout=30.0)
        summary = MigrationPlanSummary(
            total_source=total,
            filtered=filtered,
            already_target=already,
            invalid=invalid,
            ready=len(ready_items),
            action=ActionType.INVITE,
        )
        return job_id, summary

    def create_remove_plan(
        self,
        account_id: int,
        source_dataset_id: int,
        target_group_id: int,
        precheck: PrecheckResult,
        filter_spec: FilterSpec | None = None,
    ) -> tuple[int, MigrationPlanSummary]:
        """Create a conservative REMOVE plan from members known to be in the target.

        A remove job never acts on an unknown target state. With PARTIAL coverage it
        only includes the IDs that were actually observed; with UNAVAILABLE coverage it
        refuses to create actionable candidates.
        """
        spec = filter_spec or FilterSpec(exclude_bot=False, exclude_deleted=False)
        rows, source_map, source_filter = self._source_rows(
            account_id, source_dataset_id, spec
        )
        with self.db.reader() as conn:
            own_row = conn.execute(
                "SELECT telegram_user_id FROM accounts WHERE id=?", (account_id,)
            ).fetchone()
        own_user_id = (
            int(own_row[0])
            if own_row is not None and own_row[0] is not None
            else None
        )
        total = len(rows)
        invalid = 0
        filtered = 0
        not_in_target = 0
        ready_items: list[tuple[int, str]] = []
        seen: set[int] = set()

        for row in rows:
            uid = row["telegram_user_id"]
            if uid is None or row["access_hash"] is None:
                invalid += 1
                continue
            uid = int(uid)
            if own_user_id is not None and uid == own_user_id:
                # Never let a REMOVE job kick the account operating the job.
                filtered += 1
                continue
            if uid in seen:
                filtered += 1
                continue
            seen.add(uid)
            if not self._passes_local_filters(row, spec, source_map, source_filter):
                filtered += 1
                continue
            if uid not in precheck.target_ids:
                not_in_target += 1
                continue
            ready_items.append((int(row["id"]), str(TargetMemberState.KNOWN_PRESENT)))

        job = Job(
            id=None,
            job_type=JobType.REMOVE,
            state=JobState.READY,
            account_id=account_id,
            source_dataset_id=source_dataset_id,
            target_group_id=target_group_id,
            total=len(ready_items),
        )
        job_id = self.jobs.create(job)
        self.jobs.submit_add_items(job_id, ready_items).result(timeout=30.0)
        summary = MigrationPlanSummary(
            total_source=total,
            filtered=filtered,
            already_target=0,
            invalid=invalid,
            ready=len(ready_items),
            not_in_target=not_in_target,
            action=ActionType.REMOVE,
        )
        return job_id, summary
