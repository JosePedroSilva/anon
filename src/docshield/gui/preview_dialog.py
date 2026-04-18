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

from PySide6.QtCore import Qt, QTimer
from PySide6.QtGui import QColor, QTextCharFormat, QTextCursor
from PySide6.QtWidgets import QTextEdit as _QTextEdit  # for ExtraSelection type
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
from ..core.placeholder import canonicalise


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

        # Header counts: show both unique-entity and total-mention counts
        # so the user understands the dedupe.
        unique_count = len({(d.entity_type, canonicalise(d.entity_type, d.text)) for d in detections})
        layout = QVBoxLayout(self)
        layout.addWidget(
            QLabel(
                f"{unique_count} unique entities ({len(detections)} mentions). "
                "Untick anything you want to keep as-is — one untick removes all mentions.",
            )
        )

        splitter = QSplitter(Qt.Orientation.Horizontal, self)
        layout.addWidget(splitter, 1)

        # Left: grouped tree of detections.
        self._tree = QTreeWidget()
        self._tree.setHeaderLabels(["Surface", "Type", "Score"])
        self._tree.setColumnWidth(0, 320)
        # Populate before connecting itemChanged so we don't fire the
        # checkbox-change handler thousands of times during build.
        self._populate_tree(detections)
        self._tree.itemChanged.connect(self._on_item_changed)
        splitter.addWidget(self._tree)

        # Right: before/after text with the selected detections highlighted.
        right = QWidget()
        right_layout = QVBoxLayout(right)
        right_layout.setContentsMargins(0, 0, 0, 0)
        right_layout.addWidget(QLabel("Preview (approved redactions highlighted):"))
        self._preview = QTextEdit()
        self._preview.setReadOnly(True)
        # Cache the full text once. ExtraSelections paint on top of the
        # existing document so we don't re-render text on every toggle.
        self._preview.setPlainText(self._flat_text)
        right_layout.addWidget(self._preview, 1)

        # Pre-build the highlight format once.
        self._hl_format = QTextCharFormat()
        self._hl_format.setBackground(QColor("#fbbf24"))
        self._hl_format.setForeground(QColor("#1f2937"))
        self._hl_format.setFontUnderline(True)
        self._hl_format.setUnderlineColor(QColor("#92400e"))

        # Debounce: ticking a group fires itemChanged for every child.
        # Coalesce the burst into one refresh.
        self._refresh_timer = QTimer(self)
        self._refresh_timer.setSingleShot(True)
        self._refresh_timer.setInterval(40)
        self._refresh_timer.timeout.connect(self._refresh_preview)

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
        # Group: type → canonical key → list of detections (mentions).
        # The canonical key is the same one the placeholder allocator
        # uses, so the tree view matches the eventual placeholder map.
        by_type: dict[str, dict[str, list[Detection]]] = {}
        for d in detections:
            key = canonicalise(d.entity_type, d.text)
            by_type.setdefault(d.entity_type, {}).setdefault(key, []).append(d)

        for entity_type in sorted(by_type):
            buckets = by_type[entity_type]
            unique_n = len(buckets)
            mention_n = sum(len(v) for v in buckets.values())
            group = QTreeWidgetItem(
                [f"{entity_type} ({unique_n} unique / {mention_n} mentions)"]
            )
            group.setFlags(
                group.flags() | Qt.ItemFlag.ItemIsUserCheckable | Qt.ItemFlag.ItemIsAutoTristate
            )
            group.setCheckState(0, Qt.CheckState.Checked)
            self._tree.addTopLevelItem(group)

            # Show buckets ordered by mention count (most frequent first)
            # so the user spots high-impact false positives quickly.
            ordered_buckets = sorted(
                buckets.items(),
                key=lambda kv: (-len(kv[1]), kv[1][0].text.lower()),
            )
            for _key, mentions in ordered_buckets:
                surface = mentions[0].text  # first-seen form
                count_label = f"{surface}  ({len(mentions)})" if len(mentions) > 1 else surface
                avg_score = sum(m.score for m in mentions) / len(mentions)
                child = QTreeWidgetItem([count_label, entity_type, f"{avg_score:.2f}"])
                child.setFlags(child.flags() | Qt.ItemFlag.ItemIsUserCheckable)
                child.setCheckState(0, Qt.CheckState.Checked)
                # Store the *list* of underlying detections — un/ticking
                # this leaf affects all of them.
                child.setData(0, Qt.ItemDataRole.UserRole, mentions)
                group.addChild(child)
            group.setExpanded(True)

    def _iter_leaves(self):
        for i in range(self._tree.topLevelItemCount()):
            group = self._tree.topLevelItem(i)
            for j in range(group.childCount()):
                yield group.child(j)

    def _set_all(self, state: Qt.CheckState) -> None:
        # Block tree signals so we don't fire (and debounce) for every
        # leaf when bulk-toggling — one refresh at the end is enough.
        self._tree.blockSignals(True)
        try:
            for leaf in self._iter_leaves():
                leaf.setCheckState(0, state)
        finally:
            self._tree.blockSignals(False)
        self._refresh_timer.start()

    def _select_all(self) -> None:
        self._set_all(Qt.CheckState.Checked)

    def _clear_all(self) -> None:
        self._set_all(Qt.CheckState.Unchecked)

    def _on_item_changed(self, *_args: object) -> None:
        # Coalesce — the QTreeWidget fires this once per affected child
        # when a parent group is (un)ticked.
        self._refresh_timer.start()

    # ----- preview rendering -----

    def _approved_detections(self) -> list[Detection]:
        out: list[Detection] = []
        for leaf in self._iter_leaves():
            if leaf.checkState(0) != Qt.CheckState.Checked:
                continue
            payload = leaf.data(0, Qt.ItemDataRole.UserRole)
            # Each leaf now stores the full list of mentions for one
            # canonical entity (FIA, FIA Riservato, etc.), so unticking
            # one row removes every mention from the output.
            if isinstance(payload, list):
                out.extend(p for p in payload if isinstance(p, Detection))
            elif isinstance(payload, Detection):
                out.append(payload)
        out.sort(key=lambda d: d.start)
        return out

    def _refresh_preview(self) -> None:
        # ExtraSelections paint highlights as an overlay — far cheaper
        # than mergeCharFormat per detection (which dirties the document
        # and triggers a relayout each time). With 1000+ detections,
        # mergeCharFormat blocked the GUI for seconds; this stays
        # snappy.
        doc = self._preview.document()
        selections: list[_QTextEdit.ExtraSelection] = []
        for det in self._approved_detections():
            sel = _QTextEdit.ExtraSelection()
            sel.format = self._hl_format
            cursor = QTextCursor(doc)
            cursor.setPosition(det.start)
            cursor.setPosition(det.end, QTextCursor.MoveMode.KeepAnchor)
            sel.cursor = cursor
            selections.append(sel)
        self._preview.setExtraSelections(selections)

    # ----- public result -----

    def result_payload(self) -> PreviewResult:
        extras_raw = self._extra_input.text().strip()
        extras = [t.strip() for t in re.split(r"[,\n]", extras_raw) if t.strip()]
        return PreviewResult(approved=self._approved_detections(), extra_terms=extras)
