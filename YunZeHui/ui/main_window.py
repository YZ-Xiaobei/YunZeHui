"""YunZeHui 云泽汇优化 — 主窗口."""
from __future__ import annotations

from PySide6.QtCore import Qt, QTimer
from PySide6.QtWidgets import (
    QApplication, QButtonGroup, QFrame, QHBoxLayout, QLabel, QMainWindow,
    QPushButton, QStackedWidget, QVBoxLayout, QWidget, QMessageBox,
)

from .. import __version__
from ..core import admin
from ..core import guardian as guardian_mod
from ..ui import tray as tray_mod
from .pages import (
    HomePage, BoostPage, CleanPage, GamesPage, StartupPage,
    NetworkPage, DiskPage, HardwarePage, SettingsPage,
)
from .new_pages import GuardianPage, ServicesPage, DebloatPage

NAV_ITEMS = [
    ("🏠", "首页", HomePage),
    ("🚀", "游戏加速", BoostPage),
    ("🛡️", "内存守护", GuardianPage),
    ("🧹", "垃圾清理", CleanPage),
    ("🎮", "游戏库", GamesPage),
    ("📋", "启动项", StartupPage),
    ("🌐", "网络优化", NetworkPage),
    ("🔧", "服务精简", ServicesPage),
    ("📦", "预装清理", DebloatPage),
    ("💾", "磁盘分析", DiskPage),
    ("🖥️", "硬件信息", HardwarePage),
    ("⚙️", "设置", SettingsPage),
]


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("YunZeHui 云泽汇优化")
        self.resize(1060, 700)
        self._build_ui()
        self._check_admin()

    def _build_ui(self):
        central = QWidget()
        root = QHBoxLayout(central)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        # ---- 侧边栏
        side = QFrame()
        side.setObjectName("SideBar")
        side.setFixedWidth(180)
        sideLay = QVBoxLayout(side)
        sideLay.setContentsMargins(8, 8, 8, 8)
        brand = QLabel("YunZeHui")
        brand.setObjectName("brandLabel")
        sideLay.addWidget(brand)
        ver = QLabel(f"云泽汇优化 v{__version__}")
        ver.setObjectName("verLabel")
        sideLay.addWidget(ver)

        self.navGroup = QButtonGroup(self)
        self.navGroup.setExclusive(True)
        self._buttons = []
        for i, (icon, text, _cls) in enumerate(NAV_ITEMS):
            b = QPushButton(f"{icon}  {text}")
            b.setProperty("class", "navBtn")
            b.setCheckable(True)
            b.setCursor(Qt.PointingHandCursor)
            self.navGroup.addButton(b, i)
            b.clicked.connect(lambda _=False, idx=i: self.switch_page(idx))
            sideLay.addWidget(b)
            self._buttons.append(b)
        sideLay.addStretch()
        # 守护状态徽标
        self.guardBadge = QLabel("")
        self.guardBadge.setObjectName("guardBadge")
        self.guardBadge.setVisible(False)
        sideLay.addWidget(self.guardBadge)
        self.adminLabel = QLabel()
        sideLay.addWidget(self.adminLabel)
        root.addWidget(side)

        # ---- 内容
        self.stack = QStackedWidget()
        self.pages = []
        for _icon, _text, cls in NAV_ITEMS:
            page = cls()
            self.stack.addWidget(page)
            self.pages.append(page)
        root.addWidget(self.stack, 1)
        self.setCentralWidget(central)
        self._buttons[0].setChecked(True)

        # ---- 托盘
        self.tray = tray_mod.TrayController(self)

        # ---- 内存监控定时器（更新托盘文字）
        self._mem_timer = QTimer(self)
        self._mem_timer.timeout.connect(self._update_tray_mem)
        self._mem_timer.start(3000)

        # ---- 启动时自动恢复守护
        g = guardian_mod.get_guardian()
        if g.cfg.get("enabled"):
            g.start_guardian()
        self.tray.update_guard_text()

    def _update_tray_mem(self):
        try:
            import psutil
            vm = psutil.virtual_memory()
            self.tray.update_mem_text(
                f"内存：{vm.available / (1 << 30):.1f} GB 可用（{100 - vm.percent:.0f}% 空闲）")
        except Exception:
            pass
        # 同步侧边栏守护徽标与托盘文字
        g = guardian_mod.get_guardian()
        self.guardBadge.setVisible(g.running)
        self.guardBadge.setText("🛡️ 内存守护运行中")
        self.tray.update_guard_text()

    def switch_page(self, idx: int):
        self.stack.setCurrentIndex(idx)
        page = self.pages[idx]
        if hasattr(page, "on_show"):
            page.on_show()

    def _check_admin(self):
        if admin.is_admin():
            self.adminLabel.setText("🛡️ 管理员模式")
            self.adminLabel.setStyleSheet("color:#4ade80; font-size:11px; padding:6px 12px;")
        else:
            self.adminLabel.setText("⚠️ 未以管理员运行（部分功能受限）")
            self.adminLabel.setStyleSheet("color:#fbbf24; font-size:10px; padding:6px 10px;")
            self.adminLabel.setWordWrap(True)

    def closeEvent(self, event):
        """关闭窗口 = 最小化到托盘；真正退出走托盘菜单。"""
        from PySide6.QtWidgets import QSystemTrayIcon
        if self.tray.tray and self.tray.tray.isVisible():
            self.tray.tray.showMessage(
                "YunZeHui 云泽汇优化",
                "程序已最小化到系统托盘，右键托盘图标可退出或快速清理内存。",
                QSystemTrayIcon.Information, 3000)
            self.hide()
            event.ignore()
        else:
            QApplication.closeAllWindows()
            event.accept()


def run() -> int:
    import sys
    app = QApplication(sys.argv)
    from .widgets import STYLESHEET
    app.setStyleSheet(STYLESHEET)
    win = MainWindow()
    win.show()
    return app.exec()
