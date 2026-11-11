"""YunZeHui 云泽汇优化 — UI 基础组件（PageBase / InfoCard / StatCard / SectionCard）."""
from __future__ import annotations

from PySide6.QtCore import Qt, QThread, Signal
from PySide6.QtWidgets import (
    QFrame, QGridLayout, QHBoxLayout, QLabel, QProgressBar, QPushButton,
    QScrollArea, QVBoxLayout, QWidget,
)

from .theme import C


# ============================================================ 后台任务

class Worker(QThread):
    done = Signal(object)
    failed = Signal(str)

    def __init__(self, fn, *args, **kwargs):
        super().__init__()
        self.fn = fn
        self.args = args
        self.kwargs = kwargs

    def run(self):
        import inspect
        try:
            kwargs = dict(self.kwargs)
            cb = kwargs.pop("progress_cb", None)
            if cb is not None:
                try:
                    sig = inspect.signature(self.fn)
                    params = sig.parameters
                    if "progress" in params or any(
                            p.kind == inspect.Parameter.VAR_KEYWORD for p in params.values()):
                        kwargs["progress"] = cb
                except (ValueError, TypeError):
                    pass
            self.done.emit(self.fn(*self.args, **kwargs))
        except Exception as e:
            self.failed.emit(f"{type(e).__name__}: {e}")


def run_async(page: QWidget, fn, on_done, on_fail=None, progress=None):
    """在页面上启动后台任务，自动防重入。"""
    if getattr(page, "_busy", False):
        return
    page._busy = True
    w = Worker(fn, progress_cb=progress)
    page._worker = w

    def _done(r):
        page._busy = False
        on_done(r)

    def _fail(msg):
        page._busy = False
        if on_fail:
            on_fail(msg)
        else:
            from PySide6.QtWidgets import QMessageBox
            QMessageBox.warning(page, "出错了", msg)

    w.done.connect(_done)
    w.failed.connect(_fail)
    w.start()


def hsize(n: float) -> str:
    for u in ("B", "KB", "MB", "GB", "TB"):
        if n < 1024 or u == "TB":
            return f"{int(n)} B" if u == "B" else f"{n:.1f} {u}"
        n /= 1024
    return f"{n:.1f} TB"


# ============================================================ 页面骨架

class PageBase(QWidget):
    """页面骨架：标题 + 副标题 + 滚动内容区。子类实现 build_content(lay)。"""

    title: str = ""
    subtitle: str = ""

    def __init__(self):
        super().__init__()
        outer = QVBoxLayout(self)
        outer.setContentsMargins(28, 22, 28, 20)
        outer.setSpacing(12)

        head = QVBoxLayout()
        head.setSpacing(2)
        t = QLabel(self.title)
        t.setObjectName("pageTitle")
        head.addWidget(t)
        if self.subtitle:
            s = QLabel(self.subtitle)
            s.setObjectName("pageSub")
            s.setWordWrap(True)
            head.addWidget(s)
        outer.addLayout(head)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        body = QWidget()
        self.content = QVBoxLayout(body)
        self.content.setContentsMargins(0, 4, 6, 0)
        self.content.setSpacing(12)
        scroll.setWidget(body)
        outer.addWidget(scroll, 1)
        self.build_content(self.content)

    def build_content(self, lay: QVBoxLayout):
        raise NotImplementedError

    def on_show(self):  # noqa: B027
        pass


# ============================================================ 卡片组件

def Card() -> QFrame:
    f = QFrame()
    f.setProperty("class", "card")
    return f


class SectionCard(QFrame):
    """带标题的分区卡片。"""

    def __init__(self, title: str = "", subtitle: str = "", parent=None):
        super().__init__(parent)
        self.setProperty("class", "card")
        lay = QVBoxLayout(self)
        lay.setContentsMargins(16, 14, 16, 14)
        lay.setSpacing(10)
        if title:
            t = QLabel(title)
            t.setObjectName("sectionTitle")
            lay.addWidget(t)
        if subtitle:
            s = QLabel(subtitle)
            s.setObjectName("muted")
            s.setWordWrap(True)
            lay.addWidget(s)
        self.body = lay

    def add(self, w):
        self.body.addWidget(w)
        return w

    def add_layout(self, ly):
        self.body.addLayout(ly)
        return ly

    def add_stretch(self):
        self.body.addStretch()


class InfoCard(SectionCard):
    """键值信息卡：**更新式**。set_item 首次创建行，之后只改文本，绝不重复追加。

    行索引由 self._rows 计数器维护，不依赖 QGridLayout.rowCount()
    （Qt 的 rowCount 在布局未 flush 时可能返回不准确值）。
    """

    def __init__(self, title: str = "", parent=None):
        super().__init__(title, parent=parent)
        self._grid = QGridLayout()
        self._grid.setHorizontalSpacing(18)
        self._grid.setVerticalSpacing(8)
        self.body.addLayout(self._grid)
        self._items: dict[str, tuple[QLabel, QLabel]] = {}
        self._rows = 0  # 显式行计数器

    def set_item(self, key: str, value: str):
        """设置/更新一项。首次创建行，之后只改文本。"""
        if key in self._items:
            self._items[key][1].setText(str(value))
            return
        keyLbl = QLabel(key)
        keyLbl.setObjectName("infoKey")
        valLbl = QLabel(str(value))
        valLbl.setObjectName("infoVal")
        valLbl.setTextInteractionFlags(Qt.TextSelectableByMouse)
        self._grid.addWidget(keyLbl, self._rows, 0, Qt.AlignTop)
        self._grid.addWidget(valLbl, self._rows, 1)
        self._items[key] = (keyLbl, valLbl)
        self._rows += 1


class StatCard(QFrame):
    """统计卡：大数字 + 单位 + 标题 + 进度条（颜色随水位变化）。"""

    def __init__(self, icon: str, title: str, parent=None):
        super().__init__(parent)
        self.setProperty("class", "card")
        lay = QVBoxLayout(self)
        lay.setContentsMargins(16, 14, 16, 12)
        lay.setSpacing(4)
        top = QHBoxLayout()
        ic = QLabel(icon)
        ic.setObjectName("statIcon")
        top.addWidget(ic)
        top.addStretch()
        self.titleLbl = QLabel(title)
        self.titleLbl.setObjectName("statTitle")
        top.addWidget(self.titleLbl)
        lay.addLayout(top)
        row = QHBoxLayout()
        self.valueLbl = QLabel("--")
        self.valueLbl.setObjectName("statValue")
        row.addWidget(self.valueLbl)
        self.unitLbl = QLabel("")
        self.unitLbl.setObjectName("statUnit")
        row.addWidget(self.unitLbl)
        row.addStretch()
        lay.addLayout(row)
        self.bar = QProgressBar()
        self.bar.setRange(0, 100)
        self.bar.setValue(0)
        self.bar.setTextVisible(False)
        lay.addWidget(self.bar)

    def set_value(self, value_text: str, percent: float | None = None, unit: str = ""):
        self.valueLbl.setText(value_text)
        self.unitLbl.setText(unit)
        if percent is None:
            self.bar.hide()
            return
        self.bar.show()
        p = max(0, min(100, int(percent)))
        self.bar.setValue(p)
        color = C["bar_ok"] if p < 60 else (C["bar_mid"] if p < 85 else C["bar_high"])
        self.bar.setStyleSheet(
            f"QProgressBar::chunk {{ background: {color}; border-radius: 5px; }}")

    def set_plain(self, value_text: str):
        self.valueLbl.setText(value_text)
        self.bar.hide()


def button_row(*buttons, stretch=True) -> QHBoxLayout:
    ly = QHBoxLayout()
    ly.setSpacing(10)
    for b in buttons:
        ly.addWidget(b)
    if stretch:
        ly.addStretch()
    return ly
