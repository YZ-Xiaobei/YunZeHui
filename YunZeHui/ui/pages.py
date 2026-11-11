"""YunZeHui 云泽汇优化 — 各功能页面."""
from __future__ import annotations

from PySide6.QtCore import Qt, QThread, Signal
from PySide6.QtWidgets import (
    QCheckBox, QFileDialog, QFormLayout, QFrame, QGridLayout, QHBoxLayout,
    QHeaderView, QLabel, QLineEdit, QMessageBox, QProgressBar, QPushButton,
    QScrollArea, QTableWidget, QTableWidgetItem, QVBoxLayout, QWidget,
)

from ..core import admin, booster, cleaner, diagnostics, disk, games, hardware, network, startup
from .widgets import StatCard, human_size

# ================================================================ 工作线程

class Worker(QThread):
    """通用后台任务线程：fn() 在子线程执行，结果经 done 信号返回。"""
    done = Signal(object)
    failed = Signal(str)
    progress = Signal(str)

    def __init__(self, fn, *args, **kwargs):
        super().__init__()
        self.fn = fn
        self.args = args
        self.kwargs = kwargs

    def run(self):
        try:
            import inspect
            # 只给真正接受 progress 参数的函数传入 progress，避免 TypeError
            kwargs = dict(self.kwargs)
            kwargs.pop("progress_cb", None)
            if self.kwargs.get("progress_cb") is not None:
                try:
                    sig = inspect.signature(self.fn)
                    if "progress" in sig.parameters or any(
                        p.kind == inspect.Parameter.VAR_KEYWORD
                        for p in sig.parameters.values()
                    ):
                        kwargs["progress"] = self.kwargs["progress_cb"]
                except (ValueError, TypeError):
                    pass
            result = self.fn(*self.args, **kwargs)
            self.done.emit(result)
        except Exception as e:
            self.failed.emit(f"{type(e).__name__}: {e}")


def run_async(page: QWidget, fn, on_done, on_fail=None, progress=None):
    """在页面上启动后台任务，自动防重复。"""
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
            QMessageBox.warning(page, "出错了", msg)

    w.done.connect(_done)
    w.failed.connect(_fail)
    if progress:
        w.progress.connect(progress)
    w.start()


# ================================================================ 首页

class HomePage(QWidget):
    def __init__(self):
        super().__init__()
        lay = QVBoxLayout(self)
        lay.setContentsMargins(24, 20, 24, 20)
        title = QLabel("首页概览")
        title.setProperty("class", "pageTitle")
        lay.addWidget(title)

        grid = QGridLayout()
        self.cpuCard = StatCard("CPU 使用率", "🧠")
        self.memCard = StatCard("内存使用", "📦")
        self.diskCard = StatCard("系统盘占用", "💾")
        grid.addWidget(self.cpuCard, 0, 0)
        grid.addWidget(self.memCard, 0, 1)
        grid.addWidget(self.diskCard, 0, 2)
        lay.addLayout(grid)

        infoCard = QFrame()
        infoCard.setProperty("class", "card")
        self.infoForm = QFormLayout(infoCard)
        lay.addWidget(infoCard)
        lay.addStretch()

        refresh = QPushButton("刷新状态")
        refresh.clicked.connect(self.on_show)
        lay.addWidget(refresh)

    def on_show(self):
        run_async(self, booster.get_stats, self._fill)

    def _fill(self, st: booster.SystemStats):
        self.cpuCard.set_value(f"{st.cpu_percent:.0f}%", st.cpu_percent)
        self.memCard.set_value(
            f"{st.mem_used / (1 << 30):.1f} / {st.mem_total / (1 << 30):.1f} GB", st.mem_percent)
        hw = hardware.get_full_report()
        sys_drive = next((d for d in disk.list_drives() if d["drive"].startswith("C")), None)
        if sys_drive:
            self.diskCard.set_value(f"{sys_drive['percent']:.0f}%", sys_drive["percent"])
        self._set_info("设备类型", hw["device_type"])
        self._set_info("处理器", hw["cpu"]["name"])
        self._set_info("内存", f"{hw['memory']['total_gb']} GB")
        self._set_info("显卡", " / ".join(g["name"] for g in hw["gpus"]) or "未知")
        self._set_info("系统", f"{hw['os']['system']} ({hw['os']['machine']})")
        self._set_info("当前电源计划", st.power_plan)
        self._set_info("游戏模式", "开" if st.game_mode else ("关" if st.game_mode is not None else "未设置"))

    def _set_info(self, k, v):
        self.infoForm.addRow(QLabel(f"<b>{k}</b>"), QLabel(str(v)))


# ================================================================ 游戏加速

class BoostPage(QWidget):
    def __init__(self):
        super().__init__()
        lay = QVBoxLayout(self)
        lay.setContentsMargins(24, 20, 24, 20)
        title = QLabel("游戏加速")
        title.setProperty("class", "pageTitle")
        lay.addWidget(title)
        self.desc = QLabel("一键优化电源计划、清理内存与后台进程、开启游戏模式、关闭 Game DVR。")
        lay.addWidget(self.desc)

        self.aggressive = QCheckBox("激进模式（额外清理待机内存，需管理员）")
        lay.addWidget(self.aggressive)

        btnRow = QHBoxLayout()
        self.boostBtn = QPushButton("🚀 一键加速")
        self.boostBtn.clicked.connect(self._boost)
        restoreBtn = QPushButton("还原设置")
        restoreBtn.setProperty("class", "secondary")
        restoreBtn.clicked.connect(self._restore)
        btnRow.addWidget(self.boostBtn)
        btnRow.addWidget(restoreBtn)
        btnRow.addStretch()
        lay.addLayout(btnRow)

        self.result = QLabel("")
        self.result.setWordWrap(True)
        lay.addWidget(self.result)
        lay.addStretch()

    def _boost(self):
        self.boostBtn.setEnabled(False)
        aggressive = self.aggressive.isChecked()

        def job(**kw):
            return booster.boost_full(aggressive=aggressive)

        run_async(self, job, self._boost_done, on_fail=self._fail)

    def _boost_done(self, r: dict):
        self.boostBtn.setEnabled(True)
        mem = r.get("memory") or {}
        self.result.setText(
            f"✅ 完成！电源计划：{r['power_plan'][:8]}… | 修剪进程 {mem.get('trimmed', 0)} 个 | "
            f"结束后台 {len(r.get('killed', []))} 个 | 游戏模式 {'✓' if r['game_mode'] else '✗'} | "
            f"定时器 {'✓' if r['timer'] else '✗'} | 关 DVR {'✓' if r['game_dvr'] else '✗'}")

    def _restore(self):
        self.boostBtn.setEnabled(False)
        run_async(self, booster.boost_restore, self._restore_done, on_fail=self._fail)

    def _restore_done(self, r: dict):
        self.boostBtn.setEnabled(True)
        self.result.setText("已还原：定时器/GameDVR/电源计划 → 常规状态")

    def _fail(self, msg):
        self.boostBtn.setEnabled(True)
        QMessageBox.warning(self, "加速失败", msg)


# ================================================================ 垃圾清理

class CleanPage(QWidget):
    def __init__(self):
        super().__init__()
        lay = QVBoxLayout(self)
        lay.setContentsMargins(24, 20, 24, 20)
        title = QLabel("垃圾清理")
        title.setProperty("class", "pageTitle")
        lay.addWidget(title)

        self.checks = []
        self.table = QTableWidget(0, 3)
        self.table.setHorizontalHeaderLabels(["清理项", "文件数", "大小"])
        self.table.horizontalHeader().setSectionResizeMode(0, QHeaderView.Stretch)
        self.table.setSelectionBehavior(QTableWidget.SelectRows)
        lay.addWidget(self.table)

        btnRow = QHBoxLayout()
        scanBtn = QPushButton("扫描")
        scanBtn.clicked.connect(self._scan)
        self.cleanBtn = QPushButton("🧹 清理选中项")
        self.cleanBtn.setProperty("class", "danger")
        self.cleanBtn.clicked.connect(self._clean)
        btnRow.addWidget(scanBtn)
        btnRow.addWidget(self.cleanBtn)
        btnRow.addStretch()
        lay.addLayout(btnRow)
        self.status = QLabel("共可释放：--")
        lay.addWidget(self.status)

    def on_show(self):
        self._scan()

    def _scan(self):
        def job(**kw):
            return cleaner.scan_junk()

        run_async(self, job, self._scan_done, on_fail=lambda m: QMessageBox.warning(self, "扫描失败", m))

    def _scan_done(self, rows):
        self.table.setRowCount(0)
        total = 0
        for row in rows:
            r = self.table.rowCount()
            self.table.insertRow(r)
            cb = QCheckBox(row["name"])
            cb.setChecked(True)
            self.checks.append((cb, row["name"]))
            self.table.setCellWidget(r, 0, cb)
            self.table.setItem(r, 1, QTableWidgetItem(str(row["files"])))
            self.table.setItem(r, 2, QTableWidgetItem(human_size(row["bytes"])))
            total += row["bytes"]
        self.status.setText(f"共可释放：{human_size(total)}（勾选后点清理）")

    def _clean(self):
        selected = [name for cb, name in self.checks if cb.isChecked()]
        if not selected:
            QMessageBox.information(self, "提示", "请先勾选要清理的项目")
            return
        self.cleanBtn.setEnabled(False)

        def job(**kw):
            return cleaner.clean_targets(selected)

        run_async(self, job, self._clean_done, on_fail=self._clean_fail)

    def _clean_done(self, results):
        self.cleanBtn.setEnabled(True)
        freed = sum(r["freed_bytes"] for r in results)
        QMessageBox.information(self, "清理完成", f"共释放 {human_size(freed)}")
        self.checks.clear()
        self._scan()

    def _clean_fail(self, msg):
        self.cleanBtn.setEnabled(True)
        QMessageBox.warning(self, "清理失败", msg)


# ================================================================ 游戏库

class GamesPage(QWidget):
    def __init__(self):
        super().__init__()
        lay = QVBoxLayout(self)
        lay.setContentsMargins(24, 20, 24, 20)
        title = QLabel("游戏库")
        title.setProperty("class", "pageTitle")
        lay.addWidget(title)
        self.table = QTableWidget(0, 3)
        self.table.setHorizontalHeaderLabels(["游戏", "状态", "路径"])
        self.table.horizontalHeader().setSectionResizeMode(2, QHeaderView.Stretch)
        lay.addWidget(self.table)
        btnRow = QPushButton("🔍 检测游戏")
        btnRow.clicked.connect(self._detect)
        lay.addWidget(btnRow)
        self.fsBtn = QPushButton("关闭所选游戏的全屏优化")
        self.fsBtn.setProperty("class", "secondary")
        self.fsBtn.clicked.connect(self._fs_opt)
        lay.addWidget(self.fsBtn)

    def on_show(self):
        self._detect()

    def _detect(self):
        run_async(self, games.detect_installed_games, self._fill,
                  on_fail=lambda m: QMessageBox.warning(self, "检测失败", m))

    def _fill(self, found):
        self.table.setRowCount(0)
        self._games = found
        for g in found:
            r = self.table.rowCount()
            self.table.insertRow(r)
            self.table.setItem(r, 0, QTableWidgetItem(g["name"]))
            self.table.setItem(r, 1, QTableWidgetItem("✅ 已安装" if g["installed"] else "未检测到"))
            self.table.setItem(r, 2, QTableWidgetItem(g.get("exe_path", "")))

    def _fs_opt(self):
        rows = {i.row() for i in self.table.selectedIndexes()}
        if not rows:
            QMessageBox.information(self, "提示", "请先在表格中选中游戏行")
            return
        ok = 0
        for r in rows:
            g = self._games[r]
            if g.get("exe_path") and games.set_fullscreen_optimized_off(g["exe_path"], True):
                ok += 1
        QMessageBox.information(self, "完成", f"已为 {ok} 个游戏关闭全屏优化（需重启游戏生效）")


# ================================================================ 启动项

class StartupPage(QWidget):
    def __init__(self):
        super().__init__()
        lay = QVBoxLayout(self)
        lay.setContentsMargins(24, 20, 24, 20)
        title = QLabel("启动项管理")
        title.setProperty("class", "pageTitle")
        lay.addWidget(title)
        self.table = QTableWidget(0, 4)
        self.table.setHorizontalHeaderLabels(["名称", "位置", "命令", "状态"])
        self.table.horizontalHeader().setSectionResizeMode(2, QHeaderView.Stretch)
        lay.addWidget(self.table)
        row = QHBoxLayout()
        enBtn = QPushButton("启用")
        enBtn.clicked.connect(lambda: self._toggle(True))
        disBtn = QPushButton("禁用")
        disBtn.setProperty("class", "secondary")
        disBtn.clicked.connect(lambda: self._toggle(False))
        restoreBtn = QPushButton("从备份恢复全部")
        restoreBtn.setProperty("class", "secondary")
        restoreBtn.clicked.connect(self._restore_all)
        row.addWidget(enBtn)
        row.addWidget(disBtn)
        row.addWidget(restoreBtn)
        row.addStretch()
        lay.addLayout(row)

    def on_show(self):
        self._refresh()

    def _refresh(self):
        self.table.setRowCount(0)
        self._items = startup.list_startup_items()
        for it in self._items:
            r = self.table.rowCount()
            self.table.insertRow(r)
            self.table.setItem(r, 0, QTableWidgetItem(it["name"]))
            self.table.setItem(r, 1, QTableWidgetItem(it["root_label"]))
            self.table.setItem(r, 2, QTableWidgetItem(it["command"]))
            self.table.setItem(r, 3, QTableWidgetItem("✅ 启用" if it["enabled"] else "⛔ 禁用"))

    def _toggle(self, enable: bool):
        rows = sorted({i.row() for i in self.table.selectedIndexes()}, reverse=True)
        if not rows:
            QMessageBox.information(self, "提示", "请先选中启动项")
            return
        ok = 0
        for r in rows:
            it = self._items[r]
            root = winreg_root(it["root_label"])
            if root is None:
                continue  # 文件夹启动项不支持此操作
            if enable and startup.enable_startup_item(root, it["path"], it["name"]):
                ok += 1
            elif not enable and startup.disable_startup_item(root, it["path"], it["name"]):
                ok += 1
        QMessageBox.information(self, "完成", f"成功处理 {ok} 项")
        self._refresh()

    def _restore_all(self):
        n = startup.restore_from_backup()
        QMessageBox.information(self, "恢复完成", f"恢复了 {n} 项")
        self._refresh()


def winreg_root(label: str):
    import winreg
    return {
        "HKCU": winreg.HKEY_CURRENT_USER,
        "HKLM": winreg.HKEY_LOCAL_MACHINE,
        "HKCU-Once": winreg.HKEY_CURRENT_USER,
        "HKLM-Once": winreg.HKEY_LOCAL_MACHINE,
    }.get(label)


# ================================================================ 网络优化

class NetworkPage(QWidget):
    def __init__(self):
        super().__init__()
        lay = QVBoxLayout(self)
        lay.setContentsMargins(24, 20, 24, 20)
        title = QLabel("网络优化")
        title.setProperty("class", "pageTitle")
        lay.addWidget(title)
        self.checks = []
        for desc, name, value, note in network.NETWORK_TWEAKS:
            cb = QCheckBox(f"{desc}（{note}）")
            cb.setChecked(True)
            cb._tweak_name = name
            lay.addWidget(cb)
            self.checks.append(cb)
        row = QHBoxLayout()
        applyBtn = QPushButton("应用优化（需管理员）")
        applyBtn.clicked.connect(self._apply)
        restoreBtn = QPushButton("恢复默认")
        restoreBtn.setProperty("class", "secondary")
        restoreBtn.clicked.connect(self._restore)
        flushBtn = QPushButton("刷新 DNS")
        flushBtn.setProperty("class", "secondary")
        flushBtn.clicked.connect(self._flush)
        row.addWidget(applyBtn)
        row.addWidget(restoreBtn)
        row.addWidget(flushBtn)
        row.addStretch()
        lay.addLayout(row)
        self.status = QLabel("")
        lay.addWidget(self.status)
        lay.addStretch()

    def _apply(self):
        selected = [cb._tweak_name for cb in self.checks if cb.isChecked()]
        run_async(self, lambda **kw: network.apply_network_tweaks(selected), self._applied)

    def _applied(self, counts):
        self.status.setText("已写入：" + ", ".join(f"{k} ×{v}" for k, v in counts.items()) +
                            "。重启网卡或电脑后生效。")

    def _restore(self):
        run_async(self, lambda **kw: network.restore_network_defaults(),
                  lambda r: self.status.setText("已恢复系统默认网络设置" if r else "恢复时出现部分错误"))

    def _flush(self):
        run_async(self, lambda **kw: network.flush_dns(),
                  lambda r: self.status.setText("DNS 缓存已刷新 ✅" if r else "刷新失败"))


# ================================================================ 磁盘分析

class DiskPage(QWidget):
    def __init__(self):
        super().__init__()
        lay = QVBoxLayout(self)
        lay.setContentsMargins(24, 20, 24, 20)
        title = QLabel("磁盘分析")
        title.setProperty("class", "pageTitle")
        lay.addWidget(title)
        self.table = QTableWidget(0, 4)
        self.table.setHorizontalHeaderLabels(["分区", "总容量", "已用", "剩余"])
        lay.addWidget(self.table)
        row = QHBoxLayout()
        self.dirInput = QLineEdit()
        self.dirInput.setPlaceholderText("输入要分析的目录，如 D:\\")
        pickBtn = QPushButton("选择…")
        pickBtn.setProperty("class", "secondary")
        pickBtn.clicked.connect(self._pick)
        anaBtn = QPushButton("分析子目录占用")
        anaBtn.clicked.connect(self._analyze)
        row.addWidget(self.dirInput, 1)
        row.addWidget(pickBtn)
        row.addWidget(anaBtn)
        lay.addLayout(row)
        self.result = QTableWidget(0, 2)
        self.result.setHorizontalHeaderLabels(["目录", "占用 GB"])
        self.result.horizontalHeader().setSectionResizeMode(0, QHeaderView.Stretch)
        lay.addWidget(self.result)

    def on_show(self):
        drives = disk.list_drives()
        self.table.setRowCount(0)
        for d in drives:
            r = self.table.rowCount()
            self.table.insertRow(r)
            self.table.setItem(r, 0, QTableWidgetItem(d["drive"]))
            self.table.setItem(r, 1, QTableWidgetItem(f"{d['total_gb']} GB"))
            self.table.setItem(r, 2, QTableWidgetItem(f"{d['used_gb']} GB ({d['percent']}%)"))
            self.table.setItem(r, 3, QTableWidgetItem(f"{d['free_gb']} GB"))

    def _pick(self):
        d = QFileDialog.getExistingDirectory(self, "选择目录")
        if d:
            self.dirInput.setText(d)

    def _analyze(self):
        path = self.dirInput.text().strip() or "C:\\"
        self.result.setRowCount(0)
        status = QLabel("分析中，可能需要几分钟…")
        lay = self.layout()
        lay.addWidget(status)

        def job(**kw):
            return disk.analyze_directory(path, depth=2, min_mb=50)

        def done(rows):
            status.setText("分析完成")
            for row in rows:
                r = self.result.rowCount()
                self.result.insertRow(r)
                self.result.setItem(r, 0, QTableWidgetItem(row["path"]))
                self.result.setItem(r, 1, QTableWidgetItem(str(row["gb"])))

        run_async(self, job, done, on_fail=lambda m: status.setText(f"失败：{m}"))


# ================================================================ 硬件信息

class HardwarePage(QWidget):
    def __init__(self):
        super().__init__()
        lay = QVBoxLayout(self)
        lay.setContentsMargins(24, 20, 24, 20)
        title = QLabel("硬件信息")
        title.setProperty("class", "pageTitle")
        lay.addWidget(title)
        self.info = QLabel("")
        self.info.setTextFormat(Qt.RichText)
        self.info.setWordWrap(True)
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        wrap = QWidget()
        wl = QVBoxLayout(wrap)
        wl.addWidget(self.info)
        wl.addStretch()
        scroll.setWidget(wrap)
        lay.addWidget(scroll)
        btn = QPushButton("生成诊断报告")
        btn.clicked.connect(self._report)
        lay.addWidget(btn)

    def on_show(self):
        run_async(self, hardware.get_full_report, self._fill)

    def _fill(self, hw):
        rows = [
            ("系统", f"{hw['os']['system']}  ({hw['os']['machine']})"),
            ("设备类型", hw["device_type"]),
            ("CPU", f"{hw['cpu']['name']} — {hw['cpu']['cores']}C/{hw['cpu']['threads']}T @ {hw['cpu']['freq_mhz']} MHz"),
            ("内存", f"{hw['memory']['used_gb']} / {hw['memory']['total_gb']} GB ({hw['memory']['percent']}%)"),
            ("显卡", "<br>".join(f"• {g['name']}" + (f"（{g['vram_mb']} MB）" if g["vram_mb"] else "") for g in hw["gpus"]) or "未检测到"),
        ]
        if hw.get("battery"):
            rows.append(("电池", f"{hw['battery']['percent']}% {'充电中' if hw['battery']['plugged'] else ''}"))
        self.info.setText("".join(f"<p><b>{k}：</b>{v}</p>" for k, v in rows))

    def _report(self):
        path, _ = QFileDialog.getSaveFileName(self, "保存诊断报告", "YunZeHui_report.txt", "文本文件 (*.txt)")
        if path and diagnostics.save_report(path):
            QMessageBox.information(self, "已保存", f"报告已保存到 {path}")


# ================================================================ 设置

class SettingsPage(QWidget):
    def __init__(self):
        super().__init__()
        lay = QVBoxLayout(self)
        lay.setContentsMargins(24, 20, 24, 20)
        title = QLabel("设置")
        title.setProperty("class", "pageTitle")
        lay.addWidget(title)

        card = QFrame()
        card.setProperty("class", "card")
        form = QFormLayout(card)
        adminRow = QHBoxLayout()
        self.adminStatus = QLabel()
        adminRow.addWidget(self.adminStatus)
        elevBtn = QPushButton("以管理员身份重启")
        elevBtn.setProperty("class", "secondary")
        elevBtn.clicked.connect(self._elevate)
        adminRow.addWidget(elevBtn)
        adminRow.addStretch()
        form.addRow("权限：", adminRow)

        # 开机自启
        from .tray import is_autorun_enabled, set_autorun
        self.autorunCb = QCheckBox("开机自动启动（最小化到托盘，守护后台运行）")
        self.autorunCb.setChecked(is_autorun_enabled())
        self.autorunCb.toggled.connect(lambda on: set_autorun(on))
        form.addRow("", self.autorunCb)

        # 后台进程 kill list 编辑
        from ..core.booster import load_kill_list, save_kill_list
        self.killEdit = QLineEdit(", ".join(load_kill_list()))
        form.addRow("后台清理进程列表（逗号分隔）：", self.killEdit)
        saveBtn = QPushButton("保存进程列表")
        saveBtn.setProperty("class", "secondary")
        saveBtn.clicked.connect(self._save_kill)
        form.addRow("", saveBtn)

        lay.addWidget(card)
        lay.addStretch()
        from .. import __version__
        about = QLabel(
            f"YunZeHui 云泽汇优化 v{__version__}<br>"
            "开源学习项目：系统优化与游戏加速工具。<br>"
            "功能参考公开逆向分析与开源方案（ISLC / Atlas-OS / Process Lasso 思路）重新实现。<br>"
            "关闭窗口会最小化到系统托盘，托盘右键可退出。")
        about.setWordWrap(True)
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
