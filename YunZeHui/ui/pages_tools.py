"""YunZeHui 云泽汇优化 — 页面：游戏库 / 启动项 / 网络 / 服务精简 / 预装清理."""
from __future__ import annotations

from PySide6.QtCore import Qt as _Qt
from PySide6.QtWidgets import (
    QCheckBox, QHBoxLayout, QLabel, QLineEdit, QMessageBox, QPushButton,
    QTableWidget, QTableWidgetItem, QVBoxLayout, QWidget,
)

from ..core import debloat, games, network, services, startup
from .base import Card, PageBase, SectionCard, button_row, run_async

CHECKED = _Qt.CheckState.Checked
UNCHECKED = _Qt.CheckState.Unchecked


# ================================================================ 游戏库

class GamesPage(PageBase):
    title = "游戏库"
    subtitle = "检测已安装游戏，一键关闭全屏优化"

    def build_content(self, lay: QVBoxLayout):
        self.table = QTableWidget(0, 3)
        self.table.setHorizontalHeaderLabels(["游戏", "状态", "路径"])
        self.table.horizontalHeader().setStretchLastSection(True)
        self.table.setColumnWidth(0, 180)
        self.table.setColumnWidth(1, 120)
        self.table.setMinimumHeight(220)
        lay.addWidget(self.table, 1)

        detect = _mkbtn("🔍 检测游戏", "secondary", self._detect)
        self.fsBtn = _mkbtn("关闭选中游戏的全屏优化", "primary", self._fs_opt)
        lay.addLayout(button_row(detect, self.fsBtn))

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
        rows = sorted({i.row() for i in self.table.selectedIndexes()})
        if not rows:
            QMessageBox.information(self, "提示", "请先在表格中选中游戏行")
            return
        ok = 0
        for r in rows:
            g = self._games[r]
            if g.get("exe_path") and games.set_fullscreen_optimized_off(g["exe_path"], True):
                ok += 1
        QMessageBox.information(self, "完成", f"已为 {ok} 个游戏关闭全屏优化（重启游戏生效）")


# ================================================================ 启动项

class StartupPage(PageBase):
    title = "启动项管理"
    subtitle = "注册表 Run 键与启动文件夹；禁用自动备份，可恢复"

    def build_content(self, lay: QVBoxLayout):
        self.table = QTableWidget(0, 4)
        self.table.setHorizontalHeaderLabels(["名称", "位置", "命令", "状态"])
        self.table.horizontalHeader().setStretchLastSection(True)
        self.table.setColumnWidth(0, 180)
        self.table.setColumnWidth(1, 90)
        self.table.setColumnWidth(2, 260)
        self.table.setMinimumHeight(300)
        lay.addWidget(self.table, 1)
        lay.addLayout(button_row(
            _mkbtn("启用", "secondary", lambda: self._toggle(True)),
            _mkbtn("禁用", "secondary", lambda: self._toggle(False)),
            _mkbtn("从备份恢复全部", "flat", self._restore_all),
        ))

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
        import winreg
        ok = 0
        for r in rows:
            it = self._items[r]
            root = {
                "HKCU": winreg.HKEY_CURRENT_USER, "HKLM": winreg.HKEY_LOCAL_MACHINE,
                "HKCU-Once": winreg.HKEY_CURRENT_USER, "HKLM-Once": winreg.HKEY_LOCAL_MACHINE,
            }.get(it["root_label"])
            if root is None:
                continue
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


# ================================================================ 网络优化

class NetworkPage(PageBase):
    title = "网络优化"
    subtitle = "TCP 参数调优（重启网卡/电脑后生效）与 DNS 刷新"

    def build_content(self, lay: QVBoxLayout):
        card = SectionCard("优化项")
        self.checks: list[tuple[QCheckBox, str]] = []
        for desc, name, _v, note in network.NETWORK_TWEAKS:
            cb = QCheckBox(f"{desc}（{note}）")
            cb.setChecked(True)
            card.add(cb)
            self.checks.append((cb, name))
        lay.addWidget(card)

        self.status = QLabel("")
        self.status.setObjectName("infoVal")
        self.status.setWordWrap(True)
        lay.addWidget(self.status)
        lay.addLayout(button_row(
            _mkbtn("应用优化（需管理员）", "primary", self._apply),
            _mkbtn("恢复默认", "secondary", self._restore),
            _mkbtn("刷新 DNS", "secondary", self._flush),
        ))
        lay.addStretch()

    def _apply(self):
        selected = [n for cb, n in self.checks if cb.isChecked()]
        if not selected:
            QMessageBox.information(self, "提示", "请至少勾选一项优化")
            return
        self.status.setText("写入中…")
        run_async(self, lambda **kw: network.apply_network_tweaks(selected), self._applied)

    def _applied(self, counts):
        if not counts:
            self.status.setText(
                "未写入任何项：可能不是管理员，或没有可用的网卡接口。"
                "请用「设置 → 以管理员身份重启」后重试。")
            return
        self.status.setText("已写入：" + ", ".join(f"{k} ×{v}" for k, v in counts.items()) +
                            "。重启网卡或电脑后生效。")

    def _restore(self):
        self.status.setText("恢复中…")
        run_async(self, lambda **kw: network.restore_network_defaults(),
                  lambda r: self.status.setText("已恢复系统默认网络设置" if r else "恢复时出现部分错误"))

    def _flush(self):
        run_async(self, lambda **kw: network.flush_dns(),
                  lambda r: self.status.setText("DNS 缓存已刷新 ✅" if r else "刷新失败"))


# ================================================================ 服务精简

class ServicesPage(PageBase):
    title = "游戏模式服务精简"
    subtitle = "临时禁用吃内存/CPU 的服务；禁用前自动备份原始启动类型，可一键还原"

    def build_content(self, lay: QVBoxLayout):
        self.table = QTableWidget(0, 3)
        self.table.setHorizontalHeaderLabels(["服务", "说明", "当前状态"])
        self.table.horizontalHeader().setStretchLastSection(True)
        self.table.setColumnWidth(0, 160)
        self.table.setColumnWidth(1, 380)
        self.table.setMinimumHeight(320)
        lay.addWidget(self.table, 1)
        lay.addLayout(button_row(
            _mkbtn("禁用选中服务", "danger", self._disable),
            _mkbtn("全部还原", "secondary", self._restore),
            _mkbtn("刷新状态", "flat", self._refresh),
        ))

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
            item = QTableWidgetItem(r0["name"])
            # 复选框 = 「要禁用的选择」，默认全部不勾，避免误点一次禁用一整批服务
            item.setCheckState(UNCHECKED)
            item.setToolTip("已禁用，可用「全部还原」恢复" if r0["disabled"]
                            else "勾选后点「禁用选中服务」")
            self.table.setItem(r, 0, item)
            self.table.setItem(r, 1, QTableWidgetItem(f"{r0['desc']} — {r0['why']}"))
            st = "⛔ 已禁用" if r0["disabled"] else (
                "🟢 运行中" if r0["status"] == "RUNNING" else "⏸ 已停止")
            self.table.setItem(r, 2, QTableWidgetItem(st))

    def _disable(self):
        names = [self.table.item(r, 0).text() for r in range(self.table.rowCount())
                 if self.table.item(r, 0).checkState() == CHECKED
                 and not self._rows[r]["disabled"]]
        if not names:
            QMessageBox.information(self, "提示", "请先勾选要禁用的服务（已禁用的无需重复勾选）")
            return
        if QMessageBox.question(
                self, "确认禁用",
                f"将临时禁用 {len(names)} 个服务：\n" + "、".join(names) +
                "\n\n原始启动类型会自动备份，可随时「全部还原」。继续？"
        ) != QMessageBox.StandardButton.Yes:
            return
        run_async(self, lambda **kw: services.disable_game_services(names),
                  self._disabled)

    def _disabled(self, ok_list):
        QMessageBox.information(self, "完成", f"已禁用 {len(ok_list)} 个服务（已备份）")
        self._refresh()

    def _restore(self):
        run_async(self, lambda **kw: services.restore_game_services(),
                  lambda n: (QMessageBox.information(self, "还原完成", f"恢复了 {n} 个服务"), self._refresh()))


# ================================================================ 预装清理

class DebloatPage(PageBase):
    title = "预装应用清理 (Debloat)"
    subtitle = "卸载仅影响当前用户；系统组件已标记，建议不动"

    def build_content(self, lay: QVBoxLayout):
        self.table = QTableWidget(0, 2)
        self.table.setHorizontalHeaderLabels(["应用（🏷️ = 建议可移除）", "包名"])
        self.table.horizontalHeader().setStretchLastSection(True)
        self.table.setColumnWidth(0, 300)
        self.table.setMinimumHeight(320)
        lay.addWidget(self.table, 1)

        self.status = QLabel("")
        self.status.setObjectName("muted")
        lay.addWidget(self.status)
        lay.addLayout(button_row(
            _mkbtn("扫描应用", "secondary", lambda: self._scan(manual=True)),
            _mkbtn("卸载选中（仅当前用户）", "danger", self._remove),
        ))

    def on_show(self):
        self._scan(manual=False)

    def _scan(self, manual: bool = False):
        self._manual_scan = manual
        self.status.setText("扫描中…")
        run_async(self, debloat.list_uwp_apps, self._fill, on_fail=self._scan_fail)

    def _scan_fail(self, msg: str):
        detail = msg.split(":", 1)[-1].strip() if ":" in msg else msg
        self.table.setRowCount(0)
        self.status.setText(f"扫描失败：{detail}（可尝试以管理员身份重启）")
        # 仅在用户主动点「扫描应用」时弹窗，避免每次切页都打断
        if getattr(self, "_manual_scan", False):
            QMessageBox.warning(
                self, "无法枚举预装应用",
                f"{detail}\n\n常见原因：\n"
                "• 当前账户被组策略/企业管控限制访问 Appx 包管理\n"
                "• AppX 部署服务（AppXSvc）被禁用\n"
                "请尝试以管理员身份重启本程序后再扫描。")

    def _fill(self, apps):
        self.table.setRowCount(0)
        self._apps = apps
        for a in sorted(apps, key=lambda x: (not x["removable"], x["name"])):
            r = self.table.rowCount()
            self.table.insertRow(r)
            item = QTableWidgetItem(("🏷️ " if a["removable"] else "") + a["name"])
            item.setCheckState(CHECKED if a["removable"] else UNCHECKED)
            self.table.setItem(r, 0, item)
            self.table.setItem(r, 1, QTableWidgetItem(a["package"]))
        n = sum(1 for a in apps if a["removable"])
        self.status.setText(f"共 {len(apps)} 个 UWP 应用，{n} 个建议可移除")

    def _remove(self):
        selected = [self.table.item(r, 1).text() for r in range(self.table.rowCount())
                    if self.table.item(r, 0).checkState() == CHECKED]
        if not selected:
            QMessageBox.information(self, "提示", "请先勾选要卸载的应用")
            return
        if QMessageBox.question(self, "确认",
                                f"确定卸载 {len(selected)} 个应用？（仅当前用户）") != QMessageBox.StandardButton.Yes:
            return
        self._remove_busy = True
        run_async(self, lambda **kw: [p for p in selected if debloat.remove_app(p)],
                  self._removed, on_fail=self._remove_fail)

    def _removed(self, ok_list):
        self._remove_busy = False
        QMessageBox.information(self, "完成", f"成功卸载 {len(ok_list)} 个应用")
        self._scan()

    def _remove_fail(self, msg):
        self._remove_busy = False
        QMessageBox.warning(self, "卸载失败", msg)


def _mkbtn(text, cls, cb):
    b = QPushButton(text)
    if cls != "primary":
        b.setProperty("class", cls)
    b.clicked.connect(cb)
    return b
