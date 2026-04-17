"""QThread wrappers around the pipeline so the UI stays responsive.

spaCy's first ``analyser.analyze`` call takes 5–30 s as the large models
load into memory; running it on the GUI thread would freeze the window
and make the app feel broken. These workers run the slow bits on a
background thread and emit Qt signals on completion.

Run the GUI from a terminal to see stderr progress prints — on cold
start the "loading spaCy models" step is the single longest operation.
"""

from __future__ import annotations

import sys
import time
import traceback
from pathlib import Path

from PySide6.QtCore import QObject, QThread, Signal


def _log(msg: str) -> None:
    print(f"[docshield] {msg}", file=sys.stderr, flush=True)

from ..core import detector, pipeline
from ..core.entities import Detection
from ..core.placeholder import PlaceholderAllocator


class AnalyseWorker(QObject):
    """Run detection for one document."""

    finished = Signal(object)  # pipeline.AnalysedDocument
    failed = Signal(str)

    def __init__(self, path: Path, config: detector.DetectorConfig) -> None:
        super().__init__()
        self._path = path
        self._config = config

    def run(self) -> None:
        t0 = time.monotonic()
        _log(f"analyse: start {self._path.name}")
        try:
            analysed = pipeline.analyse(self._path, self._config)
        except Exception as exc:
            traceback.print_exc()
            self.failed.emit(f"Failed to analyse {self._path.name}: {exc}")
            return
        dt = time.monotonic() - t0
        _log(f"analyse: done {self._path.name} in {dt:.1f}s ({len(analysed.detections)} hits)")
        self.finished.emit(analysed)


class WriteWorker(QObject):
    """Apply replacements and write the output files."""

    finished = Signal(object, object)  # (out_doc: Path, out_map: Path)
    failed = Signal(str)

    def __init__(
        self,
        analysed: "pipeline.AnalysedDocument",
        approved: list[Detection],
        allocator: PlaceholderAllocator,
        password: str,
        output_dir: Path | None,
    ) -> None:
        super().__init__()
        self._analysed = analysed
        self._approved = approved
        self._allocator = allocator
        self._password = password
        self._output_dir = output_dir

    def run(self) -> None:
        t0 = time.monotonic()
        _log(f"write: start {self._analysed.path.name}")
        try:
            out_doc, out_map, _ = pipeline.write_output(
                self._analysed,
                self._approved,
                self._allocator,
                password=self._password,
                output_dir=self._output_dir,
            )
        except Exception as exc:
            traceback.print_exc()
            self.failed.emit(f"Failed to write output: {exc}")
            return
        _log(f"write: done in {time.monotonic() - t0:.1f}s → {out_doc.name}")
        self.finished.emit(out_doc, out_map)


def run_in_thread(worker: QObject) -> QThread:
    """Move ``worker`` onto a fresh QThread and start it.

    **Caller must keep a Python reference to the worker** (not just the
    returned thread), otherwise PySide6 will GC the QObject as soon as
    the calling function returns, ``thread.started`` will fire, and the
    dispatch will have no target — a silent hang with no traceback.
    """
    thread = QThread()
    worker.moveToThread(thread)
    thread.started.connect(worker.run)  # type: ignore[attr-defined]
    if hasattr(worker, "finished"):
        worker.finished.connect(thread.quit)  # type: ignore[attr-defined]
    if hasattr(worker, "failed"):
        worker.failed.connect(thread.quit)  # type: ignore[attr-defined]
    thread.finished.connect(worker.deleteLater)
    thread.finished.connect(thread.deleteLater)
    thread.start()
    return thread
