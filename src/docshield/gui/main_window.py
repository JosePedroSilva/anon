"""Main application window.

Three tabs:

* Anonymise — drop / pick .docx files, run the pipeline, preview, write.
* Rehydrate — restore real names in an LLM response.
* History   — read the audit log.

The Anonymise tab processes a batch with a single shared
``PlaceholderAllocator`` so placeholder numbering stays consistent
across the batch (FR-3.2).
"""

from __future__ import annotations

import getpass
from pathlib import Path

import time

from PySide6.QtCore import QObject, Qt, QThread, QTimer
from PySide6.QtGui import QAction, QDragEnterEvent, QDropEvent
from PySide6.QtWidgets import (
    QDialog,
    QFileDialog,
    QHBoxLayout,
    QLabel,
    QListWidget,
    QMainWindow,
    QMessageBox,
    QPushButton,
    QStatusBar,
    QTabWidget,
    QVBoxLayout,
    QWidget,
)

from ..config import Settings
from ..core import detector
from ..core.input_validation import has_error, validate_docx
from ..core.placeholder import PlaceholderAllocator
from ..logging_setup import write_run
from .history_tab import HistoryTab
from .prewarm import start_prewarm
from .preview_dialog import PreviewDialog
from .rehydrate_tab import RehydrateTab
from .settings_dialog import SettingsDialog
from .worker import AnalyseWorker, WriteWorker, run_in_thread


class DropList(QListWidget):
    """QListWidget that accepts .docx files dropped onto it.

    Silently ignoring unsupported drops makes the UI feel broken, so we
    surface a message via ``rejected`` when the user drops something
    we can't process (FR-1.4).
    """

    from PySide6.QtCore import Signal as _Signal  # local alias to avoid top-level import churn

    rejected = _Signal(list)  # list[tuple[str, str]] of (path, reason)

    def __init__(self, parent: QWidget | None = None):
        super().__init__(parent)
        self.setAcceptDrops(True)

    def dragEnterEvent(self, event: QDragEnterEvent) -> None:  # noqa: N802 Qt API
        if event.mimeData().hasUrls():
            event.acceptProposedAction()

    def dragMoveEvent(self, event: QDragEnterEvent) -> None:  # noqa: N802 Qt API
        if event.mimeData().hasUrls():
            event.acceptProposedAction()

    def dropEvent(self, event: QDropEvent) -> None:  # noqa: N802 Qt API
        problems: list[tuple[str, str]] = []
        for url in event.mimeData().urls():
            p = url.toLocalFile()
            if not p:
                continue
            if not p.lower().endswith(".docx"):
                problems.append((p, "only .docx files are supported"))
                continue
            if not self._has(p):
                self.addItem(p)
        if problems:
            self.rejected.emit(problems)
        event.acceptProposedAction()

    def _has(self, path: str) -> bool:
        return any(self.item(i).text() == path for i in range(self.count()))


class AnonymiseTab(QWidget):
    def __init__(self, settings: Settings, on_history_changed, parent: QWidget | None = None):
        super().__init__(parent)
        self._settings = settings
        self._on_history_changed = on_history_changed
        self._threads: list[QThread] = []  # keep refs alive

        # Keep strong refs to live workers; QThread alone is not enough to
        # prevent Python GC of the moved-to-thread QObject (silent hang).
        self._workers: list[QObject] = []

        layout = QVBoxLayout(self)
        layout.addWidget(
            QLabel(
                "Drop .docx files below, or click <b>Add files…</b>. "
                "Entity numbering is shared across a batch."
            )
        )
        self._drop = DropList()
        self._drop.setSelectionMode(QListWidget.SelectionMode.ExtendedSelection)
        self._drop.rejected.connect(self._on_rejected_drops)
        layout.addWidget(self._drop, 1)

        row = QHBoxLayout()
        add = QPushButton("Add files…")
        add.clicked.connect(self._pick_files)
        row.addWidget(add)
        remove = QPushButton("Remove selected")
        remove.clicked.connect(self._remove_selected)
        row.addWidget(remove)
        row.addStretch(1)
        self._go = QPushButton("Anonymise batch")
        self._go.clicked.connect(self._start_batch)
        row.addWidget(self._go)
        layout.addLayout(row)

    # ----- file list management -----

    def _pick_files(self) -> None:
        paths, _ = QFileDialog.getOpenFileNames(
            self, "Choose .docx files", "", "Word documents (*.docx)"
        )
        for p in paths:
            if not any(self._drop.item(i).text() == p for i in range(self._drop.count())):
                self._drop.addItem(p)

    def _remove_selected(self) -> None:
        for item in self._drop.selectedItems():
            self._drop.takeItem(self._drop.row(item))

    # ----- batch orchestration -----

    def _on_rejected_drops(self, problems: list) -> None:
        lines = "\n".join(f"• {Path(p).name}: {reason}" for p, reason in problems)
        QMessageBox.warning(self, "Can't add files", lines)

    def _start_batch(self) -> None:
        files = [Path(self._drop.item(i).text()) for i in range(self._drop.count())]
        if not files:
            QMessageBox.information(self, "Nothing to do", "Add one or more .docx files first.")
            return

        # Validate up-front so the user learns about errors/warnings before
        # spending time on the first analysis pass.
        all_errors: list[str] = []
        warnings: list[str] = []
        for f in files:
            for issue in validate_docx(f):
                (all_errors if issue.severity == "error" else warnings).append(issue.message)
        if all_errors:
            QMessageBox.critical(self, "Can't process these files", "\n".join(f"• {m}" for m in all_errors))
            return
        if warnings:
            proceed = QMessageBox.warning(
                self,
                "Large document(s)",
                "\n".join(f"• {m}" for m in warnings)
                + "\n\nProceed anyway? Detection may take several minutes.",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.Cancel,
            )
            if proceed != QMessageBox.StandardButton.Yes:
                return

        password, ok = _prompt_password(self, "Mapping password")
        if not ok or not password:
            return

        output_dir = Path(self._settings.default_output_dir) if self._settings.default_output_dir else None
        # Stash batch state on ``self`` so the per-file slots can read it
        # without capturing it in a lambda closure (which caused wrong-
        # thread widget mutation in PySide6).
        self._batch_files = files
        self._batch_index = 0
        self._batch_allocator = PlaceholderAllocator()
        self._batch_password = password
        self._batch_output_dir = output_dir
        self._go.setEnabled(False)
        self._process_next()

    def _process_next(self) -> None:
        if self._batch_index >= len(self._batch_files):
            self._go.setEnabled(True)
            self._on_history_changed()
            QMessageBox.information(
                self, "Done", f"Processed {len(self._batch_files)} file(s)."
            )
            return

        path = self._batch_files[self._batch_index]
        cfg = detector.DetectorConfig(
            confidence_threshold=self._settings.confidence_threshold,
            allowlist=self._settings.allowlist,
            denylist=self._settings.denylist,
            enabled_types=set(self._settings.enabled_types) if self._settings.enabled_types else None,
            detect_dates=self._settings.detect_dates,
            detect_money=self._settings.detect_money,
        )

        # Status ticker so the user knows we haven't frozen — first run
        # takes 10–30 s while spaCy loads the large models.
        self._ticker_start = time.monotonic()
        self._ticker_label = f"Analysing {path.name}"
        if not hasattr(self, "_ticker"):
            self._ticker = QTimer(self)
            self._ticker.timeout.connect(self._tick_status)
        self._ticker.start(500)
        self._tick_status()

        worker = AnalyseWorker(path, cfg)
        worker.finished.connect(self._after_analyse)
        worker.failed.connect(self._abort_batch)
        self._workers.append(worker)
        self._threads.append(run_in_thread(worker))

    def _tick_status(self) -> None:
        dt = time.monotonic() - self._ticker_start
        self.window().statusBar().showMessage(f"{self._ticker_label}… ({dt:0.0f}s)")

    def _after_analyse(self, analysed) -> None:
        if hasattr(self, "_ticker"):
            self._ticker.stop()
        self.window().statusBar().clearMessage()

        dlg = PreviewDialog(analysed.document.flat_text, analysed.detections, self)
        dlg.setWindowTitle(f"Review — {analysed.path.name}")
        if dlg.exec() != QDialog.DialogCode.Accepted:
            # User cancelled this file; skip and keep going so the batch
            # isn't all-or-nothing.
            self._batch_index += 1
            self._process_next()
            return

        payload = dlg.result_payload()
        approved = list(payload.approved)
        if payload.extra_terms:
            cfg = detector.DetectorConfig(
                confidence_threshold=self._settings.confidence_threshold,
                allowlist=self._settings.allowlist,
                denylist=payload.extra_terms,
            )
            _, extra_dets = detector.detect(
                analysed.document.flat_text, config=cfg, language=analysed.language
            )
            approved.extend(d for d in extra_dets if d.entity_type == "CUSTOM")

        # Stash the items each write needs so the callback doesn't have to
        # close over them (same thread-affinity hazard as above).
        self._current_analysed = analysed
        self._current_approved = approved

        self._ticker_start = time.monotonic()
        self._ticker_label = f"Writing {analysed.path.stem}_anon.docx"
        self._ticker.start(500)
        self._tick_status()

        writer = WriteWorker(
            analysed,
            approved,
            self._batch_allocator,
            self._batch_password,
            self._batch_output_dir,
        )
        writer.finished.connect(self._after_write)
        writer.failed.connect(self._abort_batch)
        self._workers.append(writer)
        self._threads.append(run_in_thread(writer))

    def _after_write(self, out_doc, out_map) -> None:
        if hasattr(self, "_ticker"):
            self._ticker.stop()
        write_run(
            source=self._current_analysed.path,
            output=Path(out_doc),
            mapping=Path(out_map),
            detections=self._current_approved,
            user=getpass.getuser(),
        )
        self.window().statusBar().showMessage(
            f"Wrote {Path(out_doc).name} ({len(self._current_approved)} entities)", 5000
        )
        self._batch_index += 1
        self._process_next()

    def _abort_batch(self, message: str) -> None:
        if hasattr(self, "_ticker"):
            self._ticker.stop()
        self.window().statusBar().clearMessage()
        self._go.setEnabled(True)
        QMessageBox.critical(self, "Error", message)


def _prompt_password(parent: QWidget, title: str) -> tuple[str, bool]:
    """Modal password prompt. Returns ``(password, accepted)``."""
    from PySide6.QtWidgets import QInputDialog, QLineEdit

    password, ok = QInputDialog.getText(parent, title, "Password:", QLineEdit.EchoMode.Password)
    return password, ok


class MainWindow(QMainWindow):
    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle("DocShield")
        self.resize(1000, 720)

        self._settings = Settings.load()

        tabs = QTabWidget()
        self._history = HistoryTab()
        self._anon = AnonymiseTab(self._settings, on_history_changed=self._history.reload)
        tabs.addTab(self._anon, "Anonymise")
        tabs.addTab(RehydrateTab(), "Rehydrate")
        tabs.addTab(self._history, "History")
        self.setCentralWidget(tabs)

        self.setStatusBar(QStatusBar())
        self.statusBar().showMessage("Loading spaCy models in the background…")

        # Kick off model pre-warm so the first Anonymise click feels fast.
        # Passing ``self`` as the connection context forces the slot to run
        # on the MainWindow's thread (the main thread) — otherwise lambda
        # slots inherit the emitter's thread and mutating widgets from a
        # worker thread triggers Qt's "cannot create children" warnings.
        self._prewarm_thread, self._prewarm_worker = start_prewarm()
        self._prewarm_worker.finished.connect(self._on_prewarm_done)
        self._prewarm_worker.failed.connect(self._on_prewarm_failed)

    def _on_prewarm_done(self, dt: float) -> None:
        self.statusBar().showMessage(f"Ready (models loaded in {dt:0.1f}s)", 4000)

    def _on_prewarm_failed(self, msg: str) -> None:
        self.statusBar().showMessage(f"Model load failed: {msg}", 8000)

        menubar = self.menuBar()
        file_menu = menubar.addMenu("&File")
        settings_act = QAction("&Settings…", self)
        settings_act.triggered.connect(self._open_settings)
        file_menu.addAction(settings_act)
        quit_act = QAction("&Quit", self)
        quit_act.triggered.connect(self.close)
        file_menu.addAction(quit_act)

    def _open_settings(self) -> None:
        dlg = SettingsDialog(self._settings, self)
        if dlg.exec() == QDialog.DialogCode.Accepted:
            self._settings = dlg.updated_settings()
            self._settings.save()
            self._anon._settings = self._settings
