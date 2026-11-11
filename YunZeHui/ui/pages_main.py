"""YunZeHui 云泽汇优化 — 页面：首页 / 加速 / 守护 / 清理."""
from __future__ import annotations

import psutil
from PySide6.QtCore import Qt, QTimer
from PySide6.QtWidgets import (
    QCheckBox, QGridLayout, QHBoxLayout, QLabel, QMessageBox, QProgressBar,
    QPushButton, QSpinBox, QTableWidget, QTableWidgetItem, QVBoxLayout,
)
from PySide6.QtCore import Qt as _Qt

from ..core import booster, cleaner, guardian, hardware, disk
from .base import Card, InfoCard, PageBase, SectionCard, StatCard, button_row, hsize, run_async
from .theme import C

CHECKED = _Qt.CheckState.Checked
UNCHECKED = _Qt.CheckState.Unchecked


# ================================================================ 首页

class HomePage(PageBase):
    title = "首页概览"
    subtitle = "系统实时状态一览"

    def build_content(self, lay: QVBoxLayout):
        grid = QGridLayout()
        grid.setSpacing(12)
        self.cpuCard = StatCard("🧠", "CPU 使用率")
        self.memCard = StatCard("📦", "内存使用")
        self.diskCard = StatCard("💾", "系统盘占用")
        grid.addWidget(self.cpuCard, 0, 0)
        grid.addWidget(self.memCard, 0, 1)
        grid.addWidget(self.diskCard, 0, 2)
        lay.addLayout(grid)

        self.info = InfoCard("设备信息")
        lay.addWidget(self.info)

        refresh = QPushButton("🔄 刷新状态")
        refresh.setFixedWidth(140)
        refresh.clicked.connect(self.on_show)
        lay.addWidget(refresh, 0, _Qt.AlignLeft)
        lay.addStretch()

    def on_show(self):
        run_async(self, booster.get_stats, self._fill)

    def _fill(self, st: booster.SystemStats):
        # 统计卡（更新式）
        self.cpuCard.set_value(f"{st.cpu_percent:.0f}", st.cpu_percent, unit="%")
        vm = psutil.virtual_memory()
        self.memCard.set_value(f"{vm.available / (1 << 30):.1f} GB 可用", vm.percent,
                               unit=f"/ {vm.total / (1 << 30):.0f} GB")
        try:
            d = next(d for d in disk.list_drives() if d["drive"].startswith("C"))
            self.diskCard.set_value(f"{d['percent']:.0f}", d["percent"], unit="% 已用")
        except StopIteration:
            self.diskCard.set_plain("--")

        # 信息卡（更新式，修复重复追加 bug）
        hw = hardware.get_full_report()
        self.info.set_item("设备类型", hw["device_type"])
        self.info.set_item("处理器", f"{hw['cpu']['name']}（{hw['cpu']['cores']}C/{hw['cpu']['threads']}T）")
        self.info.set_item("内存", f"{hw['memory']['total_gb']} GB（当前 {vm.percent}%）")
        self.info.set_item("显卡", " / ".join(g["name"] for g in hw["gpus"]) or "未知")
        self.info.set_item("操作系统", f"{hw['os']['system']} · {hw['os']['machine']}")
        self.info.set_item("电源计划", st.power_plan)
        self.info.set_item("游戏模式", "开" if st.game_mode else ("关" if st.game_mode is not None else "未设置"))
        self.info.set_item("进程数", str(st.processes))


# ================================================================ 游戏加速

class BoostPage(PageBase):
    title = "游戏加速"
    subtitle = "一键切换高性能电源计划、清理内存与后台进程、开启游戏模式、关闭 Game DVR"

    def build_content(self, lay: QVBoxLayout):
        # 当前状态（更新式，刷新不会追加行）
        self.stateCard = InfoCard("当前状态")
        lay.addWidget(self.stateCard)

        card = SectionCard("加速选项")
        self.aggressive = QCheckBox("激进模式 — 额外清理待机内存列表（ISLC 方案，需管理员）")
        card.add(self.aggressive)
        lay.addWidget(card)

        actions = Card()
        aly = QHBoxLayout(actions)
        aly.setContentsMargins(16, 14, 16, 14)
        self.boostBtn = QPushButton("🚀 一键加速")
        self.boostBtn.setFixedHeight(38)
        self.boostBtn.clicked.connect(self._boost)
        restoreBtn = QPushButton("还原常规设置")
        restoreBtn.setProperty("class", "secondary")
        restoreBtn.clicked.connect(self._restore)
        refreshBtn = QPushButton("🔄 刷新状态")
        refreshBtn.setProperty("class", "secondary")
        refreshBtn.clicked.connect(self.on_show)
        aly.addWidget(self.boostBtn)
        aly.addWidget(restoreBtn)
        aly.addWidget(refreshBtn)
        aly.addStretch()
        lay.addWidget(actions)

        self.resultCard = SectionCard("执行结果")
        self.result = QLabel("尚未执行")
        self.result.setObjectName("muted")
        self.result.setWordWrap(True)
        self.resultCard.add(self.result)
        lay.addWidget(self.resultCard)
        lay.addStretch()

    def on_show(self):
        run_async(self, booster.get_stats, self._fill_state)

    def _fill_state(self, st: booster.SystemStats):
        dvr = booster.is_game_dvr_on()
        hags = booster.is_hags_on()
        gm = st.game_mode
        self.stateCard.set_item("电源计划", st.power_plan)
        self.stateCard.set_item("游戏模式", "开" if gm else ("关" if gm is not None else "未设置"))
        self.stateCard.set_item("Game DVR", "开" if dvr else ("已关闭" if dvr is not None else "未设置"))
        self.stateCard.set_item("硬件加速 GPU 计划", "开" if hags else ("关" if hags is not None else "未设置"))
        self.stateCard.set_item("定时器精度", "0.5 ms（已优化）" if st.timer_ok else "系统默认")
        self.stateCard.set_item("后台进程数", str(st.processes))

    def _boost(self):
        self.boostBtn.setEnabled(False)
        aggressive = self.aggressive.isChecked()
        self.result.setText("加速中…")
        run_async(self, lambda **kw: booster.boost_full(aggressive=aggressive),
                  self._boost_done, on_fail=self._fail)

    def _boost_done(self, r: dict):
        self.boostBtn.setEnabled(True)
        mem = r.get("memory") or {}
        plan = r.get("power_plan") or ""
        plan_txt = f"{plan[:8]}…" if plan else "未切换（需管理员）"
        self.result.setObjectName("infoVal")
        # 改 objectName 后必须重新 polish，否则 QSS 不生效
        self.result.style().unpolish(self.result)
        self.result.style().polish(self.result)
        self.result.setText(
            f"✅ 电源计划 {plan_txt} · 修剪 {mem.get('trimmed', 0)} 进程 · "
            f"结束 {len(r.get('killed', []))} 后台 · 游戏模式 {'✓' if r['game_mode'] else '✗'} · "
            f"定时器 {'✓' if r['timer'] else '✗'} · 关 DVR {'✓' if r['game_dvr'] else '✗'}")
        self.on_show()

    def _restore(self):
        self.boostBtn.setEnabled(False)
        run_async(self, booster.boost_restore, self._restore_done, on_fail=self._fail)

    def _restore_done(self, r: dict):
        self.boostBtn.setEnabled(True)
        self.result.setText("已还原：定时器 / GameDVR / 电源计划 → 常规状态")
        self.on_show()

    def _fail(self, msg):
        self.boostBtn.setEnabled(True)
        QMessageBox.warning(self, "加速失败", msg)


# ================================================================ 内存守护

class GuardianPage(PageBase):
    title = "动态内存守护"
    subtitle = "后台监控内存水位：超阈值自动分层清理，检测到游戏启动时预清理（ISLC 方案）"

    def build_content(self, lay: QVBoxLayout):
        # 状态行
        statusCard = Card()
        sly = QHBoxLayout(statusCard)
        sly.setContentsMargins(16, 14, 16, 14)
        self.statusLbl = QLabel("⛔ 守护未运行")
        self.statusLbl.setStyleSheet(f"font-size:16px; font-weight:800; color:{C['danger']};")
        sly.addWidget(self.statusLbl)
        sly.addStretch()
        self.memLbl = QLabel("--")
        self.memLbl.setObjectName("infoVal")
        sly.addWidget(self.memLbl)
        self.startBtn = QPushButton("▶ 启动守护")
        self.startBtn.setFixedHeight(34)
        self.startBtn.clicked.connect(self._toggle)
        sly.addWidget(self.startBtn)
        lay.addWidget(statusCard)

        # 参数
        cfg = SectionCard("触发参数")
        form = QGridLayout()
        form.setHorizontalSpacing(16)
        form.setVerticalSpacing(8)
        g = guardian.load_config()
        self.thresh = QSpinBox()
        self.thresh.setRange(50, 98)
        self.thresh.setValue(int(g.get("threshold_percent", 85)))
        self.thresh.setSuffix(" %")
        self.interval = QSpinBox()
        self.interval.setRange(2, 120)
        self.interval.setValue(int(g.get("interval_seconds", 10)))
        self.interval.setSuffix(" 秒")
        self.cooldown = QSpinBox()
        self.cooldown.setRange(10, 600)
        self.cooldown.setValue(int(g.get("cooldown_seconds", 60)))
        self.cooldown.setSuffix(" 秒")
        for r, (lbl, w) in enumerate((("内存占用阈值", self.thresh),
                                      ("检查间隔", self.interval),
                                      ("两次清理最小间隔", self.cooldown))):
            form.addWidget(QLabel(lbl), r, 0)
            form.addWidget(w, r, 1)
        form.setColumnStretch(2, 1)
        cfg.add_layout(form)
        self.gameDetect = QCheckBox("游戏启动时自动预清理")
        self.gameDetect.setChecked(bool(g.get("game_detect_enabled", True)))
        self.autoKill = QCheckBox("达阈值时同时结束后台进程（kill list）")
        self.autoKill.setChecked(bool(g.get("auto_kill_on_threshold", True)))
        self.aggressive = QCheckBox("激进模式：清理待机内存列表（需管理员）")
        self.aggressive.setChecked(bool(g.get("aggressive", False)))
        cfg.add(self.gameDetect)
        cfg.add(self.autoKill)
        cfg.add(self.aggressive)
        row = button_row(
            _mkbtn("保存设置", "secondary", self._save),
            _mkbtn("立即清理一次", "flat", self._clean_now),
        )
        cfg.add_layout(row)
        lay.addWidget(cfg)

        # 游戏检测
        self.gameCard = SectionCard("游戏进程")
        self.gameLbl = QLabel("未检测到游戏进程")
        self.gameLbl.setObjectName("muted")
        self.gameCard.add(self.gameLbl)
        lay.addWidget(self.gameCard)

        # 事件日志
        logCard = SectionCard("清理记录")
        self.logTable = QTableWidget(0, 5)
        self.logTable.setHorizontalHeaderLabels(["时间", "触发", "内存%", "释放 MB", "修剪/结束"])
        self.logTable.horizontalHeader().setStretchLastSection(True)
        self.logTable.setColumnWidth(0, 90)
        self.logTable.setColumnWidth(1, 130)
        self.logTable.setColumnWidth(2, 80)
        self.logTable.setColumnWidth(3, 90)
        self.logTable.setMinimumHeight(180)
        logCard.add(self.logTable)
        lay.addWidget(logCard, 1)

        self.timer = QTimer(self)
        self.timer.timeout.connect(self._refresh)
        self.timer.start(2000)

    def _toggle(self):
        g = guardian.get_guardian()
        if g.running:
            g.stop_guardian()
            self._save()
        else:
            self._save()
            g.start_guardian()
        self._refresh()

    def _save(self):
        guardian.save_config({
            "enabled": guardian.get_guardian().running,
            "threshold_percent": self.thresh.value(),
            "interval_seconds": self.interval.value(),
            "cooldown_seconds": self.cooldown.value(),
            "game_detect_enabled": self.gameDetect.isChecked(),
            "auto_kill_on_threshold": self.autoKill.isChecked(),
            "aggressive": self.aggressive.isChecked(),
        })
        guardian.get_guardian().update_config()

    def _clean_now(self):
        run_async(self, lambda **kw: guardian.get_guardian().trigger_manual(),
                  self._clean_done, on_fail=lambda m: QMessageBox.warning(self, "失败", m))

    def _clean_done(self, ev):
        if ev:
            QMessageBox.information(self, "清理完成",
                                    f"释放约 {ev.freed_mb:.0f} MB · 修剪 {ev.trimmed} · 结束 {ev.killed} 个后台进程")
            self._refresh()

    def _refresh(self):
        g = guardian.get_guardian()
        running = g.running
        if running:
            self.statusLbl.setText("🟢 守护运行中")
            self.statusLbl.setStyleSheet(f"font-size:16px; font-weight:800; color:{C['ok']};")
            self.startBtn.setText("⏹ 停止守护")
        else:
            self.statusLbl.setText("⛔ 守护未运行")
            self.statusLbl.setStyleSheet(f"font-size:16px; font-weight:800; color:{C['danger']};")
            self.startBtn.setText("▶ 启动守护")
        try:
            vm = psutil.virtual_memory()
            self.memLbl.setText(
                f"{vm.available / (1 << 30):.1f} GB 可用 / {vm.total / (1 << 30):.1f} GB（{vm.percent}%）")
        except Exception:
            pass
        games = guardian.find_game_processes()
        self.gameLbl.setText("、".join(games) if games else "未检测到游戏进程")

        # 事件表重建（固定 5 列，不追加）
        self.logTable.setRowCount(0)
        for ev in reversed(g.events):
            r = self.logTable.rowCount()
            self.logTable.insertRow(r)
            self.logTable.setItem(r, 0, QTableWidgetItem(ev.time))
            self.logTable.setItem(r, 1, QTableWidgetItem(
                {"threshold": "⚡ 达阈值", "game_start": "🎮 游戏启动", "manual": "👆 手动"}.get(ev.reason, ev.reason)))
            self.logTable.setItem(r, 2, QTableWidgetItem(f"{ev.mem_percent:.0f}%"))
            self.logTable.setItem(r, 3, QTableWidgetItem(f"{ev.freed_mb:.0f}"))
            self.logTable.setItem(r, 4, QTableWidgetItem(f"{ev.trimmed} / {ev.killed}"))


def _mkbtn(text: str, cls: str, cb):
    b = QPushButton(text)
    b.setProperty("class", cls)
    b.clicked.connect(cb)
    return b


# ================================================================ 垃圾清理

class CleanPage(PageBase):
    title = "垃圾清理"
    subtitle = "扫描 → 勾选 → 清理，14 类系统垃圾"

    def build_content(self, lay: QVBoxLayout):
        self.table = QTableWidget(0, 3)
        self.table.setHorizontalHeaderLabels(["清理项", "文件数", "大小"])
        self.table.horizontalHeader().setStretchLastSection(True)
        self.table.setColumnWidth(0, 320)
        self.table.setColumnWidth(1, 110)
        self.table.setMinimumHeight(300)
        lay.addWidget(self.table, 1)

        self.totalLbl = QLabel("共可释放：--")
        self.totalLbl.setObjectName("infoVal")
        lay.addWidget(self.totalLbl)

        self.scanBtn = QPushButton("🔄 重新扫描")
        self.scanBtn.setProperty("class", "secondary")
        self.scanBtn.clicked.connect(self._scan)
        self.cleanBtn = QPushButton("🧹 清理选中项")
        self.cleanBtn.setProperty("class", "danger")
        self.cleanBtn.clicked.connect(self._clean)
        lay.addLayout(button_row(self.scanBtn, self.cleanBtn))

    def on_show(self):
        self._scan()

    def _scan(self):
        run_async(self, lambda **kw: cleaner.scan_junk(), self._scan_done,
                  on_fail=lambda m: QMessageBox.warning(self, "扫描失败", m))

    def _scan_done(self, rows):
        # 修复重复迭代 bug：先清空行再重建，checks 一并重建
        self.table.setRowCount(0)
        self._checks: list[tuple[int, str]] = []
        total = 0
        for row in rows:
            r = self.table.rowCount()
            self.table.insertRow(r)
            item = QTableWidgetItem(row["name"])
            item.setCheckState(CHECKED)
            self.table.setItem(r, 0, item)
            self._checks.append((r, row["name"]))
            self.table.setItem(r, 1, QTableWidgetItem(str(row["files"])))
            self.table.setItem(r, 2, QTableWidgetItem(hsize(row["bytes"])))
            total += row["bytes"]
        self.totalLbl.setText(f"共可释放：{hsize(total)}（勾选后点清理）")

    def _clean(self):
        selected = [name for r, name in getattr(self, "_checks", []) if
                    self.table.item(r, 0).checkState() == CHECKED]
        if not selected:
            QMessageBox.information(self, "提示", "请先勾选要清理的项目")
            return
        self.cleanBtn.setEnabled(False)
        run_async(self, lambda **kw: cleaner.clean_targets(selected), self._clean_done,
                  on_fail=self._clean_fail)

    def _clean_done(self, results):
        self.cleanBtn.setEnabled(True)
        freed = sum(x["freed_bytes"] for x in results)
        QMessageBox.information(self, "清理完成", f"共释放 {hsize(freed)}")
        self._scan()

    def _clean_fail(self, msg):
        self.cleanBtn.setEnabled(True)
        QMessageBox.warning(self, "清理失败", msg)
