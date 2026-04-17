"""GUI entry point. Usable as ``python -m docshield.app`` or ``docshield-gui``."""

from __future__ import annotations

import sys

from PySide6.QtWidgets import QApplication

from .gui.main_window import MainWindow


def main() -> int:
    app = QApplication(sys.argv)
    app.setApplicationName("DocShield")
    window = MainWindow()
    window.show()
    return app.exec()


if __name__ == "__main__":  # pragma: no cover
    sys.exit(main())
