from __future__ import annotations

import sys

from .bootstrap import bootstrap


def main() -> int:
    try:
        from PySide6.QtWidgets import QApplication
    except ModuleNotFoundError as exc:
        raise SystemExit(
            "PySide6 is not installed. Run: pip install -e .  (or pip install -e \".[dev]\")"
        ) from exc

    from .ui.main_window import MainWindow

    app = QApplication(sys.argv)
    app.setApplicationName("Telegram Migration Studio")
    context = bootstrap()
    context.runtime.start()
    context.accounts.normalize_legacy_operation_states()
    context.recovery.normalize_after_restart()
    window = MainWindow(context)
    window.show()
    app.aboutToQuit.connect(context.runtime.stop)
    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())
