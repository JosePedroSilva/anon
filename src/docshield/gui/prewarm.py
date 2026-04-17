"""Pre-load spaCy models on a background thread at GUI startup.

First-time ``AnalyzerEngine`` construction takes 10–30 s because spaCy
has to load two large models into memory. Doing that work at app launch
(instead of the first time the user clicks *Anonymise*) means the click
feels responsive.
"""

from __future__ import annotations

import sys
import time
import traceback

from PySide6.QtCore import QObject, QThread, Signal

from ..core.detector import SUPPORTED_LANGUAGES, _build_analyzer


class PrewarmWorker(QObject):
    finished = Signal(float)  # elapsed seconds
    failed = Signal(str)

    def run(self) -> None:
        t0 = time.monotonic()
        print("[docshield] pre-warming spaCy models…", file=sys.stderr, flush=True)
        try:
            _build_analyzer(SUPPORTED_LANGUAGES)
        except Exception as exc:
            traceback.print_exc()
            self.failed.emit(str(exc))
            return
        dt = time.monotonic() - t0
        print(f"[docshield] pre-warm done in {dt:.1f}s", file=sys.stderr, flush=True)
        self.finished.emit(dt)


def start_prewarm() -> tuple[QThread, PrewarmWorker]:
    worker = PrewarmWorker()
    thread = QThread()
    worker.moveToThread(thread)
    thread.started.connect(worker.run)
    worker.finished.connect(thread.quit)
    worker.failed.connect(thread.quit)
    thread.finished.connect(worker.deleteLater)
    thread.finished.connect(thread.deleteLater)
    thread.start()
    return thread, worker
