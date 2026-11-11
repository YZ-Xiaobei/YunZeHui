"""YunZeHui 云泽汇优化 — 动态内存守护页 + 服务精简页 + Debloat 页."""
from __future__ import annotations

from PySide6.QtCore import Qt, QTimer
from PySide6.QtWidgets import (
    QCheckBox, QDoubleSpinBox, QFormLayout, QFrame, QHBoxLayout, QHeaderView,
    QLabel, QMessageBox, QPushButton, QSpinBox, QTableWidget, QTableWidgetItem,
    QVBoxLayout, QWidget,
)

from ..core import debloat, guardian, services
from .pages import run_async

CHECKED = Qt.CheckState.Checked
UNCHECKED = Qt.CheckState.Unchecked


# ================================================================ 动态内存守护

class GuardianPage(QWidget):
    def __init__(self):
        super().__init__()
        lay = QVBoxLayout(self)
        lay.setContentsMargins(24, 20, 24, 20)
        title = QLabel("动态内存守护")
        title.setProperty("class", "pageTitle")
        lay.addWidget(title)
        self.desc = QLabel(
            "后台持续监控内存水位：超过阈值自动分层清理（温和修剪工作集 → 结束后台进程 → 激进清待机列表）；"
            "检测到游戏启动时立即预清理，为游戏腾出最大可用内存。")
        self.desc.setWordWrap(True)
        lay.addWidget(self.desc)

        # ---- 状态卡
        card = QFrame()
        card.setProperty("class", "card")
        form = QFormLayout(card)
        self.statusLabel = QLabel("⛔ 未运行")
        self.statusLabel.setStyleSheet("font-size:16px; font-weight:bold; color:#ef4444;")
        form.addRow("守护状态：", self.statusLabel)
        self.memLabel = QLabel("--")
        form.addRow("当前内存：", self.memLabel)
        self.gameLabel = QLabel("未检测到游戏进程")
        form.addRow("游戏进程：", self.gameLabel)
        lay.addWidget(card)

        # ---- 参数
        cfgCard = QFrame()
        cfgCard.setProperty("class", "card")
        cfg = QFormLayout(cfgCard)
        g = guardian.load_config()
        self.threshSpin = QSpinBox()
        self.threshSpin.setRange(50, 98)
        self.threshSpin.setValue(int(g.get("threshold_percent", 85)))
        self.threshSpin.setSuffix(" %")
        cfg.addRow("触发阈值（内存占用）：", self.threshSpin)
        self.intervalSpin = QSpinBox()
        self.intervalSpin.setRange(2, 120)
        self.intervalSpin.setValue(int(g.get("interval_seconds", 10)))
        self.intervalSpin.setSuffix(" 秒")
        cfg.addRow("检查间隔：", self.intervalSpin)
        self.cooldownSpin = QSpinBox()
        self.cooldownSpin.setRange(10, 600)
        self.cooldownSpin.setValue(int(g.get("cooldown_seconds", 60)))
        self.cooldownSpin.setSuffix(" 秒")
        cfg.addRow("两次清理最小间隔：", self.cooldownSpin)
        self.gameDetect = QCheckBox("游戏启动时自动预清理")
        self.gameDetect.setChecked(bool(g.get("game_detect_enabled", True)))
        cfg.addRow("", self.gameDetect)
        self.autoKill = QCheckBox("达阈值时同时结束后台进程（kill list）")
        self.autoKill.setChecked(bool(g.get("auto_kill_on_threshold", True)))
        cfg.addRow("", self.autoKill)
        self.aggressive = QCheckBox("激进模式：清理待机内存列表（需管理员，ISLC 方案）")
        self.aggressive.setChecked(bool(g.get("aggressive", False)))
        cfg.addRow("", self.aggressive)
        lay.addWidget(cfgCard)

        # ---- 按钮
        row = QHBoxLayout()
        self.startBtn = QPushButton("▶ 启动守护")
        self.startBtn.clicked.connect(self._toggle)
        self.cleanNowBtn = QPushButton("立即清理一次")
        self.cleanNowBtn.setProperty("class", "secondary")
        self.cleanNowBtn.clicked.connect(self._clean_now)
        saveBtn = QPushButton("保存设置")
        saveBtn.setProperty("class", "secondary")
        saveBtn.clicked.connect(self._save)
        row.addWidget(self.startBtn)
        row.addWidget(self.cleanNowBtn)
        row.addWidget(saveBtn)
        row.addStretch()
        lay.addLayout(row)

        # ---- 事件日志
        self.logTable = QTableWidget(0, 5)
        self.logTable.setHorizontalHeaderLabels(["时间", "触发原因", "当时内存%", "释放 MB", "修剪/结束进程"])
        self.logTable.horizontalHeader().setSectionResizeMode(1, QHeaderView.Stretch)
        lay.addWidget(self.logTable, 1)

        # 定时刷新
        self.timer = QTimer(self)
        self.timer.timeout.connect(self._refresh)
        self.timer.start(2000)
        self._start_timer_sync()

    def _start_timer_sync(self):
        g = guardian.get_guardian()
        if g.running:
            self._set_running_ui(True)

    def _set_running_ui(self, running: bool):
        if running:
            self.statusLabel.setText("🟢 守护运行中")
            self.statusLabel.setStyleSheet("font-size:16px; font-weight:bold; color:#4ade80;")
            self.startBtn.setText("⏹ 停止守护")
        else:
            self.statusLabel.setText("⛔ 未运行")
            self.statusLabel.setStyleSheet("font-size:16px; font-weight:bold; color:#ef4444;")
            self.startBtn.setText("▶ 启动守护")

    def _toggle(self):
        g = guardian.get_guardian()
        if g.running:
            g.stop_guardian()
            self._set_running_ui(False)
        else:
            self._save()
            g.start_guardian()
            self._set_running_ui(True)

    def _save(self):
        cfg = {
            "enabled": guardian.get_guardian().running,
            "threshold_percent": self.threshSpin.value(),
            "interval_seconds": self.intervalSpin.value(),
            "cooldown_seconds": self.cooldownSpin.value(),
            "game_detect_enabled": self.gameDetect.isChecked(),
            "auto_kill_on_threshold": self.autoKill.isChecked(),
            "aggressive": self.aggressive.isChecked(),
        }
        guardian.save_config(cfg)
        guardian.get_guardian().update_config()

    def _clean_now(self):
        run_async(self, lambda **kw: guardian.get_guardian().trigger_manual(),
                  self._clean_done, on_fail=lambda m: QMessageBox.warning(self, "失败", m))

    def _clean_done(self, ev):
        if ev:
            QMessageBox.information(
                self, "清理完成",
                f"释放约 {ev.freed_mb:.0f} MB | 修剪 {ev.trimmed} 个进程 | 结束 {ev.killed} 个后台进程")
            self._refresh()

    def _refresh(self):
        import psutil
        try:
            vm = psutil.virtual_memory()
            self.memLabel.setText(
                f"{vm.available / (1 << 30):.1f} GB 可用 / 共 {vm.total / (1 << 30):.1f} GB（占用 {vm.percent}%）")
            if vm.percent >= self.threshSpin.value():
                self.memLabel.setStyleSheet("color:#ef4444; font-weight:bold;")
            else:
                self.memLabel.setStyleSheet("")
        except Exception:
            pass
        games = guardian.find_game_processes()
        self.gameLabel.setText("、".join(games) if games else "未检测到游戏进程")

        g = guardian.get_guardian()
        self.logTable.setRowCount(0)
        for ev in reversed(g.events):
            r = self.logTable.rowCount()
            self.logTable.insertRow(r)
            self.logTable.setItem(r, 0, QTableWidgetItem(ev.time))
            reason = {"threshold": "⚡ 达到阈值", "game_start": "🎮 游戏启动", "manual": "👆 手动"}.get(ev.reason, ev.reason)
            self.logTable.setItem(r, 1, QTableWidgetItem(reason))
            self.logTable.setItem(r, 2, QTableWidgetItem(f"{ev.mem_percent:.0f}%"))
            self.logTable.setItem(r, 3, QTableWidgetItem(f"{ev.freed_mb:.0f}"))
            self.logTable.setItem(r, 4, QTableWidgetItem(f"{ev.trimmed}/{ev.killed}"))


# ================================================================ 服务精简

class ServicesPage(QWidget):
    def __init__(self):
        super().__init__()
        lay = QVBoxLayout(self)
        lay.setContentsMargins(24, 20, 24, 20)
        title = QLabel("游戏模式服务精简")
        title.setProperty("class", "pageTitle")
        lay.addWidget(title)
        self.desc = QLabel("临时禁用吃内存/CPU 的系统服务（全部自动备份，可一键还原）。禁用前会记录原始启动类型。")
        self.desc.setWordWrap(True)
        lay.addWidget(self.desc)

        self.table = QTableWidget(0, 3)
        self.table.setHorizontalHeaderLabels(["服务", "说明", "当前状态"])
        self.table.horizontalHeader().setSectionResizeMode(1, QHeaderView.Stretch)
        lay.addWidget(self.table, 1)

        row = QHBoxLayout()
        self.disableBtn = QPushButton("禁用选中服务")
        self.disableBtn.setProperty("class", "danger")
        self.disableBtn.clicked.connect(self._disable)
        restoreBtn = QPushButton("全部还原")
        restoreBtn.setProperty("class", "secondary")
        restoreBtn.clicked.connect(self._restore)
        refreshBtn = QPushButton("刷新状态")
        refreshBtn.setProperty("class", "secondary")
        refreshBtn.clicked.connect(self._refresh)
        row.addWidget(self.disableBtn)
        row.addWidget(restoreBtn)
        row.addWidget(refreshBtn)
        row.addStretch()
        lay.addLayout(row)

    def on_show(self):
        self._refresh()

    def _refresh(self):
        run_async(self, services.service_report, self._fill)

    def _fill(self, rows):
        self.table.setRowCount(0)
        self._rows = rows
        for r0 in rows:
            r = self.table.rowCount()
            self.table.insertRow(r)
            name_item = QTableWidgetItem(r0["name"])
            name_item.setCheckState(UNCHECKED if r0["disabled"] else CHECKED)
            self.table.setItem(r, 0, name_item)
            why = r0["why"]
            self.table.setItem(r, 1, QTableWidgetItem(f"{r0['desc']} — {why}"))
            st = "⛔ 已禁用" if r0["disabled"] else (
                "🟢 运行中" if r0["status"] == "RUNNING" else "⏸ 已停止")
            self.table.setItem(r, 2, QTableWidgetItem(st))

    def _disable(self):
        names = []
        for r in range(self.table.rowCount()):
            item = self.table.item(r, 0)
            if item.checkState() == CHECKED:
                names.append(item.text())
        if not names:
            QMessageBox.information(self, "提示", "请先勾选要禁用的服务")
            return
        run_async(self, lambda **kw: services.disable_game_services(names), self._disabled)

    def _disabled(self, ok_list):
        QMessageBox.information(self, "完成", f"已禁用 {len(ok_list)} 个服务（已备份，可还原）")
        self._refresh()

    def _restore(self):
        run_async(self, lambda **kw: services.restore_game_services(), self._restored)

    def _restored(self, n):
        QMessageBox.information(self, "还原完成", f"恢复了 {n} 个服务")
        self._refresh()


# ================================================================ Debloat

class DebloatPage(QWidget):
    def __init__(self):
        super().__init__()
        lay = QVBoxLayout(self)
        lay.setContentsMargins(24, 20, 24, 20)
        title = QLabel("预装应用清理 (Debloat)")
        title.setProperty("class", "pageTitle")
        lay.addWidget(title)
        self.desc = QLabel("扫描 Windows 预装 UWP 应用（新闻/天气/Cortana/Teams 等），卸载只影响当前用户，可通过 PowerShell 恢复。")
        self.desc.setWordWrap(True)
        lay.addWidget(self.desc)

        self.table = QTableWidget(0, 2)
        self.table.setHorizontalHeaderLabels(["应用", "包名"])
        self.table.horizontalHeader().setSectionResizeMode(0, QHeaderView.Stretch)
        self.table.horizontalHeader().setSectionResizeMode(1, QHeaderView.Stretch)
        lay.addWidget(self.table, 1)

        row = QHBoxLayout()
        scanBtn = QPushButton("扫描应用")
        scanBtn.clicked.connect(self._scan)
        self.removeBtn = QPushButton("卸载选中（仅当前用户）")
        self.removeBtn.setProperty("class", "danger")
        self.removeBtn.clicked.connect(self._remove)
        row.addWidget(scanBtn)
        row.addWidget(self.removeBtn)
        row.addStretch()
        lay.addLayout(row)
        self.status = QLabel("")
        lay.addWidget(self.status)

    def on_show(self):
        self._scan()

    def _scan(self):
        self.status.setText("扫描中…")
        run_async(self, debloat.list_uwp_apps, self._fill,
                  on_fail=lambda m: self.status.setText(f"扫描失败：{m}"))

    def _fill(self, apps):
        self.table.setRowCount(0)
        self._apps = apps
        removable_first = sorted(apps, key=lambda a: (not a["removable"], a["name"]))
        for a in removable_first:
            r = self.table.rowCount()
            self.table.insertRow(r)
            name_item = QTableWidgetItem(("🏷️ " if a["removable"] else "") + a["name"])
            name_item.setCheckState(CHECKED if a["removable"] else UNCHECKED)
            name_item.setToolTip("🏷️ = 建议可安全移除" if a["removable"] else "系统组件，不建议移除")
            self.table.setItem(r, 0, name_item)
            self.table.setItem(r, 1, QTableWidgetItem(a["package"]))
        n_rem = sum(1 for a in apps if a["removable"])
        self.status.setText(f"共 {len(apps)} 个 UWP 应用，其中 {n_rem} 个建议可移除")

    def _remove(self):
        selected = []
        for r in range(self.table.rowCount()):
            item = self.table.item(r, 0)
            if item.checkState() == CHECKED:
                pkg = self.table.item(r, 1).text()
                selected.append(pkg)
        if not selected:
            QMessageBox.information(self, "提示", "请先勾选要卸载的应用")
            return
        if QMessageBox.question(self, "确认", f"确定卸载 {len(selected)} 个应用？（仅当前用户，可恢复）") != QMessageBox.Yes:
            return
        self.removeBtn.setEnabled(False)

        def job(**kw):
            ok = [p for p in selected if debloat.remove_app(p)]
            return ok

        run_async(self, job, self._removed, on_fail=self._remove_fail)

    def _removed(self, ok_list):
        self.removeBtn.setEnabled(True)
        QMessageBox.information(self, "完成", f"成功卸载 {len(ok_list)} 个应用")
        self._scan()

    def _remove_fail(self, msg):
        self.removeBtn.setEnabled(True)
        QMessageBox.warning(self, "卸载失败", msg)
