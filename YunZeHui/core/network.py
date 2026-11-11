"""YunZeHui 云泽汇优化 — 网络优化（TCP 参数调优）."""
from __future__ import annotations

from .winreg_compat import winreg

IFACE_BASE = r"SYSTEM\CurrentControlSet\Services\Tcpip\Parameters\Interfaces"

# 这两项不是网卡级参数，而是全局多媒体调度参数，写在 SystemProfile 下。
# 之前错误的写进每个网卡接口键，写了也不生效。
SYSTEM_PROFILE = r"SOFTWARE\Microsoft\Windows NT\CurrentVersion\Multimedia\SystemProfile"

# (说明, 参数名, 推荐值, 默认值说明)
NETWORK_TWEAKS = [
    ("TCP 确认频率（减少延迟）", "TcpAckFrequency", 1, "默认 2（延迟 ACK），1 = 立即 ACK"),
    ("TCP No Delay（禁用 Nagle）", "TcpNoDelay", 1, "默认 0，1 = 禁用合并小包"),
    ("网络节流（关闭 QoS 限流）", "NetworkThrottlingIndex", 0xFFFFFFFF, "默认 10，FFFFFFFF = 禁用节流"),
    ("系统响应性", "SystemResponsiveness", 0, "默认 20，0 = 全部给前台程序"),
]

# 需要写到 SystemProfile 全局键下的参数名
_GLOBAL_TWEAKS = {"NetworkThrottlingIndex", "SystemResponsiveness"}

# 恢复默认时使用的值（Win 默认 = 有节流 10 / 响应性 20）
_DEFAULT_VALUES = {"NetworkThrottlingIndex": 10, "SystemResponsiveness": 20}


def list_interfaces() -> list[str]:
    """列出所有网卡的注册表接口 GUID."""
    out = []
    try:
        with winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, IFACE_BASE) as k:
            i = 0
            while True:
                try:
                    out.append(winreg.EnumKey(k, i))
                    i += 1
                except OSError:
                    break
    except OSError:
        pass
    return out


def apply_network_tweaks(selected: list[str] | None = None) -> dict:
    """写入优化值，返回 {参数: 写入处数}。需管理员权限。

    selected 是**参数名**列表（如 "TcpAckFrequency"），不是说明文字；
    传 None 表示全部应用。
    TcpAckFrequency/TcpNoDelay 逐网卡写；NetworkThrottlingIndex/SystemResponsiveness
    写到全局 SystemProfile 键（写网卡接口键不生效）。
    """
    ok_counts = {}
    if selected is None:
        wanted = list(NETWORK_TWEAKS)
    else:
        sel = set(selected)
        wanted = [t for t in NETWORK_TWEAKS if t[1] in sel]
    if not wanted:
        return ok_counts

    per_iface = [t for t in wanted if t[1] not in _GLOBAL_TWEAKS]
    glob = [t for t in wanted if t[1] in _GLOBAL_TWEAKS]

    if per_iface:
        for guid in list_interfaces():
            path = IFACE_BASE + "\\" + guid
            for _desc, name, value, _d in per_iface:
                try:
                    with winreg.CreateKey(winreg.HKEY_LOCAL_MACHINE, path) as k:
                        winreg.SetValueEx(k, name, 0, winreg.REG_DWORD, value)
                    ok_counts[name] = ok_counts.get(name, 0) + 1
                except OSError:
                    continue

    if glob:
        for _desc, name, value, _d in glob:
            try:
                with winreg.CreateKey(winreg.HKEY_LOCAL_MACHINE, SYSTEM_PROFILE) as k:
                    winreg.SetValueEx(k, name, 0, winreg.REG_DWORD, value)
                ok_counts[name] = ok_counts.get(name, 0) + 1
            except OSError:
                continue

    return ok_counts


def restore_network_defaults() -> bool:
    """把优化值恢复成 Windows 默认；返回 False 表示有项目恢复失败。"""
    ok = True
    # 网卡级：删除自定义值（不存在即视为默认）
    for guid in list_interfaces():
        path = IFACE_BASE + "\\" + guid
        try:
            k = winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, path, 0, winreg.KEY_WRITE)
        except OSError:
            continue
        for _desc, name, _v, _d in NETWORK_TWEAKS:
            if name in _GLOBAL_TWEAKS:
                continue
            try:
                winreg.DeleteValue(k, name)
            except FileNotFoundError:
                pass
            except OSError:
                ok = False
        try:
            k.Close()
        except OSError:
            pass
    # 全局：写回 Windows 默认值（不是删除，这两个键系统本来就有）
    try:
        with winreg.CreateKey(winreg.HKEY_LOCAL_MACHINE, SYSTEM_PROFILE) as k:
            for name, val in _DEFAULT_VALUES.items():
                winreg.SetValueEx(k, name, 0, winreg.REG_DWORD, val)
    except OSError:
        ok = False
    return ok


def flush_dns() -> bool:
    import subprocess
    try:
        p = subprocess.run(["ipconfig", "/flushdns"], capture_output=True, timeout=15,
                           creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
        return p.returncode == 0
    except Exception:
        return False
