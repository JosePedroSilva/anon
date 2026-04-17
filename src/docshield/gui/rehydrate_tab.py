"""Rehydrate tab (FR-5.4): paste LLM output + choose mapping + password → restored text."""

from __future__ import annotations

from pathlib import Path

from PySide6.QtGui import QGuiApplication
from PySide6.QtWidgets import (
    QFileDialog,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from ..core import mapping_store
from ..core.mapping_store import MappingStoreError
from ..core.rehydrate import rehydrate


class RehydrateTab(QWidget):
    def __init__(self, parent: QWidget | None = None):
        super().__init__(parent)
        layout = QVBoxLayout(self)

        # Mapping file chooser
        row = QHBoxLayout()
        row.addWidget(QLabel("Mapping file:"))
        self._mapping_path = QLineEdit()
        self._mapping_path.setPlaceholderText("Select a .dsm mapping file…")
        row.addWidget(self._mapping_path, 1)
        browse = QPushButton("Browse…")
        browse.clicked.connect(self._browse)
        row.addWidget(browse)
        layout.addLayout(row)

        # Password
        pw_row = QHBoxLayout()
        pw_row.addWidget(QLabel("Password:"))
        self._password = QLineEdit()
        self._password.setEchoMode(QLineEdit.EchoMode.Password)
        pw_row.addWidget(self._password, 1)
        layout.addLayout(pw_row)

        layout.addWidget(QLabel("LLM response (paste below):"))
        self._input = QTextEdit()
        self._input.setPlaceholderText("Paste the redacted text the LLM returned…")
        layout.addWidget(self._input, 1)

        btn_row = QHBoxLayout()
        self._run = QPushButton("Rehydrate")
        self._run.clicked.connect(self._do_rehydrate)
        btn_row.addWidget(self._run)
        copy_btn = QPushButton("Copy result")
        copy_btn.clicked.connect(self._copy_output)
        btn_row.addWidget(copy_btn)
        btn_row.addStretch(1)
        layout.addLayout(btn_row)

        layout.addWidget(QLabel("Restored text:"))
        self._output = QTextEdit()
        self._output.setReadOnly(True)
        layout.addWidget(self._output, 1)

    def _browse(self) -> None:
        path, _ = QFileDialog.getOpenFileName(
            self, "Choose mapping file", "", "DocShield mapping (*.dsm);;All files (*)"
        )
        if path:
            self._mapping_path.setText(path)

    def _do_rehydrate(self) -> None:
        mapping_file = self._mapping_path.text().strip()
        if not mapping_file or not Path(mapping_file).is_file():
            QMessageBox.warning(self, "Missing mapping", "Please choose a .dsm mapping file first.")
            return
        password = self._password.text()
        if not password:
            QMessageBox.warning(self, "Missing password", "Please enter the mapping password.")
            return
        try:
            mapping = mapping_store.load(mapping_file, password=password)
        except MappingStoreError as exc:
            QMessageBox.critical(self, "Cannot open mapping", str(exc))
            return
        text = self._input.toPlainText()
        self._output.setPlainText(rehydrate(text, mapping))

    def _copy_output(self) -> None:
        QGuiApplication.clipboard().setText(self._output.toPlainText())
