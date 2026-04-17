"""Preview dialog (FR-4.1 … FR-4.4).

Shows every detection with a checkbox so the user can opt out of false
positives, grouped by entity type. A free-text field lets them add
custom denylist-style terms that weren't caught.

Returning the approved list happens through ``approved()``; the caller
reads it after ``exec()`` returns ``QDialog.Accepted``.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

from PySide6.QtCore import Qt
from PySide6.QtGui import QTextCharFormat, QTextCursor
from PySide6.QtWidgets import (
    QDialog,
    QDialogButtonBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QSplitter,
    QTextEdit,
    QTreeWidget,
    QTreeWidgetItem,
    QVBoxLayout,
    QWidget,
)

from ..core.entities import Detection


@dataclass
class PreviewResult:
    approved: list[Detection]
    extra_terms: list[str]  # things the user typed in as "also redact this"


class PreviewDialog(QDialog):
    def __init__(self, flat_text: str, detections: list[Detection], parent: QWidget | None = None):
        super().__init__(parent)
        self.setWindowTitle("Review detections")
        self.resize(1000, 650)
        self._flat_text = flat_text
        self._detections = detections

        layout = QVBoxLayout(self)
        layout.addWidget(
            QLabel(
                f"{len(detections)} entities detected. Untick anything you want to keep as-is.",
            )
        )

        splitter = QSplitter(Qt.Orientation.Horizontal, self)
        layout.addWidget(splitter, 1)

        # Left: grouped tree of detections.
        self._tree = QTreeWidget()
        self._tree.setHeaderLabels(["Surface", "Type", "Score"])
        self._tree.setColumnWidth(0, 320)
        self._tree.itemChanged.connect(self._on_item_changed)
        self._populate_tree(detections)
        splitter.addWidget(self._tree)

        # Right: before/after text with the selected detections highlighted.
        right = QWidget()
        right_layout = QVBoxLayout(right)
        right_layout.setContentsMargins(0, 0, 0, 0)
        right_layout.addWidget(QLabel("Preview (approved redactions highlighted):"))
        self._preview = QTextEdit()
        self._preview.setReadOnly(True)
        right_layout.addWidget(self._preview, 1)

        add_row = QHBoxLayout()
        add_row.addWidget(QLabel("Also redact (comma-separated):"))
        self._extra_input = QLineEdit()
        self._extra_input.setPlaceholderText("e.g. Project Falcon, Client-42")
        add_row.addWidget(self._extra_input, 1)
        right_layout.addLayout(add_row)

        splitter.addWidget(right)
        splitter.setSizes([400, 600])

        # Buttons: Anonymise / Cancel / (de)select all
        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        ok_button = buttons.button(QDialogButtonBox.StandardButton.Ok)
        ok_button.setText("Anonymise")
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)

        sel_row = QHBoxLayout()
        for label, fn in (("Select all", self._select_all), ("Clear all", self._clear_all)):
            b = QPushButton(label)
            b.clicked.connect(fn)
            sel_row.addWidget(b)
        sel_row.addStretch(1)
        sel_row.addWidget(buttons)
        layout.addLayout(sel_row)

        self._refresh_preview()

    # ----- tree population & checkbox logic -----

    def _populate_tree(self, detections: list[Detection]) -> None:
        by_type: dict[str, list[Detection]] = {}
        for d in detections:
            by_type.setdefault(d.entity_type, []).append(d)

        for entity_type in sorted(by_type):
            group = QTreeWidgetItem([f"{entity_type} ({len(by_type[entity_type])})"])
            group.setFlags(group.flags() | Qt.ItemFlag.ItemIsUserCheckable | Qt.ItemFlag.ItemIsAutoTristate)
            group.setCheckState(0, Qt.CheckState.Checked)
            self._tree.addTopLevelItem(group)
            for det in by_type[entity_type]:
                child = QTreeWidgetItem([det.text, det.entity_type, f"{det.score:.2f}"])
                child.setFlags(child.flags() | Qt.ItemFlag.ItemIsUserCheckable)
                child.setCheckState(0, Qt.CheckState.Checked)
                child.setData(0, Qt.ItemDataRole.UserRole, det)
                group.addChild(child)
            group.setExpanded(True)

    def _iter_leaves(self):
        for i in range(self._tree.topLevelItemCount()):
            group = self._tree.topLevelItem(i)
            for j in range(group.childCount()):
                yield group.child(j)

    def _select_all(self) -> None:
        for leaf in self._iter_leaves():
            leaf.setCheckState(0, Qt.CheckState.Checked)

    def _clear_all(self) -> None:
        for leaf in self._iter_leaves():
            leaf.setCheckState(0, Qt.CheckState.Unchecked)

    def _on_item_changed(self, *_args: object) -> None:
        self._refresh_preview()

    # ----- preview rendering -----

    def _approved_detections(self) -> list[Detection]:
        out: list[Detection] = []
        for leaf in self._iter_leaves():
            if leaf.checkState(0) == Qt.CheckState.Checked:
                det = leaf.data(0, Qt.ItemDataRole.UserRole)
                if isinstance(det, Detection):
                    out.append(det)
        out.sort(key=lambda d: d.start)
        return out

    def _refresh_preview(self) -> None:
        self._preview.clear()
        self._preview.setPlainText(self._flat_text)
        fmt = QTextCharFormat()
        fmt.setBackground(Qt.GlobalColor.yellow)
        cursor = self._preview.textCursor()
        for det in self._approved_detections():
            cursor.setPosition(det.start)
            cursor.setPosition(det.end, QTextCursor.MoveMode.KeepAnchor)
            cursor.mergeCharFormat(fmt)

    # ----- public result -----

    def result_payload(self) -> PreviewResult:
        extras_raw = self._extra_input.text().strip()
        extras = [t.strip() for t in re.split(r"[,\n]", extras_raw) if t.strip()]
        return PreviewResult(approved=self._approved_detections(), extra_terms=extras)
