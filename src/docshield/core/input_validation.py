"""Input file validation (FR-1.4, FR-1.5).

The spec's original 50 MB cap turned out to be conservative — a .docx is
ZIP-compressed XML, so real legal documents rarely cross 20 MB. We lift
the hard cap to 200 MB and emit a soft warning above 30 MB where
memory pressure starts to matter (NFR-2.3's 1.5 GB budget).
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

MAX_FILE_SIZE_MB = 200
WARN_FILE_SIZE_MB = 30


@dataclass
class ValidationIssue:
    severity: str  # "error" | "warning"
    message: str


def validate_docx(path: Path) -> list[ValidationIssue]:
    """Return any blocking errors or soft warnings for ``path``.

    Callers decide what to do with warnings (prompt, ignore, log). Errors
    are hard: the pipeline must not run on that file.
    """
    issues: list[ValidationIssue] = []
    if not path.exists():
        return [ValidationIssue("error", f"File not found: {path}")]
    if not path.is_file():
        return [ValidationIssue("error", f"Not a file: {path}")]
    if path.suffix.lower() != ".docx":
        return [ValidationIssue("error", f"Unsupported file type: {path.suffix or '(none)'}. Only .docx is accepted.")]
    size_mb = path.stat().st_size / (1024 * 1024)
    if size_mb > MAX_FILE_SIZE_MB:
        issues.append(
            ValidationIssue(
                "error",
                f"{path.name} is {size_mb:.0f} MB, above the {MAX_FILE_SIZE_MB} MB limit.",
            )
        )
    elif size_mb > WARN_FILE_SIZE_MB:
        issues.append(
            ValidationIssue(
                "warning",
                f"{path.name} is {size_mb:.0f} MB; detection may be slow and use significant memory.",
            )
        )
    return issues


def has_error(issues: list[ValidationIssue]) -> bool:
    return any(i.severity == "error" for i in issues)
