"""Plain-Python pipeline functions that both the CLI and GUI call.

Keeping all the orchestration here (instead of inside ``cli.py``) means the
GUI worker thread doesn't have to re-implement the flow, and both
frontends stay honest about what's happening under the hood.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from . import detector, docx_io, mapping_store, replacer
from .entities import Detection, Replacement
from .placeholder import PlaceholderAllocator


@dataclass
class AnalysedDocument:
    """Result of the *detect* half of the pipeline; ready for preview."""

    path: Path
    document: docx_io.Document
    language: str
    detections: list[Detection]


def analyse(path: Path, config: detector.DetectorConfig) -> AnalysedDocument:
    doc = docx_io.load(path)
    language, detections = detector.detect(doc.flat_text, config=config)
    return AnalysedDocument(path=path, document=doc, language=language, detections=detections)


def write_output(
    analysed: AnalysedDocument,
    approved: list[Detection],
    allocator: PlaceholderAllocator,
    password: str,
    output_dir: Path | None = None,
) -> tuple[Path, Path, mapping_store.MappingFile]:
    """Apply ``approved`` detections, save anonymised docx + mapping.

    Returns ``(out_doc, out_map, mapping)``. The mapping object is
    returned separately so callers (e.g. history display) don't need to
    decrypt it again.
    """
    replacements: list[Replacement] = []
    for det in approved:
        ph = allocator.allocate(det.entity_type, det.text)
        replacements.append(Replacement(detection=det, placeholder=ph))

    replacer.apply(analysed.document, replacements)

    out_dir = output_dir or analysed.path.parent
    out_doc = out_dir / f"{analysed.path.stem}_anon.docx"
    out_map = out_dir / f"{analysed.path.stem}_mapping.dsm"
    docx_io.save(analysed.document, out_doc)

    mapping = mapping_store.MappingFile(
        source_file=analysed.path.name,
        language=analysed.language,
        entries=[
            {"placeholder": e.placeholder, "original": e.original, "type": e.entity_type}
            for e in allocator.entries()
        ],
    )
    mapping_store.save(out_map, mapping, password=password)
    return out_doc, out_map, mapping
