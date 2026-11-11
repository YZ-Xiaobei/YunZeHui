"""YunZeHui 云泽汇优化 — 设计系统 v3（设计令牌 + 全局样式）."""
from __future__ import annotations

# ---------------- 设计令牌 ----------------
C = {
    # 品牌主色
    "primary": "#2563eb",
    "primary_hover": "#1d4ed8",
    "primary_soft": "rgba(37, 99, 235, 0.10)",
    # 中性色
    "bg": "#f4f6fb",
    "surface": "#ffffff",
    "line": "#e3e8f2",
    "text": "#17223b",
    "text_2": "#5b6b8c",
    "text_3": "#94a3bf",
    # 侧边栏（深色）
    "side_bg": "#101a30",
    "side_text": "#b9c5dd",
    "side_hover": "#1b2947",
    "side_active": "#2563eb",
    "side_title": "#7ea6ff",
    # 语义色
    "ok": "#16a34a",
    "warn": "#d97706",
    "danger": "#dc2626",
    "danger_hover": "#b91c1c",
    # 图表
    "bar_ok": "#22c55e",
    "bar_mid": "#f59e0b",
    "bar_high": "#ef4444",
}

SP = {"xs": 4, "s": 8, "m": 14, "l": 20, "xl": 28}

RADIUS = "10px"


def build_qss() -> str:
    return f"""
* {{ outline: none; }}
QWidget {{ font-family: "Microsoft YaHei UI", "Segoe UI"; font-size: 13px; color: {C['text']}; }}

/* ---------- 主窗口 ---------- */
#Root {{ background: {C['bg']}; }}

/* ---------- 侧边栏 ---------- */
#SideBar {{ background: {C['side_bg']}; }}
#brand {{ color: #ffffff; font-size: 17px; font-weight: 800; padding: 18px 18px 2px; letter-spacing: 2px; }}
#brandSub {{ color: {C['side_title']}; font-size: 11px; padding: 0 18px 14px; }}
#navGroup {{ color: {C['text_3']}; font-size: 11px; font-weight: 700; padding: 12px 18px 4px; letter-spacing: 1px; }}
QPushButton.nav {{
    color: {C['side_text']}; background: transparent; border: none;
    text-align: left; padding: 9px 14px; margin: 1px 8px; border-radius: 8px; font-size: 13px;
}}
QPushButton.nav:hover {{ background: {C['side_hover']}; }}
QPushButton.nav:checked {{ background: {C['side_active']}; color: #ffffff; font-weight: 700; }}
#guardBadge {{
    color: #86efac; background: rgba(34,197,94,0.14); border-radius: 8px;
    font-size: 11px; padding: 6px 10px; margin: 6px 8px;
}}
#adminChip {{ color: #fbbf24; font-size: 10px; padding: 4px 12px; }}
#adminChipOk {{ color: #86efac; font-size: 10px; padding: 4px 12px; }}

/* ---------- 页面 ---------- */
#pageTitle {{ font-size: 22px; font-weight: 800; }}
#pageSub {{ color: {C['text_2']}; font-size: 12px; }}
#sectionTitle {{ font-size: 14px; font-weight: 700; color: {C['text']}; }}
#muted {{ color: {C['text_2']}; font-size: 12px; }}

/* ---------- 卡片 ---------- */
QFrame.card {{ background: {C['surface']}; border: 1px solid {C['line']}; border-radius: {RADIUS}; }}
QFrame.card:hover {{ border-color: #c9d6ee; }}

/* 统计卡 */
#statValue {{ font-size: 26px; font-weight: 800; color: {C['primary']}; }}
#statUnit {{ font-size: 12px; color: {C['text_2']}; }}
#statIcon {{ font-size: 20px; }}
#statTitle {{ color: {C['text_2']}; font-size: 12px; }}

/* 信息行 */
#infoKey {{ color: {C['text_2']}; font-size: 12px; }}
#infoVal {{ font-size: 13px; font-weight: 600; }}

/* ---------- 按钮 ---------- */
QPushButton {{
    background: {C['primary']}; color: #ffffff; border: none; border-radius: 8px;
    padding: 8px 18px; font-size: 13px; font-weight: 600;
}}
QPushButton:hover {{ background: {C['primary_hover']}; }}
QPushButton:disabled {{ background: #c7d3e8; color: #8fa0bd; }}
QPushButton.secondary {{ background: #eef2f9; color: {C['text']}; border: 1px solid {C['line']}; }}
QPushButton.secondary:hover {{ background: #e2e9f5; }}
QPushButton.danger {{ background: {C['danger']}; }}
QPushButton.danger:hover {{ background: {C['danger_hover']}; }}
QPushButton.success {{ background: {C['ok']}; }}
QPushButton.success:hover {{ background: #15803d; }}
QPushButton.flat {{
    background: {C['primary_soft']}; color: {C['primary']}; border: none; padding: 6px 14px;
}}
QPushButton.flat:hover {{ background: rgba(37,99,235,0.18); }}
QPushButton.small {{ padding: 5px 12px; font-size: 12px; }}

/* ---------- 表格 ---------- */
QTableWidget {{
    background: {C['surface']}; border: 1px solid {C['line']}; border-radius: {RADIUS};
    gridline-color: transparent; alternate-background-color: #fafbfe;
    selection-background-color: {C['primary_soft']}; selection-color: {C['text']};
}}
QTableWidget::item {{ padding: 6px 8px; border-bottom: 1px solid #f0f3f9; }}
QHeaderView::section {{
    background: #f7f9fd; color: {C['text_2']}; border: none; border-bottom: 1px solid {C['line']};
    padding: 8px; font-weight: 700; font-size: 12px;
}}
QTableCornerButton::section {{ background: #f7f9fd; border: none; }}

/* ---------- 输入控件 ---------- */
QLineEdit, QSpinBox, QDoubleSpinBox {{
    background: {C['surface']}; border: 1px solid {C['line']}; border-radius: 8px; padding: 6px 10px;
}}
QLineEdit:focus, QSpinBox:focus, QDoubleSpinBox:focus {{ border-color: {C['primary']}; }}
QCheckBox {{ spacing: 8px; }}
QCheckBox::indicator {{ width: 16px; height: 16px; border: 1.5px solid #c3cfe3; border-radius: 4px; background: #ffffff; }}
QCheckBox::indicator:checked {{ background: {C['primary']}; border-color: {C['primary']};
    image: url(none); }}

/* ---------- 进度条 ---------- */
QProgressBar {{ background: #e8edf7; border: none; border-radius: 5px; height: 8px; text-align: center; color: transparent; }}
QProgressBar::chunk {{ border-radius: 5px; }}

/* ---------- 滚动区 ---------- */
QScrollArea {{ border: none; background: transparent; }}
QScrollBar:vertical {{ background: transparent; width: 9px; margin: 2px; }}
QScrollBar::handle:vertical {{ background: #cdd8ec; border-radius: 4px; min-height: 40px; }}
QScrollBar::handle:vertical:hover {{ background: #b3c2dd; }}
QScrollBar::add-line, QScrollBar::sub-line {{ height: 0; }}

/* ---------- 其他 ---------- */
QTextEdit {{ background: {C['surface']}; border: 1px solid {C['line']}; border-radius: 8px;
    font-family: Consolas, monospace; font-size: 12px; }}
QMessageBox {{ background: {C['surface']}; }}
QToolTip {{ background: {C['side_bg']}; color: #ffffff; border: none; padding: 6px; }}
"""
