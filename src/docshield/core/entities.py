"""Shared entity types used between detector, allocator, and replacer."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class Detection:
    """A detector hit, expressed in *flat-text* coordinates.

    ``start`` and ``end`` index into ``Document.flat_text``. ``text`` is the
    surface form (cached so the allocator and preview don't have to slice
    the document again). ``score`` is detector confidence in [0, 1].
    """

    entity_type: str
    start: int
    end: int
    text: str
    score: float


@dataclass
class Replacement:
    """An approved swap: replace ``detection.text`` with ``placeholder``."""

    detection: Detection
    placeholder: str
