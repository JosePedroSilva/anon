"""GUI widget smoke tests. Offscreen Qt, no user interaction.

We don't drive the anonymise workflow here — that requires the spaCy
models and a real thread loop, which the integration tests already cover
headlessly. These tests just confirm the dialogs instantiate, accept
input, and return the right payloads.
"""

from __future__ import annotations

import os

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

pytest.importorskip("PySide6")

from PySide6.QtCore import Qt  # noqa: E402
from PySide6.QtWidgets import QApplication  # noqa: E402

from docshield.core.entities import Detection  # noqa: E402
from docshield.core.mapping_store import MappingFile, save as save_mapping  # noqa: E402
from docshield.gui.preview_dialog import PreviewDialog  # noqa: E402
from docshield.gui.rehydrate_tab import RehydrateTab  # noqa: E402


@pytest.fixture(scope="module")
def qapp():
    app = QApplication.instance() or QApplication([])
    yield app


def test_preview_dialog_returns_checked_subset(qapp) -> None:
    text = "Contact Giulia Rossi at giulia@example.com."
    detections = [
        Detection("PERSON", 8, 20, "Giulia Rossi", 0.9),
        Detection("EMAIL", 24, 42, "giulia@example.com", 1.0),
    ]
    dlg = PreviewDialog(text, detections)
    # Uncheck the EMAIL detection (second leaf under its group)
    tree = dlg._tree
    # Find the EMAIL group and uncheck its first leaf
    for i in range(tree.topLevelItemCount()):
        group = tree.topLevelItem(i)
        if group.text(0).startswith("EMAIL"):
            group.child(0).setCheckState(0, Qt.CheckState.Unchecked)
    dlg._extra_input.setText("Project Falcon, Client-42")

    payload = dlg.result_payload()
    kept = {d.entity_type for d in payload.approved}
    assert kept == {"PERSON"}
    assert payload.extra_terms == ["Project Falcon", "Client-42"]


def test_preview_dedupes_repeated_mentions(qapp) -> None:
    """Three mentions of "FIA Riservato" should appear as a single leaf
    with a (3) count, and unticking it should drop every underlying
    detection from the approved list.
    """
    text = "FIA Riservato, FIA Riservato, e di nuovo FIA Riservato."
    detections = [
        Detection("ORG", 0, 13, "FIA Riservato", 0.85),
        Detection("ORG", 15, 28, "FIA Riservato", 0.85),
        Detection("ORG", 41, 54, "FIA Riservato", 0.85),
    ]
    dlg = PreviewDialog(text, detections)
    tree = dlg._tree
    org_group = next(
        tree.topLevelItem(i) for i in range(tree.topLevelItemCount())
        if tree.topLevelItem(i).text(0).startswith("ORG")
    )
    assert org_group.childCount() == 1, "duplicates should collapse to one leaf"
    leaf = org_group.child(0)
    assert "(3)" in leaf.text(0)
    # Approved list should hold all 3 mentions.
    assert len(dlg._approved_detections()) == 3
    # Untick the leaf → all three should drop out.
    leaf.setCheckState(0, Qt.CheckState.Unchecked)
    assert dlg._approved_detections() == []


def test_rehydrate_tab_restores_originals(qapp, tmp_path) -> None:
    mapping_path = tmp_path / "m.dsm"
    save_mapping(
        mapping_path,
        MappingFile(
            source_file="x.docx",
            language="en",
            entries=[
                {"placeholder": "[PERSON_1]", "original": "Giulia Rossi", "type": "PERSON"},
                {"placeholder": "[EMAIL_1]", "original": "giulia@example.com", "type": "EMAIL"},
            ],
        ),
        password="pw",
    )
    tab = RehydrateTab()
    tab._mapping_path.setText(str(mapping_path))
    tab._password.setText("pw")
    tab._input.setPlainText("[PERSON_1] ([EMAIL_1]) confirmed.")
    tab._do_rehydrate()
    assert tab._output.toPlainText() == "Giulia Rossi (giulia@example.com) confirmed."
