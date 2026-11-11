"""YunZeHui 云泽汇优化 — 页面：磁盘分析 / 硬件信息 / 设置."""
from __future__ import annotations

import os

from PySide6.QtCore import Qt as _Qt
from PySide6.QtWidgets import (
    QCheckBox, QFileDialog, QHBoxLayout, QLabel, QLineEdit, QMessageBox,
    QPushButton, QTableWidget, QTableWidgetItem, QVBoxLayout,
)

from .. import __version__
from ..core import admin, diagnostics, disk, hardware
from .base import Card, InfoCard, PageBase, SectionCard, button_row, hsize, run_async

CHECKED = _Qt.CheckState.Checked


# ================================================================ 磁盘分析

class DiskPage(PageBase):
    title = "磁盘分析"
    subtitle = "分区用量与目录占用分析"

    def build_content(self, lay: QVBoxLayout):
        self.drives = QTableWidget(0, 4)
        self.drives.setHorizontalHeaderLabels(["分区", "总容量", "已用", "剩余"])
        self.drives.horizontalHeader().setStretchLastSection(True)
        self.drives.setColumnWidth(0, 90)
        self.drives.setColumnWidth(1, 130)
        self.drives.setColumnWidth(2, 160)
        self.drives.setMaximumHeight(180)
        lay.addWidget(self.drives)

        row = QHBoxLayout()
        self.dirInput = QLineEdit()
        self.dirInput.setPlaceholderText("输入要分析的目录，如 D:\\")
        pick = QPushButton("选择…")
        pick.setProperty("class", "secondary")
        pick.clicked.connect(self._pick)
        ana = QPushButton("分析子目录占用")
        ana.clicked.connect(self._analyze)
        row.addWidget(self.dirInput, 1)
        row.addWidget(pick)
        row.addWidget(ana)
        lay.addLayout(row)

        self.status = QLabel("")
        self.status.setObjectName("muted")
        lay.addWidget(self.status)

        self.result = QTableWidget(0, 2)
        self.result.setHorizontalHeaderLabels(["目录", "占用 GB"])
        self.result.horizontalHeader().setStretchLastSection(True)
        self.result.setColumnWidth(0, 480)
        self.result.setMinimumHeight(260)
        lay.addWidget(self.result, 1)

    def on_show(self):
        # 修复重复迭代 bug：先清空再填充
        self.drives.setRowCount(0)
        for d in disk.list_drives():
            r = self.drives.rowCount()
            self.drives.insertRow(r)
            self.drives.setItem(r, 0, QTableWidgetItem(d["drive"]))
            self.drives.setItem(r, 1, QTableWidgetItem(f"{d['total_gb']} GB"))
            self.drives.setItem(r, 2, QTableWidgetItem(f"{d['used_gb']} GB（{d['percent']}%）"))
            self.drives.setItem(r, 3, QTableWidgetItem(f"{d['free_gb']} GB"))

    def _pick(self):
        d = QFileDialog.getExistingDirectory(self, "选择目录")
        if d:
            self.dirInput.setText(d)

    def _analyze(self):
        path = self.dirInput.text().strip() or "C:\\"
        self.result.setRowCount(0)
        self.status.setText("分析中，可能需要几分钟…")
        run_async(self, lambda **kw: disk.analyze_directory(path, depth=2, min_mb=50),
                  self._analyzed, on_fail=lambda m: self.status.setText(f"失败：{m}"))

    def _analyzed(self, rows):
        # 修复重复迭代 bug：表格只清空重建，状态栏用 setText 而不是 addWidget
        for row in rows:
            r = self.result.rowCount()
            self.result.insertRow(r)
            self.result.setItem(r, 0, QTableWidgetItem(row["path"]))
            self.result.setItem(r, 1, QTableWidgetItem(str(row["gb"])))
        self.status.setText(f"分析完成：{len(rows)} 个目录 ≥ 50 MB")


# ================================================================ 硬件信息

class HardwarePage(PageBase):
    title = "硬件信息"
    subtitle = "CPU / 内存 / GPU / 电池 / 温度，可导出诊断报告"

    def build_content(self, lay: QVBoxLayout):
        self.info = InfoCard("硬件概览")
        lay.addWidget(self.info)

        self.gpuCard = SectionCard("显卡")
        self.gpuLbl = QLabel("--")
        self.gpuLbl.setWordWrap(True)
        self.gpuCard.add(self.gpuLbl)
        lay.addWidget(self.gpuCard)

        lay.addLayout(button_row(
            _mkbtn("🔄 刷新", "secondary", self.on_show),
            _mkbtn("生成诊断报告", "primary", self._report),
        ))
        lay.addStretch()

    def on_show(self):
        run_async(self, hardware.get_full_report, self._fill)

    def _fill(self, hw):
        # 更新式（InfoCard 内部复用行），修复重复追加 bug
        self.info.set_item("处理器", f"{hw['cpu']['name']}（{hw['cpu']['cores']}C/{hw['cpu']['threads']}T @ {hw['cpu']['freq_mhz']} MHz）")
        self.info.set_item("内存", f"{hw['memory']['used_gb']} / {hw['memory']['total_gb']} GB（{hw['memory']['percent']}%）")
        self.info.set_item("操作系统", f"{hw['os']['system']} · {hw['os']['machine']}（{hw['os']['version']}）")
        self.info.set_item("设备类型", hw["device_type"])
        if hw.get("battery"):
            b = hw["battery"]
            self.info.set_item("电池", f"{b['percent']}%{'（充电中）' if b['plugged'] else ''}")
        temps = hw.get("temps") or {}
        self.info.set_item("温度传感器", "可用" if temps else "不可用（台式机常见）")
        lines = []
        for g in hw["gpus"]:
            vram = f"（{g['vram_mb']} MB 显存）" if g["vram_mb"] else ""
            lines.append(f"• {g['name']}{vram}")
        self.gpuLbl.setText("\n".join(lines) or "未检测到")

    def _report(self):
        path, _ = QFileDialog.getSaveFileName(self, "保存诊断报告", "YunZeHui_report.txt",
                                              "文本文件 (*.txt)")
        if path and diagnostics.save_report(path):
            QMessageBox.information(self, "已保存", f"报告已保存到 {path}")


# ================================================================ 设置

class SettingsPage(PageBase):
    title = "设置"
    subtitle = "权限、开机自启、后台清理进程列表"

    def build_content(self, lay: QVBoxLayout):
        perm = SectionCard("权限")
        row = QHBoxLayout()
        self.adminStatus = QLabel()
        self.adminStatus.setObjectName("infoVal")
        row.addWidget(self.adminStatus)
        row.addStretch()
        elev = QPushButton("以管理员身份重启")
        elev.setProperty("class", "secondary")
        elev.clicked.connect(self._elevate)
        row.addWidget(elev)
        perm.add_layout(row)
        lay.addWidget(perm)

        general = SectionCard("常规")
        from .tray import is_autorun_enabled, set_autorun
        self.autorunCb = QCheckBox("开机自动启动（最小化到托盘，守护后台运行）")
        self.autorunCb.setChecked(is_autorun_enabled())
        self.autorunCb.toggled.connect(lambda on: set_autorun(on))
        general.add(self.autorunCb)
        lay.addWidget(general)

        kill = SectionCard("后台清理进程列表", "内存守护达阈值时会结束这些进程（逗号分隔）")
        from ..core.booster import load_kill_list, save_kill_list
        self.killEdit = QLineEdit(", ".join(load_kill_list()))
        kill.add(self.killEdit)
        kill.add_layout(button_row(_mkbtn("保存进程列表", "secondary", self._save_kill), stretch=False))
        lay.addWidget(kill)
        lay.addStretch()

        about = QLabel(
            f"YunZeHui 云泽汇优化 v{__version__}<br>"
            "开源学习项目 · MIT License · <a href='https://github.com/YZ-Xiaobei/YunZeHui'>GitHub 仓库</a><br>"
            "功能思路参考 Atlas-OS / optimizer / Winhance / ISLC 等开源项目，代码全部自主实现。<br>"
            "关闭窗口最小化到托盘；托盘右键可退出。")
        about.setObjectName("muted")
        about.setWordWrap(True)
        about.setOpenExternalLinks(True)
        lay.addWidget(about)

    def on_show(self):
        if admin.is_admin():
            self.adminStatus.setText("✅ 当前已是管理员")
        else:
            self.adminStatus.setText("⚠️ 普通权限，部分功能不可用")

    def _elevate(self):
        if not admin.relaunch_as_admin():
            QMessageBox.warning(self, "提权失败", "UAC 请求被拒绝或失败")

    def _save_kill(self):
        from ..core.booster import save_kill_list
        names = [x.strip() for x in self.killEdit.text().split(",") if x.strip()]
        if save_kill_list(names):
            QMessageBox.information(self, "已保存", f"进程列表已保存（{len(names)} 项）")
        else:
            QMessageBox.warning(self, "失败", "写入 kill_list.json 失败")


def _mkbtn(text, cls, cb):
    b = QPushButton(text)
    if cls != "primary":
        b.setProperty("class", cls)
    b.clicked.connect(cb)
    return b
