"""YunZeHui 云泽汇优化 — 程序入口.

python -m YunZeHui          启动图形界面
python -m YunZeHui --autoclean   静默清理临时文件后退出
"""
from __future__ import annotations


def main() -> int:
    import sys

    if "--autoclean" in sys.argv:
        from .core import automation
        automation.auto_clean_on_startup(silent=True)
        return 0

    from PySide6.QtCore import Qt
    from PySide6.QtWidgets import QApplication

    try:
        QApplication.setHighDpiScaleFactorRoundingPolicy(
            Qt.HighDpiScaleFactorRoundingPolicy.PassThrough)
    except Exception:
        pass

    from .ui.main_window import run
    return run()


if __name__ == "__main__":
    raise SystemExit(main())
