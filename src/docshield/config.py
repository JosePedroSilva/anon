"""User-scoped config + audit log paths (FR-7.2, FR-6.2).

We use ``platformdirs`` so the same code maps to ``%APPDATA%`` on Windows,
``~/Library/Application Support`` on macOS, and ``~/.config`` on Linux —
no admin rights required, satisfies NFR-1.2.
"""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from pathlib import Path

from platformdirs import user_config_dir, user_data_dir

APP_NAME = "DocShield"
APP_AUTHOR = "DocShield"


def config_path() -> Path:
    p = Path(user_config_dir(APP_NAME, APP_AUTHOR))
    p.mkdir(parents=True, exist_ok=True)
    return p / "settings.json"


def audit_log_path() -> Path:
    p = Path(user_data_dir(APP_NAME, APP_AUTHOR))
    p.mkdir(parents=True, exist_ok=True)
    return p / "audit.log"


@dataclass
class Settings:
    confidence_threshold: float = 0.6
    language_preference: str | None = None  # None = auto-detect
    default_output_dir: str | None = None
    allowlist: list[str] = field(default_factory=list)
    denylist: list[str] = field(default_factory=list)
    enabled_types: list[str] | None = None
    detect_dates: bool = False
    detect_money: bool = False
    password_hash: str | None = None  # set on first run

    @classmethod
    def load(cls, path: Path | None = None) -> "Settings":
        p = path or config_path()
        if not p.is_file():
            return cls()
        try:
            data = json.loads(p.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return cls()
        # Be lenient: ignore unknown keys so older builds don't crash on
        # newer config files.
        known = {f for f in cls.__dataclass_fields__}
        return cls(**{k: v for k, v in data.items() if k in known})

    def save(self, path: Path | None = None) -> Path:
        p = path or config_path()
        tmp = p.with_suffix(p.suffix + ".tmp")
        tmp.write_text(json.dumps(asdict(self), ensure_ascii=False, indent=2), encoding="utf-8")
        tmp.replace(p)
        return p
