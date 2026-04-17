"""Test fixtures.

Builds tiny synthetic ``.docx`` files on disk so we don't need to ship
binary fixtures in the repo. ``python-docx`` is a runtime dependency anyway.
"""

from __future__ import annotations

from pathlib import Path

import pytest
from docx import Document as _DocxDocument


@pytest.fixture()
def simple_docx(tmp_path: Path) -> Path:
    """A 3-paragraph EN doc with one table and one styled run."""
    d = _DocxDocument()
    d.add_paragraph("Hello world.")
    p = d.add_paragraph("Contact ")
    p.add_run("Giulia Rossi").bold = True
    p.add_run(" at giulia@example.com.")
    table = d.add_table(rows=1, cols=2)
    table.rows[0].cells[0].text = "ACME S.p.A."
    table.rows[0].cells[1].text = "IBAN: IT60X0542811101000000123456"
    out = tmp_path / "sample.docx"
    d.save(out)
    return out


@pytest.fixture()
def italian_docx(tmp_path: Path) -> Path:
    d = _DocxDocument()
    d.add_paragraph("Il sig. Mario Bianchi risiede a Milano.")
    d.add_paragraph("Codice fiscale: BNCMRA80A01F205X.")
    d.add_paragraph("Email: mario.bianchi@studio.it, IBAN IT60X0542811101000000123456.")
    out = tmp_path / "italian.docx"
    d.save(out)
    return out
