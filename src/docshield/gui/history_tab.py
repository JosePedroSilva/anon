"""History tab (FR-6.3): read the JSON-lines audit log."""

from __future__ import annotations

import json
from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from ..config import audit_log_path


class HistoryTab(QWidget):
    def __init__(self, parent: QWidget | None = None):
        super().__init__(parent)
        layout = QVBoxLayout(self)

        header = QHBoxLayout()
        header.addWidget(QLabel("Anonymisation history"))
        header.addStretch(1)
        refresh = QPushButton("Refresh")
        refresh.clicked.connect(self.reload)
        header.addWidget(refresh)
        layout.addLayout(header)

        self._table = QTableWidget(0, 5)
        self._table.setHorizontalHeaderLabels(["When", "Source", "Entities", "Output", "Mapping"])
        self._table.horizontalHeader().setSectionResizeMode(
            QHeaderView.ResizeMode.ResizeToContents
        )
        self._table.horizontalHeader().setStretchLastSection(True)
        self._table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self._table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        layout.addWidget(self._table, 1)

        self.reload()

    def reload(self) -> None:
        self._table.setRowCount(0)
        path = audit_log_path()
        if not Path(path).is_file():
            return
        with open(path, encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    entry = json.loads(line)
                except json.JSONDecodeError:
                    continue
                row = self._table.rowCount()
                self._table.insertRow(row)
                totals = sum(entry.get("entities", {}).values())
                breakdown = ", ".join(
                    f"{k}:{v}" for k, v in sorted(entry.get("entities", {}).items())
                )
                values = [
                    entry.get("ts", ""),
                    entry.get("file", ""),
                    f"{totals} ({breakdown})" if breakdown else str(totals),
                    entry.get("output", ""),
                    entry.get("mapping", ""),
                ]
                for col, val in enumerate(values):
                    item = QTableWidgetItem(val)
                    item.setTextAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)
                    self._table.setItem(row, col, item)
