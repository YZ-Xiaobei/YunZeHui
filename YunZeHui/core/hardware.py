"""YunZeHui 云泽汇优化 — 硬件信息（CPU/内存/系统/GPU/温度）."""
from __future__ import annotations

import os
import platform

try:
    import psutil
    HAS_PSUTIL = True
except ImportError:
    HAS_PSUTIL = False

from .winreg_compat import winreg


def _read_reg(root, path: str, name: str):
    try:
        with winreg.OpenKey(root, path) as k:
            val, _ = winreg.QueryValueEx(k, name)
            return val
    except OSError:
        return None


def get_cpu_info() -> dict:
    info = {"name": platform.processor() or "未知", "cores": 0, "threads": 0, "freq_mhz": 0}
    name = _read_reg(winreg.HKEY_LOCAL_MACHINE,
                     r"HARDWARE\DESCRIPTION\System\CentralProcessor\0", "ProcessorNameString")
    if name:
        info["name"] = name.strip()
    if HAS_PSUTIL:
        info["cores"] = psutil.cpu_count(logical=False) or 0
        info["threads"] = psutil.cpu_count(logical=True) or 0
        try:
            info["freq_mhz"] = int(psutil.cpu_freq().current or 0)
        except Exception:
            pass
    return info


def get_memory_info() -> dict:
    if not HAS_PSUTIL:
        return {"total_gb": 0, "used_gb": 0, "percent": 0}
    vm = psutil.virtual_memory()
    return {
        "total_gb": round(vm.total / (1 << 30), 1),
        "used_gb": round((vm.total - vm.available) / (1 << 30), 1),
        "percent": vm.percent,
    }


def get_os_info() -> dict:
    return {
        "system": f"{platform.system()} {platform.release()}",
        "version": platform.version(),
        "machine": platform.machine(),
        "python": platform.python_version(),
    }


def get_gpu_info() -> list[dict]:
    """读取 GPU：先注册表显示卡类，再 WMI 兜底取显存."""
    gpus = []
    base = r"SYSTEM\CurrentControlSet\Control\Class\{4d36e968-e325-11ce-bfc1-08002be10318}"
    try:
        with winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, base) as cls:
            i = 0
            while True:
                try:
                    sub = winreg.EnumKey(cls, i)
                    i += 1
                except OSError:
                    break
                with winreg.OpenKey(cls, sub) as k:
                    desc = _read_reg(winreg.HKEY_LOCAL_MACHINE, base + "\\" + sub, "DriverDesc")
                    if not desc:
                        continue
                    # 显存：HardwareInformation.qwMemorySize (8 字节)
                    mem = 0
                    try:
                        raw, typ = winreg.QueryValueEx(k, "HardwareInformation.qwMemorySize")
                        if isinstance(raw, bytes) and len(raw) >= 8:
                            mem = int.from_bytes(raw[:8], "little")
                        elif isinstance(raw, int):
                            mem = raw
                    except OSError:
                        pass
                    gpus.append({"name": desc, "vram_mb": round(mem / (1 << 20)) if mem else 0})
    except OSError:
        pass
    if not gpus:
        gpus = _gpu_via_wmi()
    # 按名称去重（虚拟适配器/多输出会出现同名条目）
    seen = set()
    unique = []
    for g in gpus:
        if g["name"] in seen:
            # 保留显存大的那条
            for i, u in enumerate(unique):
                if u["name"] == g["name"]:
                    if g["vram_mb"] > u["vram_mb"]:
                        unique[i] = g
                    break
            continue
        seen.add(g["name"])
        unique.append(g)
    return unique


def _gpu_via_wmi() -> list[dict]:
    import subprocess

    from .admin import _decode
    out = []
    try:
        p = subprocess.run(
            ["powershell", "-NoProfile", "-Command",
             "Get-CimInstance Win32_VideoController | ForEach-Object { \"{0}|{1}\" -f $_.Name, $_.AdapterRAM }"],
            capture_output=True, timeout=20,
            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
        for line in _decode(p.stdout).splitlines():
            parts = line.strip().split("|")
            if parts and parts[0]:
                ram = int(parts[1]) if len(parts) > 1 and parts[1].isdigit() else 0
                out.append({"name": parts[0], "vram_mb": round(ram / (1 << 20)) if ram else 0})
    except Exception:
        pass
    return out


def get_temperatures() -> dict:
    """温度传感器（多数 Windows 桌面机拿不到，返回空 dict 不算错误）."""
    if not HAS_PSUTIL:
        return {}
    try:
        temps = psutil.sensors_temperatures() or {}
        return {k: [dict(current=t.current, label=t.label) for t in v] for k, v in temps.items()}
    except Exception:
        return {}


def get_battery() -> dict | None:
    if not HAS_PSUTIL:
        return None
    try:
        b = psutil.sensors_battery()
        if b:
            return {"percent": b.percent, "plugged": b.power_plugged}
    except Exception:
        pass
    return None


def get_full_report() -> dict:
    """硬件信息总表."""
    return {
        "os": get_os_info(),
        "cpu": get_cpu_info(),
        "memory": get_memory_info(),
        "gpus": get_gpu_info(),
        "temps": get_temperatures(),
        "battery": get_battery(),
        "device_type": detect_device_type(),
    }


def detect_device_type() -> str:
    """粗略判断设备类型：台式 / 游戏本 / 轻薄本."""
    battery = get_battery()
    if battery is None:
        return "台式机"
    gpus = get_gpu_info()
    discrete = any("nvidia" in g["name"].lower() or "radeon" in g["name"].lower()
                   or "arc" in g["name"].lower() for g in gpus)
    mem = get_memory_info().get("total_gb", 0)
    if discrete and mem >= 16:
        return "游戏本"
    return "轻薄本"
