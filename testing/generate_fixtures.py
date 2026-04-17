"""Generate realistic sample .docx files for manual GUI testing.

Run: ``.venv/bin/python testing/generate_fixtures.py``

Each fixture exercises a different aspect of the pipeline. Suggested
manual test order is encoded in the filenames (``01_…`` first, etc.).
"""

from __future__ import annotations

from pathlib import Path

from docx import Document
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.shared import Pt

OUT = Path(__file__).parent


def _title(doc: Document, text: str) -> None:
    p = doc.add_paragraph()
    p.alignment = WD_ALIGN_PARAGRAPH.CENTER
    r = p.add_run(text)
    r.bold = True
    r.font.size = Pt(16)


def simple_english() -> None:
    """01 — straightforward EN contract. Good first smoke test."""
    d = Document()
    _title(d, "Non-Disclosure Agreement")
    d.add_paragraph(
        "This Non-Disclosure Agreement is entered into on the 15th of January, 2026, "
        "between Giulia Rossi (giulia.rossi@example.com, +39 02 1234 5678) and "
        "ACME Industries, Inc. (hereinafter 'ACME')."
    )
    d.add_paragraph(
        "The parties acknowledge that Mr. John Carter, counsel for ACME, may be contacted "
        "at john.carter@acme-law.com for any clarification."
    )
    d.add_paragraph(
        "Any disputes shall be resolved by the Superior Court of New York County."
    )
    d.save(OUT / "01_simple_english.docx")


def italian_contract() -> None:
    """02 — Italian doc with codice fiscale + IT IBAN."""
    d = Document()
    _title(d, "Contratto di Collaborazione")
    d.add_paragraph(
        "Il presente contratto è stipulato tra il sig. Mario Bianchi, residente a Milano, "
        "codice fiscale BNCMRA80A01F205X, e la società Globex S.r.l., con sede legale "
        "in Roma."
    )
    d.add_paragraph(
        "Pagamenti da effettuarsi sull'IBAN IT60X0542811101000000123456 intestato a "
        "Mario Bianchi. Recapiti: mario.bianchi@studio.it, +39 06 9876 5432."
    )
    d.add_paragraph("Procedimento di riferimento: R.G. 4567/2024.")
    d.save(OUT / "02_italian_contract.docx")


def formatted_runs() -> None:
    """03 — bold/italic split a name across multiple <w:r> runs.

    Exercises the multi-run replacement path in ``replacer.py``.
    """
    d = Document()
    d.add_paragraph("Signed on behalf of the client by:")
    p = d.add_paragraph()
    p.add_run("Counsel: ")
    p.add_run("Dr. Julia ").bold = True  # run 1
    p.add_run("Rossi").bold = True  # run 2 (same name, split across formatting runs)
    p.add_run(", Esq.")
    d.add_paragraph(
        "Please forward all correspondence to julia.rossi@firm-example.com."
    )
    d.save(OUT / "03_formatted_runs.docx")


def with_table() -> None:
    """04 — table of parties with emails + IBANs."""
    d = Document()
    _title(d, "Schedule A — Parties")
    d.add_paragraph("The following parties are bound by this agreement:")
    table = d.add_table(rows=4, cols=3)
    table.style = "Light Grid"
    hdr = table.rows[0].cells
    hdr[0].text = "Name"
    hdr[1].text = "Email"
    hdr[2].text = "IBAN"
    rows = [
        ("Giulia Rossi", "giulia.rossi@example.com", "IT60X0542811101000000123456"),
        ("Mario Bianchi", "mario@bianchi.it", "IT28W0800000000000000000001"),
        ("John Carter", "john.carter@acme-law.com", "GB29NWBK60161331926819"),
    ]
    for i, (name, email, iban) in enumerate(rows, start=1):
        cells = table.rows[i].cells
        cells[0].text = name
        cells[1].text = email
        cells[2].text = iban
    d.save(OUT / "04_with_table.docx")


def repeated_mentions() -> None:
    """05 — same name variants across paragraphs (FR-3.2, FR-3.3).

    'Giulia Rossi' / 'Ms. Rossi' / 'G. Rossi' should collapse onto the
    same [PERSON_N] placeholder.
    """
    d = Document()
    d.add_paragraph(
        "Counsel Giulia Rossi filed the motion on behalf of the plaintiff."
    )
    d.add_paragraph(
        "Ms. Rossi argued that the evidence was inadmissible under Rule 403."
    )
    d.add_paragraph(
        "The court, unpersuaded, denied G. Rossi's motion in its entirety."
    )
    d.add_paragraph(
        "Separately, Mario Bianchi, called as a witness, confirmed the dates."
    )
    d.save(OUT / "05_repeated_mentions.docx")


def allowlist_candidate() -> None:
    """06 — contains 'Supreme Court' (allowlist candidate) and 'Project Falcon'
    (denylist candidate). Use this to exercise Settings.
    """
    d = Document()
    d.add_paragraph(
        "The case was argued before the Supreme Court of the United States in October."
    )
    d.add_paragraph(
        "Our client, Sarah Johnson, is the lead engineer on Project Falcon, "
        "a confidential initiative at Initech, LLC."
    )
    d.add_paragraph(
        "Please do not share Project Falcon details with anyone outside counsel."
    )
    d.save(OUT / "06_allow_deny_candidates.docx")


def batch_shared_names_a() -> None:
    d = Document()
    _title(d, "Letter — part 1 of 2")
    d.add_paragraph(
        "To whom it may concern: Mr. John Carter represents our client Giulia Rossi "
        "in the matter of ACME Industries vs. Globex S.r.l."
    )
    d.add_paragraph(
        "Please direct correspondence to john.carter@acme-law.com."
    )
    d.save(OUT / "07a_batch_part1.docx")


def batch_shared_names_b() -> None:
    """07a + 07b share names — drop both in the GUI to see the same
    [PERSON_N] reused across files (FR-3.2, batch stability)."""
    d = Document()
    _title(d, "Letter — part 2 of 2")
    d.add_paragraph(
        "Further to our letter of yesterday: Giulia Rossi has authorised settlement "
        "negotiations with ACME Industries."
    )
    d.add_paragraph(
        "Mr. Carter will travel to Milan next week to meet with Mario Bianchi of "
        "Globex S.r.l."
    )
    d.save(OUT / "07b_batch_part2.docx")


def main() -> None:
    simple_english()
    italian_contract()
    formatted_runs()
    with_table()
    repeated_mentions()
    allowlist_candidate()
    batch_shared_names_a()
    batch_shared_names_b()
    print(f"Wrote fixtures to {OUT}")


if __name__ == "__main__":
    main()
