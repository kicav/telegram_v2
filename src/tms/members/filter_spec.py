from dataclasses import dataclass, field


@dataclass(slots=True)
class FilterSpec:
    exclude_bot: bool = True
    exclude_deleted: bool = True
    username_required: bool = False
    activity: set[str] = field(default_factory=set)
    source: set[str] = field(default_factory=set)
    exclude_processed: set[int] = field(default_factory=set)
    exclude_target: set[int] = field(default_factory=set)
