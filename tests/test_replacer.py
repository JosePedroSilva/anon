"""Replacer correctness: single-run, multi-run spans, ordering."""

from __future__ import annotations

from pathlib import Path

from docx import Document as _DocxDocument

from docshield.core import docx_io, replacer
from docshield.core.entities import Detection, Replacement


def _read_text(path: Path) -> str:
    d = _DocxDocument(path)
    chunks = [p.text for p in d.paragraphs]
    for tbl in d.tables:
        for row in tbl.rows:
            for cell in row.cells:
                chunks.append(cell.text)
    return "\n".join(chunks)


def test_single_run_replacement(simple_docx: Path, tmp_path: Path) -> None:
    doc = docx_io.load(simple_docx)
    needle = "ACME S.p.A."
    start = doc.flat_text.find(needle)
    rep = Replacement(
        detection=Detection("ORG", start, start + len(needle), needle, 1.0),
        placeholder="[ORG_1]",
    )
    replacer.apply(doc, [rep])
    out = tmp_path / "out.docx"
    docx_io.save(doc, out)
    text = _read_text(out)
    assert "[ORG_1]" in text
    assert "ACME" not in text


def test_multi_run_replacement(simple_docx: Path, tmp_path: Path) -> None:
    """In the fixture, "Giulia Rossi" lives in its own bold run (one run),
    but the surrounding "Contact <bold>Giulia Rossi</bold> at …" produces a
    multi-run paragraph. Replace a span that bridges the bold run plus the
    leading space to exercise the multi-run path.
    """
    doc = docx_io.load(simple_docx)
    needle = "Contact Giulia Rossi"
    start = doc.flat_text.find(needle)
    assert start >= 0
    rep = Replacement(
        detection=Detection("PERSON", start, start + len(needle), needle, 1.0),
        placeholder="[PERSON_1]",
    )
    replacer.apply(doc, [rep])
    out = tmp_path / "out.docx"
    docx_io.save(doc, out)
    text = _read_text(out)
    assert "[PERSON_1]" in text
    assert "Giulia Rossi" not in text
    assert "Contact " not in text  # the prefix was inside the matched span


def test_multiple_replacements_apply_in_reverse(simple_docx: Path, tmp_path: Path) -> None:
    doc = docx_io.load(simple_docx)
    needles = ["ACME S.p.A.", "Giulia Rossi", "giulia@example.com"]
    reps = []
    for i, n in enumerate(needles, start=1):
        s = doc.flat_text.find(n)
        reps.append(
            Replacement(
                detection=Detection("X", s, s + len(n), n, 1.0),
                placeholder=f"[X_{i}]",
            )
        )
    replacer.apply(doc, reps)
    out = tmp_path / "out.docx"
    docx_io.save(doc, out)
    text = _read_text(out)
    for n in needles:
        assert n not in text
    for i in range(1, 4):
        assert f"[X_{i}]" in text


def test_replacer_does_not_alter_xml_outside_w_t(simple_docx: Path, tmp_path: Path) -> None:
    """Property check: every non-<w:t> element survives untouched."""
    import zipfile

    from lxml import etree

    doc = docx_io.load(simple_docx)
    needle = "Giulia Rossi"
    s = doc.flat_text.find(needle)
    replacer.apply(
        doc,
        [Replacement(Detection("PERSON", s, s + len(needle), needle, 1.0), "[PERSON_1]")],
    )
    out = tmp_path / "out.docx"
    docx_io.save(doc, out)

    def _structure(zip_path: Path) -> list[str]:
        sig: list[str] = []
        with zipfile.ZipFile(zip_path) as zf:
            for member in sorted(zf.namelist()):
                if not member.endswith(".xml"):
                    sig.append(f"{member}:bin")
                    continue
                root = etree.fromstring(zf.read(member))
                # tag path of every element except w:t
                for el in root.iter():
                    if el.tag.endswith("}t"):
                        continue
                    sig.append(f"{member}:{el.tag}")
        return sig

    assert _structure(simple_docx) == _structure(out)
