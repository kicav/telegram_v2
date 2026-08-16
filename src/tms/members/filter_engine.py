from .models import Member
from .filter_spec import FilterSpec


class FilterEngine:
    def apply(self, members: list[Member], spec: FilterSpec) -> list[Member]:
        result: list[Member] = []
        seen: set[tuple[str, str]] = set()
        for member in members:
            key = member.identity_key
            if key is None or key in seen:
                continue
            seen.add(key)
            if spec.exclude_bot and member.bot:
                continue
            if spec.exclude_deleted and member.deleted:
                continue
            if spec.username_required and not member.username:
                continue
            if spec.activity and (member.activity_status or "") not in spec.activity:
                continue
            if member.telegram_user_id is not None:
                if member.telegram_user_id in spec.exclude_processed:
                    continue
                if member.telegram_user_id in spec.exclude_target:
                    continue
            result.append(member)
        return result
