from __future__ import annotations

from dataclasses import dataclass
import os
from pathlib import Path


def _flag(name: str, default: bool = False) -> bool:
    return os.getenv(name, str(default)).strip().lower() in {"1", "true", "yes", "on"}


@dataclass(frozen=True)
class RuntimeSettings:
    home: Path
    app_dir: Path
    data_dir: Path
    log_dir: Path
    forward_dir: Path
    backup_dir: Path
    telegram_enabled: bool
    telegram_dry_run: bool
    telegram_token: str | None
    telegram_chat_id: str | None
    daily_summary: bool
    telegram_candidate_alerts: bool
    execution: str = "DISABLED"

    @classmethod
    def from_env(cls, project_root: Path | None = None):
        root = Path(project_root or Path.cwd()).resolve()
        home = Path(os.getenv("BITCOIN_HOME", root))
        token = os.getenv("TELEGRAM_BOT_TOKEN") or None
        chat_id = os.getenv("TELEGRAM_CHAT_ID") or None
        enabled = _flag("TELEGRAM_ENABLED")
        requested_dry = _flag("TELEGRAM_DRY_RUN", True)
        return cls(
            home=home,
            app_dir=Path(os.getenv("BITCOIN_APP_DIR", root)),
            data_dir=Path(os.getenv("BITCOIN_DATA_DIR", home / "data")),
            log_dir=Path(os.getenv("BITCOIN_LOG_DIR", home / "logs")),
            forward_dir=Path(os.getenv("BITCOIN_FORWARD_DIR", home / "forward")),
            backup_dir=Path(os.getenv("BITCOIN_BACKUP_DIR", home / "backups")),
            telegram_enabled=enabled,
            telegram_dry_run=requested_dry or not (enabled and token and chat_id),
            telegram_token=token,
            telegram_chat_id=chat_id,
            daily_summary=_flag("DAILY_SUMMARY"),
            telegram_candidate_alerts=_flag("TELEGRAM_CANDIDATE_ALERTS"),
        )

    def ensure_layout(self):
        if self.execution != "DISABLED":
            raise RuntimeError("Execution must remain DISABLED")
        for path in (self.data_dir, self.log_dir, self.forward_dir, self.backup_dir):
            path.mkdir(parents=True, exist_ok=True)
