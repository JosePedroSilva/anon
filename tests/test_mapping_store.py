"""Mapping store round-trip + bad-password rejection."""

from __future__ import annotations

from pathlib import Path

import pytest

from docshield.core.mapping_store import MappingFile, MappingStoreError, load, save


def _sample() -> MappingFile:
    return MappingFile(
        source_file="Contract_ACME.docx",
        language="it",
        entries=[
            {"placeholder": "[PERSON_1]", "original": "Giulia Rossi", "type": "PERSON"},
            {"placeholder": "[ORG_1]", "original": "ACME S.p.A.", "type": "ORG"},
        ],
    )


def test_round_trip_with_correct_password(tmp_path: Path) -> None:
    out = tmp_path / "m.dsm"
    save(out, _sample(), password="correct horse battery staple")
    got = load(out, password="correct horse battery staple")
    assert got.source_file == "Contract_ACME.docx"
    assert got.entries[0]["original"] == "Giulia Rossi"


def test_wrong_password_raises(tmp_path: Path) -> None:
    out = tmp_path / "m.dsm"
    save(out, _sample(), password="hunter2")
    with pytest.raises(MappingStoreError):
        load(out, password="wrong")


def test_corrupt_file_raises(tmp_path: Path) -> None:
    out = tmp_path / "m.dsm"
    out.write_bytes(b"garbage")
    with pytest.raises(MappingStoreError):
        load(out, password="anything")


def test_distinct_salts_per_save(tmp_path: Path) -> None:
    """Two saves of the same mapping with the same password produce
    different ciphertexts (per-file salt)."""
    a = tmp_path / "a.dsm"
    b = tmp_path / "b.dsm"
    save(a, _sample(), password="pw")
    save(b, _sample(), password="pw")
    assert a.read_bytes() != b.read_bytes()
