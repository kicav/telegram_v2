from dataclasses import dataclass


@dataclass(slots=True)
class Dataset:
    id: int | None
    name: str
    source_type: str
    source_reference: str | None = None
    status: str = "READY"
    member_count: int = 0
