"""Append-only JSON-lines audit log (FR-6.1, FR-6.2)."""

from __future__ import annotations

import json
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

from .config import audit_log_path
from .core.entities import Detection


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def write_run(
    *,
    source: Path,
    output: Path,
    mapping: Path,
    detections: list[Detection],
    user: str,
    log_path: Path | None = None,
) -> Path:
    counts = Counter(d.entity_type for d in detections)
    entry = {
        "ts": _utc_now(),
        "file": source.name,
        "entities": dict(counts),
        "output": str(output),
        "mapping": str(mapping),
        "user": user,
    }
    target = log_path or audit_log_path()
    with target.open("a", encoding="utf-8") as f:
        f.write(json.dumps(entry, ensure_ascii=False) + "\n")
    return target
