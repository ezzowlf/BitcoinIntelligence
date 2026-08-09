from __future__ import annotations

from dataclasses import dataclass
import os
from pathlib import Path


def _flag(name: str, default: bool = False, values=None) -> bool:
    source=os.environ if values is None else values
    return source.get(name, str(default)).strip().lower() in {"1", "true", "yes", "on"}

def _env_values(path:Path):
    values=dict(os.environ)
    if not path.exists():return values
    for raw in path.read_text(encoding="utf-8-sig").splitlines():
        line=raw.strip()
        if not line or line.startswith("#") or "=" not in line:continue
        name,value=line.split("=",1);name=name.strip();value=value.strip().strip('"').strip("'")
        if name and name not in values:values[name]=value
    return values


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
        values=_env_values(root/".env")
        if _flag("BITCOIN_EXECUTION_ENABLED",values=values) or values.get("EXECUTION","DISABLED").upper()!="DISABLED":raise RuntimeError("Trading execution is not implemented and must remain DISABLED")
        home = Path(values.get("BITCOIN_HOME", root))
        token = values.get("TELEGRAM_BOT_TOKEN") or None
        chat_id = values.get("TELEGRAM_CHAT_ID") or None
        enabled = _flag("TELEGRAM_ENABLED",values=values)
        requested_dry = _flag("TELEGRAM_DRY_RUN", True,values)
        return cls(
            home=home,
            app_dir=Path(values.get("BITCOIN_APP_DIR", root)),
            data_dir=Path(values.get("BITCOIN_DATA_DIR", home / "data")),
            log_dir=Path(values.get("BITCOIN_LOG_DIR", home / "logs")),
            forward_dir=Path(values.get("BITCOIN_FORWARD_DIR", home / "forward")),
            backup_dir=Path(values.get("BITCOIN_BACKUP_DIR", home / "backups")),
            telegram_enabled=enabled,
            telegram_dry_run=requested_dry or not (enabled and token and chat_id),
            telegram_token=token,
            telegram_chat_id=chat_id,
            daily_summary=_flag("DAILY_SUMMARY",values=values),
            telegram_candidate_alerts=_flag("TELEGRAM_CANDIDATE_ALERTS",values=values),
        )

    def ensure_layout(self):
        if self.execution != "DISABLED":
            raise RuntimeError("Execution must remain DISABLED")
        for path in (self.data_dir, self.log_dir, self.forward_dir, self.backup_dir):
            path.mkdir(parents=True, exist_ok=True)
