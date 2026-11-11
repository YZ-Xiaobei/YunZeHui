"""YunZeHui 云泽汇优化 — 启动项管理（Run 键扫描/禁用/恢复）."""
from __future__ import annotations

import json
import os
from datetime import datetime

try:
    import winreg
except ImportError:
    winreg = None

RUN_LOCATIONS = [
    (winreg.HKEY_CURRENT_USER, r"Software\Microsoft\Windows\CurrentVersion\Run", "HKCU"),
    (winreg.HKEY_LOCAL_MACHINE, r"Software\Microsoft\Windows\CurrentVersion\Run", "HKLM"),
    (winreg.HKEY_CURRENT_USER, r"Software\Microsoft\Windows\CurrentVersion\RunOnce", "HKCU-Once"),
    (winreg.HKEY_LOCAL_MACHINE, r"Software\Microsoft\Windows\CurrentVersion\RunOnce", "HKLM-Once"),
]

BACKUP_FILE = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "startup_backup.json")


def list_startup_items() -> list[dict]:
    """扫描所有 Run 键，返回 [{root_label, path, name, command, enabled}]."""
    items = []
    for root, path, label in RUN_LOCATIONS:
        try:
            with winreg.OpenKey(root, path) as k:
                i = 0
                while True:
                    try:
                        name, val, _typ = winreg.EnumValue(k, i)
                        i += 1
                    except OSError:
                        break
                    # 禁用项带 "-YunZeHui-disabled" 后缀标记
                    enabled = True
                    if name.startswith("[disabled] "):
                        enabled = False
                        name = name[len("[disabled] "):]
                    items.append({
                        "root_label": label,
                        "path": path,
                        "name": name,
                        "command": str(val),
                        "enabled": enabled,
                    })
        except OSError:
            continue
    # 开始菜单启动文件夹
    for folder, label in (
        (os.path.expandvars(r"%APPDATA%\Microsoft\Windows\Start Menu\Programs\Startup"), "用户启动文件夹"),
        (r"C:\ProgramData\Microsoft\Windows\Start Menu\Programs\StartUp", "系统启动文件夹"),
    ):
        if os.path.isdir(folder):
            for f in os.listdir(folder):
                items.append({
                    "root_label": label,
                    "path": folder,
                    "name": f,
                    "command": os.path.join(folder, f),
                    "enabled": True,
                })
    return items


def disable_startup_item(root, path: str, name: str) -> bool:
    """禁用 = 把值改名加 [disabled] 前缀。"""
    try:
        with winreg.OpenKey(root, path, 0, winreg.KEY_READ | winreg.KEY_WRITE) as k:
            try:
                val, typ = winreg.QueryValueEx(k, name)
            except OSError:
                return False
            winreg.DeleteValue(k, name)
            winreg.SetValueEx(k, "[disabled] " + name, 0, typ, val)
        _backup(path, name, val)
        return True
    except OSError:
        return False


def enable_startup_item(root, path: str, name: str) -> bool:
    try:
        with winreg.OpenKey(root, path, 0, winreg.KEY_READ | winreg.KEY_WRITE) as k:
            try:
                val, typ = winreg.QueryValueEx(k, "[disabled] " + name)
            except OSError:
                return False
            winreg.DeleteValue(k, "[disabled] " + name)
            winreg.SetValueEx(k, name, 0, typ, val)
        return True
    except OSError:
        return False


def delete_startup_item(root, path: str, name: str) -> bool:
    try:
        with winreg.OpenKey(root, path, 0, winreg.KEY_WRITE) as k:
            winreg.DeleteValue(k, name)
        return True
    except OSError:
        return False


def _backup(path: str, name: str, value) -> None:
    """禁用前自动备份到 JSON，防止误操作无法恢复."""
    records = []
    try:
        with open(BACKUP_FILE, encoding="utf-8") as f:
            records = json.load(f)
    except Exception:
        pass
    records.append({"time": datetime.now().isoformat(), "path": path, "name": name,
                    "value": value})
    try:
        with open(BACKUP_FILE, "w", encoding="utf-8") as f:
            json.dump(records, f, ensure_ascii=False, indent=2)
    except Exception:
        pass


def restore_from_backup() -> int:
    """从备份文件恢复所有禁用的启动项，返回恢复条数."""
    try:
        with open(BACKUP_FILE, encoding="utf-8") as f:
            records = json.load(f)
    except Exception:
        return 0
    count = 0
    for rec in records:
        for root, _p, label in RUN_LOCATIONS:
            if rec["path"] == _p:
                try:
                    with winreg.CreateKey(root, rec["path"]) as k:
                        winreg.SetValueEx(k, rec["name"], 0, winreg.REG_SZ, rec["value"])
                    count += 1
                except OSError:
                    pass
                break
    return count
