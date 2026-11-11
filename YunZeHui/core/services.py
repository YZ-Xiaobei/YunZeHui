"""YunZeHui 云泽汇优化 — 游戏模式服务精简（可逆）."""
from __future__ import annotations

import json
import os
import subprocess
from datetime import datetime

CREATE_NO_WINDOW = getattr(subprocess, "CREATE_NO_WINDOW", 0)

BACKUP_FILE = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "services_backup.json")

# (服务名, 说明, 为什么禁用)
GAME_SERVICES = [
    ("SysMain", "SysMain (Superfetch) 预读取", "机械盘上频繁预读抢 IO，12G 内存机器会占用大量内存做缓存"),
    ("DiagTrack", "诊断跟踪 (遥测)", "微软遥测服务，持续占用 CPU/网络"),
    ("WSearch", "Windows 搜索索引", "索引时大量读写磁盘"),
    ("Spooler", "打印服务", "不打印时可禁用"),
    ("Fax", "传真服务", "基本没人用"),
    ("WerSvc", "错误报告服务", "收集并发送崩溃报告"),
    ("dmwappushservice", "设备管理无线应用", "遥测通道"),
    ("MapsBroker", "地图管理器", "下载地图数据"),
    ("XblAuthManager", "Xbox live 授权", "不玩微软商店游戏可关"),
    ("XblGameSave", "Xbox 存档同步", "同上"),
]


def _sc(args: list[str], timeout: int = 20) -> tuple[int, str]:
    try:
        p = subprocess.run(["sc.exe"] + args, capture_output=True, timeout=timeout,
                           creationflags=CREATE_NO_WINDOW)
        out = p.stdout.decode("gbk", errors="replace") + p.stderr.decode("gbk", errors="replace")
        return p.returncode, out
    except Exception as e:
        return -1, str(e)


def get_service_status(name: str) -> str:
    """返回 RUNNING / STOPPED / DISABLED / UNKNOWN."""
    rc, out = _sc(["query", name])
    if rc != 0:
        return "UNKNOWN"
    if "STOPPED" in out.upper():
        return "STOPPED"
    if "RUNNING" in out.upper():
        return "RUNNING"
    return "UNKNOWN"


def is_service_disabled(name: str) -> bool:
    rc, out = _sc(["qc", name])
    return rc == 0 and "DISABLED" in out.upper()


def disable_service(name: str) -> bool:
    """备份当前状态 → 停止 → 禁用。"""
    status = get_service_status(name)
    _backup_service(name, status)
    if status == "RUNNING":
        _sc(["stop", name])
    rc, _ = _sc(["config", name, "start=", "disabled"])
    return rc == 0


def restore_service(name: str) -> bool:
    """按备份恢复服务启动类型（demand/auto），并启动。"""
    start_type = _load_backup_start(name)
    target = start_type if start_type in ("demand", "auto", "delayed-auto") else "demand"
    rc, _ = _sc(["config", name, "start=", target])
    if rc != 0:
        return False
    _sc(["start", name])
    return True


def _backup_service(name: str, status: str) -> None:
    records = {}
    try:
        with open(BACKUP_FILE, encoding="utf-8") as f:
            records = json.load(f)
    except Exception:
        pass
    rc, out = _sc(["qc", name])
    start_type = "demand"
    if rc == 0:
        for line in out.splitlines():
            if "START_TYPE" in line.upper():
                if "AUTO_START" in line.upper():
                    start_type = "delayed-auto" if "DELAYED" in line.upper() else "auto"
                elif "DEMAND_START" in line.upper():
                    start_type = "demand"
                elif "DISABLED" in line.upper():
                    start_type = "disabled"
                break
    records[name] = {"time": datetime.now().isoformat(), "status": status, "start_type": start_type}
    try:
        with open(BACKUP_FILE, "w", encoding="utf-8") as f:
            json.dump(records, f, ensure_ascii=False, indent=2)
    except Exception:
        pass


def _load_backup_start(name: str) -> str | None:
    try:
        with open(BACKUP_FILE, encoding="utf-8") as f:
            return json.load(f).get(name, {}).get("start_type")
    except Exception:
        return None


def disable_game_services(names: list[str] | None = None) -> list[str]:
    """禁用一批服务，返回成功的名字。"""
    ok = []
    for svc, _desc, _why in GAME_SERVICES:
        if names is not None and svc not in names:
            continue
        if disable_service(svc):
            ok.append(svc)
    return ok


def restore_game_services() -> int:
    """恢复所有禁用过的服务，返回恢复条数。"""
    try:
        with open(BACKUP_FILE, encoding="utf-8") as f:
            records = json.load(f)
    except Exception:
        return 0
    count = 0
    for name in records:
        if restore_service(name):
            count += 1
    return count


def service_report() -> list[dict]:
    """所有 GAME_SERVICES 的当前状态表。"""
    out = []
    for svc, desc, why in GAME_SERVICES:
        rc, qc = _sc(["qc", svc])
        disabled = rc == 0 and "DISABLED" in qc.upper()
        out.append({
            "name": svc, "desc": desc, "why": why,
            "status": get_service_status(svc),
            "disabled": disabled,
        })
    return out
