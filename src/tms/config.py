from __future__ import annotations

from dataclasses import asdict, dataclass
import json
import os
from pathlib import Path

from .core.constants import (
    APP_DIR_NAME,
    DEFAULT_INVITE_INTERVAL_SECONDS,
    MAX_INVITE_INTERVAL_SECONDS,
    MIN_INVITE_INTERVAL_SECONDS,
)


@dataclass(frozen=True, slots=True)
class AppPaths:
    root: Path
    data: Path
    sessions: Path
    cache: Path
    temp: Path
    logs: Path
    exports: Path
    backups: Path

    @classmethod
    def discover(cls) -> "AppPaths":
        local = Path(os.environ.get("LOCALAPPDATA", Path.home() / ".local" / "share"))
        root = local / APP_DIR_NAME
        paths = cls(
            root=root,
            data=root / "data",
            sessions=root / "sessions",
            cache=root / "cache",
            temp=root / "temp",
            logs=root / "logs",
            exports=root / "exports",
            backups=root / "backups",
        )
        for path in (
            paths.root,
            paths.data,
            paths.sessions,
            paths.cache,
            paths.temp,
            paths.logs,
            paths.exports,
            paths.backups,
        ):
            path.mkdir(parents=True, exist_ok=True)
        return paths


@dataclass(slots=True)
class Settings:
    api_id: int | None = None
    api_hash: str | None = None
    invite_interval_seconds: float = DEFAULT_INVITE_INTERVAL_SECONDS

    @classmethod
    def load(cls, paths: AppPaths) -> "Settings":
        config_path = paths.root / "settings.json"
        payload: dict = {}
        if config_path.exists():
            try:
                raw = json.loads(config_path.read_text(encoding="utf-8"))
                if isinstance(raw, dict):
                    payload = raw
            except (OSError, json.JSONDecodeError):
                payload = {}
        env_id = os.getenv("TMS_TELEGRAM_API_ID")
        env_hash = os.getenv("TMS_TELEGRAM_API_HASH")
        raw_id = env_id if env_id is not None else payload.get("api_id")
        api_id: int | None
        try:
            api_id = int(raw_id) if raw_id not in (None, "") else None
        except (TypeError, ValueError):
            api_id = None
        interval = payload.get("invite_interval_seconds", DEFAULT_INVITE_INTERVAL_SECONDS)
        try:
            interval_value = float(interval)
        except (TypeError, ValueError):
            interval_value = DEFAULT_INVITE_INTERVAL_SECONDS
        if not MIN_INVITE_INTERVAL_SECONDS <= interval_value <= MAX_INVITE_INTERVAL_SECONDS:
            interval_value = DEFAULT_INVITE_INTERVAL_SECONDS
        return cls(
            api_id=api_id,
            api_hash=env_hash if env_hash is not None else payload.get("api_hash"),
            invite_interval_seconds=interval_value,
        )

    @classmethod
    def from_environment(cls) -> "Settings":
        raw_id = os.getenv("TMS_TELEGRAM_API_ID")
        return cls(
            api_id=int(raw_id) if raw_id else None,
            api_hash=os.getenv("TMS_TELEGRAM_API_HASH"),
        )

    def save(self, paths: AppPaths) -> None:
        config_path = paths.root / "settings.json"
        config_path.write_text(
            json.dumps(asdict(self), ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
