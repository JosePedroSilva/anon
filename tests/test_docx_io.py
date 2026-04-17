"""Round-trip and structural tests for docx_io."""

from __future__ import annotations

import zipfile
from pathlib import Path

from docx import Document as _DocxDocument

from docshield.core import docx_io


def _read_text(path: Path) -> str:
    return "\n".join(p.text for p in _DocxDocument(path).paragraphs)


def test_load_extracts_runs(simple_docx: Path) -> None:
    doc = docx_io.load(simple_docx)
    assert doc.runs, "expected at least one run"
    assert "Giulia Rossi" in doc.flat_text
    assert "ACME S.p.A." in doc.flat_text
    assert "IT60X0542811101000000123456" in doc.flat_text


def test_round_trip_preserves_text(simple_docx: Path, tmp_path: Path) -> None:
    """No mutations: load → save → reopen yields the same paragraph text."""
    doc = docx_io.load(simple_docx)
    out = tmp_path / "out.docx"
    docx_io.save(doc, out)
    assert _read_text(out) == _read_text(simple_docx)


def test_round_trip_preserves_zip_members(simple_docx: Path, tmp_path: Path) -> None:
    """All original zip parts (styles, rels, etc.) survive a round-trip."""
    doc = docx_io.load(simple_docx)
    out = tmp_path / "out.docx"
    docx_io.save(doc, out)
    with zipfile.ZipFile(simple_docx) as a, zipfile.ZipFile(out) as b:
        assert set(a.namelist()) == set(b.namelist())


def test_runs_for_range_handles_multi_run_span(simple_docx: Path) -> None:
    doc = docx_io.load(simple_docx)
    needle = "Giulia Rossi"
    idx = doc.flat_text.find(needle)
    assert idx >= 0
    spans = doc.runs_for_range(idx, idx + len(needle))
    rebuilt = "".join(run.text[s:e] for run, s, e in spans)
    assert rebuilt == needle


def test_set_text_marks_xml_space_preserve(simple_docx: Path, tmp_path: Path) -> None:
    doc = docx_io.load(simple_docx)
    # mutate a run with leading/trailing space
    target = next(r for r in doc.runs if "Contact " in r.text or r.text.startswith(" "))
    target.set_text("  padded  ")
    out = tmp_path / "mut.docx"
    docx_io.save(doc, out)
    reopened = docx_io.load(out)
    assert any(r.text == "  padded  " for r in reopened.runs)
