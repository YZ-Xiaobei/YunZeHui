"""YunZeHui 云泽汇优化 — 网络优化（TCP 参数调优）."""
from __future__ import annotations

try:
    import winreg
except ImportError:
    winreg = None

IFACE_BASE = r"SYSTEM\CurrentControlSet\Services\Tcpip\Parameters\Interfaces"

# (说明, 参数名, 推荐值, 默认值说明)
NETWORK_TWEAKS = [
    ("TCP 确认频率（减少延迟）", "TcpAckFrequency", 1, "默认 2（延迟 ACK），1 = 立即 ACK"),
    ("TCP No Delay（禁用 Nagle）", "TcpNoDelay", 1, "默认 0，1 = 禁用合并小包"),
    ("网络节流（关闭 QoS 限流）", "NetworkThrottlingIndex", 0xFFFFFFFF, "默认 10，FFFFFFFF = 禁用节流"),
    ("系统响应性", "SystemResponsiveness", 0, "默认 20，0 = 全部给前台程序"),
]


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
    """对每个网卡接口写入优化值，返回 {参数: 成功数}。需管理员权限。"""
    ok_counts = {}
    wanted = NETWORK_TWEAKS if selected is None else [t for t in NETWORK_TWEAKS if t[0] in selected]
    for guid in list_interfaces():
        path = IFACE_BASE + "\\" + guid
        for _desc, name, value, _d in wanted:
            try:
                with winreg.CreateKey(winreg.HKEY_LOCAL_MACHINE, path) as k:
                    winreg.SetValueEx(k, name, 0, winreg.REG_DWORD, value)
                ok_counts[name] = ok_counts.get(name, 0) + 1
            except OSError:
                continue
    return ok_counts


def restore_network_defaults() -> bool:
    """删除自定义的优化值，回到系统默认。"""
    ok = True
    for guid in list_interfaces():
        path = IFACE_BASE + "\\" + guid
        for _desc, name, _v, _d in NETWORK_TWEAKS:
            try:
                with winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, path, 0, winreg.KEY_WRITE) as k:
                    winreg.DeleteValue(k, name)
            except OSError:
                continue  # 值不存在也算恢复成功
    return ok


def flush_dns() -> bool:
    import subprocess
    try:
        p = subprocess.run(["ipconfig", "/flushdns"], capture_output=True, timeout=15,
                           creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
        return p.returncode == 0
    except Exception:
        return False
