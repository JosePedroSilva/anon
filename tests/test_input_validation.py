"""Input validation: file type gate + soft/hard size limits."""

from __future__ import annotations

from pathlib import Path

import pytest

from docshield.core.input_validation import (
    MAX_FILE_SIZE_MB,
    WARN_FILE_SIZE_MB,
    has_error,
    validate_docx,
)


def test_nonexistent_file_errors(tmp_path: Path) -> None:
    issues = validate_docx(tmp_path / "does_not_exist.docx")
    assert has_error(issues)


def test_wrong_extension_errors(tmp_path: Path) -> None:
    pdf = tmp_path / "brief.pdf"
    pdf.write_bytes(b"%PDF-1.4")
    issues = validate_docx(pdf)
    assert has_error(issues)
    assert ".pdf" in issues[0].message.lower() or "docx" in issues[0].message.lower()


def test_small_docx_has_no_issues(simple_docx: Path) -> None:
    assert validate_docx(simple_docx) == []


def test_above_warn_threshold_gives_warning(tmp_path: Path) -> None:
    """Sparse-file trick: allocate the byte we need without writing all of it."""
    big = tmp_path / "big.docx"
    size = int((WARN_FILE_SIZE_MB + 5) * 1024 * 1024)
    with open(big, "wb") as f:
        f.seek(size - 1)
        f.write(b"\x00")
    issues = validate_docx(big)
    assert not has_error(issues)
    assert any(i.severity == "warning" for i in issues)


def test_above_hard_cap_errors(tmp_path: Path) -> None:
    huge = tmp_path / "huge.docx"
    size = int((MAX_FILE_SIZE_MB + 1) * 1024 * 1024)
    with open(huge, "wb") as f:
        f.seek(size - 1)
        f.write(b"\x00")
    issues = validate_docx(huge)
    assert has_error(issues)
