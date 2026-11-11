"""YunZeHui 云泽汇优化 — 主窗口（v3 新框架：分组导航 + 托盘）."""
from __future__ import annotations

from PySide6.QtCore import Qt, QTimer
from PySide6.QtWidgets import (
    QApplication, QButtonGroup, QFrame, QHBoxLayout, QLabel, QMainWindow,
    QPushButton, QStackedWidget, QVBoxLayout, QWidget,
)

from .. import __version__
from ..core import admin, guardian as guardian_mod
from . import tray as tray_mod
from .pages_main import BoostPage, CleanPage, GuardianPage, HomePage
from .pages_system import DiskPage, HardwarePage, SettingsPage
from .pages_tools import DebloatPage, GamesPage, NetworkPage, ServicesPage, StartupPage
from .theme import build_qss

# (分组, 图标, 名称, 页面类)
NAV_ITEMS = [
    ("概览", "🏠", "首页", "HomePage"),
    ("优化", "🚀", "游戏加速", "BoostPage"),
    ("优化", "🛡️", "内存守护", "GuardianPage"),
    ("优化", "🧹", "垃圾清理", "CleanPage"),
    ("优化", "🎮", "游戏库", "GamesPage"),
    ("优化", "📋", "启动项", "StartupPage"),
    ("优化", "🌐", "网络优化", "NetworkPage"),
    ("优化", "🔧", "服务精简", "ServicesPage"),
    ("优化", "📦", "预装清理", "DebloatPage"),
    ("工具", "💾", "磁盘分析", "DiskPage"),
    ("工具", "🖥️", "硬件信息", "HardwarePage"),
    ("系统", "⚙️", "设置", "SettingsPage"),
]

PAGE_CLASSES = {
    "HomePage": HomePage, "BoostPage": BoostPage, "GuardianPage": GuardianPage,
    "CleanPage": CleanPage, "GamesPage": GamesPage, "StartupPage": StartupPage,
    "NetworkPage": NetworkPage, "ServicesPage": ServicesPage, "DebloatPage": DebloatPage,
    "DiskPage": DiskPage, "HardwarePage": HardwarePage, "SettingsPage": SettingsPage,
}


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("YunZeHui 云泽汇优化")
        self.resize(1120, 720)
        self._build_ui()
        self._check_admin()
        self._setup_tray_and_guardian()

    # ------------------------------------------------ UI

    def _build_ui(self):
        root_widget = QWidget()
        root_widget.setObjectName("Root")
        root = QHBoxLayout(root_widget)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)
        self.setCentralWidget(root_widget)

        # ---- 侧边栏
        side = QFrame()
        side.setObjectName("SideBar")
        side.setFixedWidth(190)
        sv = QVBoxLayout(side)
        sv.setContentsMargins(0, 0, 0, 10)
        sv.setSpacing(0)
        brand = QLabel("YunZeHui")
        brand.setObjectName("brand")
        sv.addWidget(brand)
        sub = QLabel(f"云泽汇优化 v{__version__}")
        sub.setObjectName("brandSub")
        sv.addWidget(sub)

        self.navGroup = QButtonGroup(self)
        self.navGroup.setExclusive(True)
        self._buttons: list[QPushButton] = []
        self._page_refs: list = []
        last_group = None
        for gi, (group, icon, text, cls_name) in enumerate(NAV_ITEMS):
            if group != last_group:
                gLabel = QLabel(group.upper())
                gLabel.setObjectName("navGroup")
                sv.addWidget(gLabel)
                last_group = group
            b = QPushButton(f"{icon}  {text}")
            b.setProperty("class", "nav")
            b.setCheckable(True)
            b.setCursor(Qt.PointingHandCursor)
            b.clicked.connect(lambda _=False, idx=len(self._buttons): self.switch_page(idx))
            self.navGroup.addButton(b)
            sv.addWidget(b)
            self._buttons.append(b)
            self._page_refs.append(cls_name)

        sv.addStretch()
        self.guardBadge = QLabel("🛡️ 内存守护运行中")
        self.guardBadge.setObjectName("guardBadge")
        self.guardBadge.setVisible(False)
        sv.addWidget(self.guardBadge)
        self.adminLabel = QLabel()
        self.adminLabel.setObjectName("adminChip")
        sv.addWidget(self.adminLabel)

        # ---- 内容栈
        self.stack = QStackedWidget()
        self.pages = []
        for _g, _i, _t, cls_name in NAV_ITEMS:
            page = PAGE_CLASSES[cls_name]()
            self.stack.addWidget(page)
            self.pages.append(page)
        root.addWidget(side)
        root.addWidget(self.stack, 1)
        self._buttons[0].setChecked(True)

    # ------------------------------------------------ 生命周期

    def _setup_tray_and_guardian(self):
        self.tray = tray_mod.TrayController(self)
        self._memTimer = QTimer(self)
        self._memTimer.timeout.connect(self._update_tray_mem)
        self._memTimer.start(3000)
        g = guardian_mod.get_guardian()
        if g.cfg.get("enabled"):
            g.start_guardian()
        self.tray.update_guard_text()

    def switch_page(self, idx: int):
        if not (0 <= idx < len(self.pages)):
            return
        self.stack.setCurrentIndex(idx)
        # 程序化切页（托盘、脚本、快捷键）时同步侧栏选中态，避免高亮停在旧项
        btn = self._buttons[idx]
        if not btn.isChecked():
            btn.setChecked(True)
        page = self.pages[idx]
        if hasattr(page, "on_show"):
            page.on_show()

    def _check_admin(self):
        if admin.is_admin():
            self.adminLabel.setText("🛡️ 管理员模式")
            self._set_chip_object_name("adminChipOk")
        else:
            self.adminLabel.setText("⚠️ 未以管理员运行")
            self._set_chip_object_name("adminChip")
            self.adminLabel.setToolTip("系统级功能受限；可在「设置」页提权重启")

    def _set_chip_object_name(self, name: str):
        """切换 objectName 后重新 polish，让 QSS 立刻生效（否则样式不刷新）。"""
        if self.adminLabel.objectName() == name:
            return
        self.adminLabel.setObjectName(name)
        st = self.adminLabel.style()
        st.unpolish(self.adminLabel)
        st.polish(self.adminLabel)

    def _update_tray_mem(self):
        try:
            import psutil
            vm = psutil.virtual_memory()
            self.tray.update_mem_text(
                f"内存：{vm.available / (1 << 30):.1f} GB 可用（{100 - vm.percent:.0f}% 空闲）")
        except Exception:
            pass
        g = guardian_mod.get_guardian()
        self.guardBadge.setVisible(g.running)
        self.tray.update_guard_text()

    def closeEvent(self, event):
        from PySide6.QtWidgets import QSystemTrayIcon
        if self.tray.tray and self.tray.tray.isVisible():
            self.tray.tray.showMessage(
                "YunZeHui 云泽汇优化",
                "已最小化到系统托盘；右键托盘图标可退出或快速清理内存。",
                QSystemTrayIcon.Information, 3000)
            self.hide()
            event.ignore()
        else:
            QApplication.closeAllWindows()
            event.accept()


def run() -> int:
    import sys
    app = QApplication(sys.argv)
    app.setStyleSheet(build_qss())
    win = MainWindow()
    win.show()
    return app.exec()
