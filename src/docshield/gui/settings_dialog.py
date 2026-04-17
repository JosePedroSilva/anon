"""Settings dialog (FR-7.1)."""

from __future__ import annotations

from PySide6.QtWidgets import (
    QCheckBox,
    QDialog,
    QDialogButtonBox,
    QDoubleSpinBox,
    QFileDialog,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPlainTextEdit,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from ..config import Settings


def _lines(text: str) -> list[str]:
    return [ln.strip() for ln in text.splitlines() if ln.strip()]


class SettingsDialog(QDialog):
    def __init__(self, settings: Settings, parent: QWidget | None = None):
        super().__init__(parent)
        self.setWindowTitle("Settings")
        self.resize(560, 620)
        self._settings = settings

        layout = QVBoxLayout(self)
        form = QFormLayout()
        layout.addLayout(form)

        self._threshold = QDoubleSpinBox()
        self._threshold.setRange(0.0, 1.0)
        self._threshold.setSingleStep(0.05)
        self._threshold.setDecimals(2)
        self._threshold.setValue(settings.confidence_threshold)
        form.addRow("Confidence threshold:", self._threshold)

        self._detect_dates = QCheckBox("Also redact dates (may over-redact)")
        self._detect_dates.setChecked(settings.detect_dates)
        form.addRow("", self._detect_dates)

        self._detect_money = QCheckBox("Also redact monetary amounts")
        self._detect_money.setChecked(settings.detect_money)
        form.addRow("", self._detect_money)

        out_row = QHBoxLayout()
        self._output_dir = QLineEdit(settings.default_output_dir or "")
        out_row.addWidget(self._output_dir, 1)
        browse = QPushButton("Browse…")
        browse.clicked.connect(self._pick_dir)
        out_row.addWidget(browse)
        form.addRow("Default output folder:", out_row)

        self._allow = QPlainTextEdit("\n".join(settings.allowlist))
        self._allow.setPlaceholderText("One term per line (e.g. Supreme Court)")
        form.addRow("Allowlist (never redact):", self._allow)

        self._deny = QPlainTextEdit("\n".join(settings.denylist))
        self._deny.setPlaceholderText("One term per line (e.g. Client-42)")
        form.addRow("Denylist (always redact):", self._deny)

        layout.addWidget(QLabel("Changes take effect on the next anonymisation."))

        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Save | QDialogButtonBox.StandardButton.Cancel
        )
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    def _pick_dir(self) -> None:
        path = QFileDialog.getExistingDirectory(self, "Choose default output folder")
        if path:
            self._output_dir.setText(path)

    def updated_settings(self) -> Settings:
        s = self._settings
        s.confidence_threshold = float(self._threshold.value())
        s.detect_dates = self._detect_dates.isChecked()
        s.detect_money = self._detect_money.isChecked()
        s.default_output_dir = self._output_dir.text().strip() or None
        s.allowlist = _lines(self._allow.toPlainText())
        s.denylist = _lines(self._deny.toPlainText())
        return s
