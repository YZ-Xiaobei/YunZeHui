"""YunZeHui 云泽汇优化 — 托盘图标与开机自启."""
from __future__ import annotations

import os
import sys

try:
    import winreg
except ImportError:
    winreg = None

AUTORUN_KEY = r"Software\Microsoft\Windows\CurrentVersion\Run"
AUTORUN_NAME = "YunZeHui"


def is_autorun_enabled() -> bool:
    if winreg is None:
        return False
    try:
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, AUTORUN_KEY) as k:
            winreg.QueryValueEx(k, AUTORUN_NAME)
            return True
    except OSError:
        return False


def set_autorun(enable: bool) -> bool:
    """开机自启（当前用户 HKCU Run 键）。"""
    if winreg is None:
        return False
    try:
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, AUTORUN_KEY, 0, winreg.KEY_WRITE) as k:
            if enable:
                exe = sys.executable
                if getattr(sys, "frozen", False):
                    # PyInstaller 打包：exe 自身
                    cmd = f'"{exe}"'
                else:
                    main = os.path.abspath(sys.argv[0]) if sys.argv else ""
                    cmd = f'"{exe}" "{main}"'
                winreg.SetValueEx(k, AUTORUN_NAME, 0, winreg.REG_SZ, cmd)
            else:
                try:
                    winreg.DeleteValue(k, AUTORUN_NAME)
                except OSError:
                    pass
            return True
    except OSError:
        return False


class TrayController:
    """系统托盘图标：显示内存水位 + 快捷操作。PySide6 QSystemTrayIcon。"""

    def __init__(self, window):
        self.window = window
        self.tray = None
        self._build()

    def _build(self):
        from PySide6.QtGui import QAction, QIcon, QColor, QPixmap, QPainter
        from PySide6.QtWidgets import QMenu, QSystemTrayIcon

        # 用代码生成一个简单的圆形图标（无外部资源依赖）
        pm = QPixmap(64, 64)
        pm.fill(QColor(0, 0, 0, 0))
        painter = QPainter(pm)
        painter.setRenderHint(QPainter.Antialiasing)
        painter.setBrush(QColor("#0ea5e9"))
        painter.setPen(QColor("#0369a1"))
        painter.drawEllipse(4, 4, 56, 56)
        painter.setPen(QColor("white"))
        font = painter.font()
        font.setPixelSize(30)
        font.setBold(True)
        painter.setFont(font)
        painter.drawText(pm.rect(), 0x0084, "Y")  # AlignCenter
        painter.end()

        self.tray = QSystemTrayIcon(QIcon(pm), self.window)
        self.tray.setToolTip("YunZeHui 云泽汇优化")
        menu = QMenu()

        a_show = QAction("显示主窗口", self.window)
        a_show.triggered.connect(self._show_window)
        menu.addAction(a_show)

        self.mem_action = QAction("内存：--", self.window)
        self.mem_action.setEnabled(False)
        menu.addAction(self.mem_action)

        a_clean = QAction("🧹 立即清理内存", self.window)
        a_clean.triggered.connect(self._quick_clean)
        menu.addAction(a_clean)

        self.guard_action = QAction("🛡️ 内存守护：关", self.window)
        self.guard_action.triggered.connect(self._toggle_guardian)
        menu.addAction(self.guard_action)

        menu.addSeparator()
        a_quit = QAction("退出", self.window)
        a_quit.triggered.connect(self._quit)
        menu.addAction(a_quit)

        self.tray.setContextMenu(menu)
        self.tray.activated.connect(self._activated)
        self.tray.show()

    def _activated(self, reason):
        from PySide6.QtWidgets import QSystemTrayIcon
        if reason == QSystemTrayIcon.Trigger:  # 单击
            self._show_window()

    def _show_window(self):
        w = self.window
        w.showNormal()
        w.raise_()
        w.activateWindow()

    def _quick_clean(self):
        from ..core import guardian
        guardian.get_guardian().trigger_manual()

    def _toggle_guardian(self):
        from ..core import guardian
        g = guardian.get_guardian()
        if g.running:
            g.stop_guardian()
        else:
            g.start_guardian()
        self.update_guard_text()

    def update_guard_text(self):
        from ..core import guardian
        g = guardian.get_guardian()
        state = "开" if g.running else "关"
        self.guard_action.setText(f"🛡️ 内存守护：{state}")

    def update_mem_text(self, text: str):
        self.mem_action.setText(text)

    def _quit(self):
        from PySide6.QtWidgets import QApplication
        from ..core import guardian
        guardian.get_guardian().stop_guardian()
        self.tray.hide()
        QApplication.quit()
