"""Apply approved replacements to a Document's runs (FR-3.5, FR-3.6).

Replacements are expressed in flat-text coordinates. Because a single
detection can straddle two or more ``<w:t>`` runs (a name split across
``<w:r>`` boundaries due to formatting), we walk the affected runs and:

* fully replace the placeholder text into the *first* covered run,
* clear the slice in any subsequent covered run (so we don't leave
  duplicated suffixes behind).

This intentionally does not merge runs or alter their style attributes —
the run keeps its bold/italic/font setting; only the text content of one
``<w:t>`` node changes.
"""

from __future__ import annotations

from .docx_io import Document
from .entities import Replacement


def apply(doc: Document, replacements: list[Replacement]) -> None:
    """Apply ``replacements`` in reverse offset order so earlier offsets
    stay valid as we mutate the run text.
    """
    if not replacements:
        return
    # Sort by start offset descending. Two detections that overlap would be
    # ambiguous; we drop the lower-confidence one (caller's responsibility
    # to filter; we just guard against straight-up duplicates here).
    seen: set[tuple[int, int]] = set()
    ordered = []
    for r in sorted(replacements, key=lambda x: x.detection.start, reverse=True):
        key = (r.detection.start, r.detection.end)
        if key in seen:
            continue
        seen.add(key)
        ordered.append(r)

    for rep in ordered:
        _apply_one(doc, rep)
    doc.rebuild_flat_text()


def _apply_one(doc: Document, rep: Replacement) -> None:
    spans = doc.runs_for_range(rep.detection.start, rep.detection.end)
    if not spans:
        return
    first_run, first_local_start, first_local_end = spans[0]
    placeholder = rep.placeholder

    if len(spans) == 1:
        # Single-run case: splice placeholder into the run text.
        new = first_run.text[:first_local_start] + placeholder + first_run.text[first_local_end:]
        first_run.set_text(new)
        return

    # Multi-run case: write placeholder + suffix-of-first into first run,
    # then strip the matched slice out of every subsequent run.
    first_new = first_run.text[:first_local_start] + placeholder
    # Tail belongs to the *last* run (whatever sits after the entity ends).
    last_run, _, last_local_end = spans[-1]
    tail = last_run.text[last_local_end:]

    # First run: prefix + placeholder
    first_run.set_text(first_new)
    # Middle runs: clear them entirely
    for mid_run, _, _ in spans[1:-1]:
        mid_run.set_text("")
    # Last run: tail only (drops the matched portion + any prefix that
    # belonged to the entity).
    if first_run is not last_run:
        last_run.set_text(tail)
