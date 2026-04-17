"""DOCX I/O.

Loads a `.docx` (a ZIP of XML parts) and exposes every text-bearing ``<w:t>``
element across body, tables, headers, footers, and footnotes as an ordered
list of ``Run`` objects. The flat concatenation of run text is what the
detector sees; each run keeps a reference to its XML node so we can write
replacements back without touching surrounding style or structure.

We deliberately avoid ``python-docx``'s high-level API for traversal because
it skips headers/footers/footnotes by default and hides direct XML access we
need for FR-3.6 (only ``<w:t>`` may be modified).
"""

from __future__ import annotations

import shutil
import tempfile
import zipfile
from dataclasses import dataclass, field
from pathlib import Path
from typing import Iterator

from lxml import etree

W_NS = "http://schemas.openxmlformats.org/wordprocessingml/2006/main"
W = f"{{{W_NS}}}"
NSMAP = {"w": W_NS}

# Parts inside the .docx ZIP whose <w:t> nodes we treat as document text.
TEXT_PARTS = (
    "word/document.xml",
    "word/footnotes.xml",
    "word/endnotes.xml",
)
# Header/footer parts are numbered (header1.xml, footer2.xml, …); we discover
# them dynamically from the zip listing.


@dataclass
class Run:
    """A single ``<w:t>`` text node, plus where it lives.

    ``part`` is the zip member (e.g. ``word/document.xml``) and ``element``
    is the lxml node so the writer can mutate ``element.text`` in place.
    ``block_id`` identifies the enclosing paragraph / table cell so the
    flat-text builder knows where to insert separators.
    """

    part: str
    element: etree._Element
    text: str
    block_id: int = 0

    def set_text(self, value: str) -> None:
        # Preserve significant whitespace if the run carries any.
        if value != value.strip() or value == "":
            self.element.set(
                "{http://www.w3.org/XML/1998/namespace}space", "preserve"
            )
        self.element.text = value
        self.text = value


@dataclass
class RunSpan:
    """A slice of the flat document text mapped back to a single run."""

    run_index: int
    start: int  # inclusive offset in flat text
    end: int  # exclusive
    run_offset: int  # offset within the run where this slice begins


@dataclass
class Document:
    """An opened .docx with parsed XML parts and an ordered run list.

    ``flat_text`` is the concatenation of every run's text in document order.
    ``spans`` lets you map any flat-text offset back to the originating run.
    """

    source_path: Path
    parts: dict[str, etree._Element] = field(default_factory=dict)
    other_files: dict[str, bytes] = field(default_factory=dict)
    runs: list[Run] = field(default_factory=list)
    flat_text: str = ""
    spans: list[RunSpan] = field(default_factory=list)

    def rebuild_flat_text(self) -> None:
        """Concatenate run text into a single string, inserting "\\n"
        between runs whose ``block_id`` differs (paragraph or cell
        boundaries) so the NER tokeniser sees coherent sentences. The
        synthetic separator is part of ``flat_text`` for the detector but
        is *not* covered by any ``RunSpan`` — we only ever write back into
        real runs.
        """
        parts: list[str] = []
        spans: list[RunSpan] = []
        cursor = 0
        prev_block: int | None = None
        for i, run in enumerate(self.runs):
            if prev_block is not None and run.block_id != prev_block:
                parts.append("\n")
                cursor += 1
            text = run.text or ""
            spans.append(RunSpan(run_index=i, start=cursor, end=cursor + len(text), run_offset=0))
            parts.append(text)
            cursor += len(text)
            prev_block = run.block_id
        self.flat_text = "".join(parts)
        self.spans = spans

    def runs_for_range(self, start: int, end: int) -> list[tuple[Run, int, int]]:
        """Return ``(run, run_local_start, run_local_end)`` slices that cover
        ``[start, end)`` in flat-text coordinates. Useful when an entity spans
        more than one run.
        """
        out: list[tuple[Run, int, int]] = []
        for span in self.spans:
            if span.end <= start:
                continue
            if span.start >= end:
                break
            local_start = max(0, start - span.start)
            local_end = min(span.end - span.start, end - span.start)
            if local_end > local_start:
                out.append((self.runs[span.run_index], local_start, local_end))
        return out


def _iter_text_elements(root: etree._Element) -> Iterator[etree._Element]:
    """Yield every ``<w:t>`` element in document order."""
    for el in root.iter(f"{W}t"):
        yield el


def _paragraph_address(t_el: etree._Element) -> tuple[int, ...]:
    """A stable identity for the enclosing ``<w:p>`` element.

    lxml proxies return different ``id()`` values for the same underlying
    node across accesses, so we can't use ``id``. Instead, build a tuple
    of child indices from the document root down to the paragraph. That
    tuple uniquely identifies the paragraph and is hashable.
    """
    node = t_el.getparent()
    while node is not None and node.tag != f"{W}p":
        node = node.getparent()
    if node is None:
        return ()
    path: list[int] = []
    cur = node
    parent = cur.getparent()
    while parent is not None:
        path.append(parent.index(cur))
        cur = parent
        parent = cur.getparent()
    return tuple(reversed(path))


def load(path: str | Path) -> Document:
    """Open a `.docx`, parse text-bearing parts, and build the run table."""
    src = Path(path)
    if not src.is_file():
        raise FileNotFoundError(src)
    doc = Document(source_path=src)

    with zipfile.ZipFile(src, "r") as zf:
        names = set(zf.namelist())
        text_parts = [n for n in TEXT_PARTS if n in names]
        # discover header*.xml and footer*.xml dynamically
        text_parts += sorted(
            n for n in names
            if (n.startswith("word/header") or n.startswith("word/footer")) and n.endswith(".xml")
        )
        for name in names:
            data = zf.read(name)
            if name in text_parts:
                # parse and remember as element tree
                doc.parts[name] = etree.fromstring(data)
            else:
                doc.other_files[name] = data

    # Build the ordered run list. Document order = order parts appear in
    # ``text_parts`` above (body first, then footnotes/endnotes, then headers
    # and footers). This is the order DocShield will present to the detector;
    # it is *not* the visual reading order, but per-part order is preserved
    # which is what matters for entity-locality.
    block_ids: dict[tuple[str, tuple[int, ...]], int] = {}
    for part_name, root in doc.parts.items():
        for t_el in _iter_text_elements(root):
            text = t_el.text or ""
            key = (part_name, _paragraph_address(t_el))
            block_id = block_ids.setdefault(key, len(block_ids) + 1)
            doc.runs.append(
                Run(part=part_name, element=t_el, text=text, block_id=block_id)
            )

    doc.rebuild_flat_text()
    return doc


def save(doc: Document, dest: str | Path) -> Path:
    """Write the document back to ``dest`` atomically.

    Atomic = write to a sibling temp file, then rename. If anything blows up
    mid-write we don't leave a corrupt half-file at the target path
    (NFR-4.2).
    """
    out = Path(dest)
    out.parent.mkdir(parents=True, exist_ok=True)

    # Rebuild the source ZIP, swapping in our (possibly mutated) parsed parts.
    fd, tmp_name = tempfile.mkstemp(prefix=".docshield_", suffix=".docx", dir=out.parent)
    try:
        with zipfile.ZipFile(tmp_name, "w", zipfile.ZIP_DEFLATED) as zf:
            # Preserve original member ordering by re-reading the source zip.
            with zipfile.ZipFile(doc.source_path, "r") as src_zf:
                for info in src_zf.infolist():
                    if info.filename in doc.parts:
                        payload = etree.tostring(
                            doc.parts[info.filename],
                            xml_declaration=True,
                            encoding="UTF-8",
                            standalone=True,
                        )
                    else:
                        payload = doc.other_files.get(info.filename, src_zf.read(info.filename))
                    zf.writestr(info, payload)
        # close fd from mkstemp; we wrote via zipfile path API
        import os as _os

        _os.close(fd)
        Path(tmp_name).replace(out)
    except Exception:
        Path(tmp_name).unlink(missing_ok=True)
        raise
    return out
