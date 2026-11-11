"""回归测试：验证「刷新时重复迭代」Bug 不再出现。

背景：v2.0.0 的首页信息卡用 `addRow()` 每次刷新都新增行、垃圾清理页不重建
勾选列表、磁盘分析页每次都 addWidget 一个状态标签，导致越刷新越长。
本脚本连续刷新三次，断言行数保持不变。

用法：
    pip install PySide6 psutil
    python tests/test_no_duplicate_rows.py

注意：温度传感器在多数台式机上不可用，HardwarePage 行数会因此少一行，
脚本已按「无电池 + 无温度」放宽为 4~6 行区间。
"""
import io
import os
import sys
import time

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from PySide6.QtCore import QTimer  # noqa: E402
from PySide6.QtWidgets import QApplication  # noqa: E402

app = QApplication([])

from YunZeHui.ui.main_window import MainWindow  # noqa: E402
from YunZeHui.ui.theme import build_qss  # noqa: E402

app.setStyleSheet(build_qss())
win = MainWindow()
win.show()

PAGE_HOME, PAGE_CLEAN, PAGE_HARDWARE = 0, 3, 10


def settle(seconds: float = 1.5) -> None:
    """等后台 Worker 线程跑完并处理 Qt 事件。"""
    app.processEvents()
    time.sleep(seconds)
    app.processEvents()


# ---- 首页：连刷 3 次，InfoCard 行数不能增长
home = win.pages[PAGE_HOME]
for _ in range(3):
    home.on_show()
    settle()
home_rows = home.info._rows
print(f"HomePage InfoCard 行数（连刷 3 次后）: {home_rows}  期望 8")

# ---- 硬件信息：连刷 2 次
hw = win.pages[PAGE_HARDWARE]
for _ in range(2):
    hw.on_show()
    settle()
hw_rows = hw.info._rows
print(f"HardwarePage 行数（连刷 2 次后）: {hw_rows}  期望 4~6（无电池/无温度时会少行）")

# ---- 垃圾清理：伪造两次扫描结果，行数必须等于结果条数
cp = win.pages[PAGE_CLEAN]
fake = [{"name": "测试项", "files": 1, "bytes": 1024}]
for _ in range(2):
    cp._scan_done(list(fake))
clean_rows = cp.table.rowCount()
print(f"CleanPage 行数（连刷 2 次后）: {clean_rows}  期望 1")

QTimer.singleShot(800, app.quit)
app.exec()

ok_home = home_rows == 8
ok_hw = 4 <= hw_rows <= 6
ok_clean = clean_rows == len(fake)
ok = ok_home and ok_hw and ok_clean
print("RESULT:", "PASS" if ok else f"FAIL (home={home_rows}, hw={hw_rows}, clean={clean_rows})")
sys.exit(0 if ok else 1)
