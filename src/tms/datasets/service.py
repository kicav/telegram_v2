from __future__ import annotations

from .set_operations import difference, intersection, union
from .models import Dataset
from .repository import DatasetRepository


class DatasetService:
    def __init__(self, repo: DatasetRepository) -> None:
        self.repo = repo

    def combine(self, name: str, a_id: int, b_id: int, op: str) -> int:
        normalized_op = op.upper()
        engines = {
            "UNION": union,
            "MERGE": union,
            "INTERSECTION": intersection,
            "DIFFERENCE": difference,
        }
        if normalized_op not in engines:
            raise ValueError(f"Unsupported dataset operation: {op}")

        a = self.repo.identity_map(a_id)
        b = self.repo.identity_map(b_id)
        keys = engines[normalized_op](set(a), set(b))
        local_ids: list[int] = []
        for key in keys:
            if key in a:
                local_ids.append(a[key])
            elif key in b:
                local_ids.append(b[key])

        dataset_id = self.repo.create(
            Dataset(
                None,
                name,
                "UNION" if normalized_op == "MERGE" else normalized_op,
                f"{a_id},{b_id}",
            )
        )
        # Preserve both source datasets as provenance for members they contributed.
        a_ids = [a[key] for key in keys if key in a]
        b_ids = [b[key] for key in keys if key in b]
        if a_ids:
            self.repo.submit_add_member_ids(
                dataset_id,
                a_ids,
                source_dataset_id=a_id,
                source_label=f"dataset:{a_id}",
            ).result(timeout=30.0)
        if b_ids:
            self.repo.submit_add_member_ids(
                dataset_id,
                b_ids,
                source_dataset_id=b_id,
                source_label=f"dataset:{b_id}",
            ).result(timeout=30.0)
        return dataset_id
