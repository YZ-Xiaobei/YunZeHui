"""YunZeHui 云泽汇优化 — 界面主题与公共控件."""
from __future__ import annotations

from PySide6.QtWidgets import QHBoxLayout, QLabel, QProgressBar, QVBoxLayout, QWidget

BRAND = "YunZeHui 云泽汇优化"
VERSION = "1.0.0"

STYLESHEET = """
QWidget { font-family: "Microsoft YaHei UI"; font-size: 13px; }
QMainWindow { background: #f5f7fa; }

/* 侧边栏 */
#SideBar { background: #1e293b; }
#SideBar QLabel#brandLabel { color: #7dd3fc; font-size: 15px; font-weight: bold; padding: 14px 12px 6px; }
#SideBar QLabel#verLabel { color: #64748b; font-size: 11px; padding: 0 12px 10px; }
QPushButton.navBtn {
    color: #cbd5e1; background: transparent; border: none;
    text-align: left; padding: 11px 16px; font-size: 13px; border-radius: 6px;
}
QPushButton.navBtn:hover { background: #334155; }
QPushButton.navBtn:checked { background: #0ea5e9; color: white; font-weight: bold; }

/* 守护运行徽标 */
QLabel#guardBadge {
    color: #4ade80; font-size: 11px; padding: 4px 12px;
    background: rgba(74, 222, 128, 0.12); border-radius: 6px;
}

/* 内容区 */
QLabel.pageTitle { font-size: 20px; font-weight: bold; color: #0f172a; }
QLabel.sectionTitle { font-size: 15px; font-weight: bold; color: #334155; }
QLabel.statValue { font-size: 22px; font-weight: bold; color: #0ea5e9; }
QLabel.statLabel { color: #64748b; font-size: 12px; }

QFrame.card {
    background: white; border-radius: 10px; border: 1px solid #e2e8f0;
}

QPushButton {
    background: #0ea5e9; color: white; border: none; border-radius: 6px;
    padding: 8px 18px; font-size: 13px;
}
QPushButton:hover { background: #0284c7; }
QPushButton:disabled { background: #cbd5e1; color: #64748b; }
QPushButton.secondary { background: #e2e8f0; color: #334155; }
QPushButton.secondary:hover { background: #cbd5e1; }
QPushButton.danger { background: #ef4444; }
QPushButton.danger:hover { background: #dc2626; }

QProgressBar { border: none; background: #e2e8f0; border-radius: 5px; height: 10px; text-align: center; }
QProgressBar::chunk { background: #0ea5e9; border-radius: 5px; }

QTreeWidget, QListWidget, QTableWidget { background: white; border: 1px solid #e2e8f0; border-radius: 6px; }
QHeaderView::section { background: #f1f5f9; border: none; padding: 6px; font-weight: bold; }

QTabWidget::pane { border: 1px solid #e2e8f0; border-radius: 6px; background: white; }
QTabBar::tab { padding: 8px 16px; }
QTabBar::tab:selected { color: #0ea5e9; font-weight: bold; }

QCheckBox { spacing: 6px; }
QTextEdit { border: 1px solid #e2e8f0; border-radius: 6px; font-family: Consolas, monospace; }
"""


class StatCard(QWidget):
    """统计卡片：图标 + 数值 + 标签 + 进度条."""

    def __init__(self, title: str, icon: str = "", parent=None):
        super().__init__(parent)
        self.setObjectName("card")
        self.setProperty("class", "card")
        from PySide6.QtWidgets import QVBoxLayout, QHBoxLayout, QLabel, QProgressBar

        lay = QVBoxLayout(self)
        lay.setContentsMargins(14, 12, 14, 12)
        row = QHBoxLayout()
        self.iconLabel = QLabel(icon)
        self.iconLabel.setStyleSheet("font-size: 22px;")
        self.valueLabel = QLabel("--")
        self.valueLabel.setProperty("class", "statValue")
        row.addWidget(self.iconLabel)
        row.addWidget(self.valueLabel)
        row.addStretch()
        lay.addLayout(row)
        self.titleLabel = QLabel(title)
        self.titleLabel.setProperty("class", "statLabel")
        lay.addWidget(self.titleLabel)
        self.bar = QProgressBar()
        self.bar.setRange(0, 100)
        self.bar.setValue(0)
        lay.addWidget(self.bar)

    def set_value(self, value_text: str, percent: int | None = None):
        self.valueLabel.setText(value_text)
        if percent is None:
            self.bar.hide()
        else:
            self.bar.show()
            self.bar.setValue(max(0, min(100, int(percent))))


def human_size(n: float) -> str:
    for unit in ("B", "KB", "MB", "GB", "TB"):
        if n < 1024 or unit == "TB":
            return f"{n:.1f} {unit}" if unit != "B" else f"{int(n)} B"
        n /= 1024
    return f"{n:.1f} TB"
