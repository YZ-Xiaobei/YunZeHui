"""YunZeHui 云泽汇优化 — 系统加速核心（电源计划/内存/进程/游戏模式/定时器/GameDVR）."""
from __future__ import annotations

import ctypes
import json
import os
import re
import subprocess
from dataclasses import dataclass, field

try:
    import winreg
except ImportError:
    winreg = None

try:
    import psutil

    HAS_PSUTIL = True
except ImportError:
    psutil = None
    HAS_PSUTIL = False

from .admin import run_command, run_elevated_command

# ---------------------------------------------------------------- 常量

GUID_ULTIMATE = "e9a42b02-d5df-448d-aa00-03f14749eb61"
GUID_HIGH_PERF = "8c5e7fda-e8bf-4a96-9a85-a6e23a8c635c"
GUID_BALANCED = "381b4222-f694-41f0-9685-ff5bb260df2e"
GUID_SAVER = "a1841308-3541-4fab-bc81-f71556f20b4a"

_POWER_PLAN_RE = re.compile(r"([a-f0-9\-]{36})\s+\((.+?)\)", re.IGNORECASE)

_SUB_PROCESSOR = "SUB_PROCESSOR"
_PROCTHROTTLEMAX = "PROCTHROTTLEMAX"
_PROCTHROTTLEMIN = "PROCTHROTTLEMIN"
_PERFBOOSTMODE = "PERFBOOSTMODE"

_GAMEDVR_KEY = r"Software\Microsoft\Windows\CurrentVersion\GameDVR"
_GAMEDVR_ALLOW_KEY = r"System\GameConfigStore"

KILL_LIST_FILE = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "kill_list.json")

DEFAULT_KILL_LIST = [
    "OneDrive.exe",
    "YourPhone.exe",
    "Teams.exe",
    "Skype.exe",
    "Spotify.exe",
    "msedge.exe",
]


@dataclass
class SystemStats:
    cpu_percent: float = 0.0
    mem_total: int = 0
    mem_used: int = 0
    mem_percent: float = 0.0
    power_plan: str = ""
    game_mode: bool | None = None
    hags: bool | None = None  # 硬件加速 GPU 计划
    processes: int = 0
    extra: dict = field(default_factory=dict)


# ---------------------------------------------------------------- 读取状态

def get_stats() -> SystemStats:
    """汇总当前系统状态，全部容错：任何一项失败不影响其他项."""
    st = SystemStats()
    if HAS_PSUTIL:
        try:
            st.cpu_percent = psutil.cpu_percent(interval=0.2) or 0.0
        except Exception:
            pass
        try:
            vm = psutil.virtual_memory()
            st.mem_total, st.mem_used = vm.total, vm.total - vm.available
            st.mem_percent = vm.percent
        except Exception:
            pass
        try:
            st.processes = len(psutil.pids())
        except Exception:
            pass
    st.power_plan = get_active_power_plan_name()
    st.game_mode = is_game_mode_on()
    st.hags = is_hags_on()
    return st


# ---------------------------------------------------------------- 电源计划

def list_power_plans() -> list[tuple[str, str]]:
    """列出所有电源计划，返回 [(guid, 名称)]；失败返回空表."""
    rc, out = run_command(["powercfg", "/list"])
    if rc != 0:
        return []
    return _POWER_PLAN_RE.findall(out)


def get_active_power_plan() -> str | None:
    """返回当前激活电源计划的 GUID."""
    rc, out = run_command(["powercfg", "/getactivescheme"])
    if rc != 0:
        return None
    m = _POWER_PLAN_RE.search(out)
    return m.group(1) if m else None


def get_active_power_plan_name() -> str:
    rc, out = run_command(["powercfg", "/getactivescheme"])
    if rc != 0:
        return "未知"
    m = _POWER_PLAN_RE.search(out)
    return m.group(2) if m else "未知"


def set_power_plan(guid: str) -> bool:
    rc, _ = run_command(["powercfg", "/setactive", guid])
    return rc == 0


def ensure_high_performance() -> str:
    """确保高性能电源计划。优先卓越性能，不存在则复制出高性能，再激活。返回实际激活的 GUID。"""
    plans = {g.lower(): n for g, n in list_power_plans()}
    if GUID_ULTIMATE.lower() in plans:
        set_power_plan(GUID_ULTIMATE)
        return GUID_ULTIMATE
    if GUID_HIGH_PERF.lower() in plans:
        set_power_plan(GUID_HIGH_PERF)
        return GUID_HIGH_PERF
    # 尝试复制卓越性能（有的系统默认隐藏）。duplicatescheme 生成新 GUID，需从输出解析。
    rc, out = run_command(["powercfg", "/duplicatescheme", GUID_ULTIMATE])
    new_guid = None
    if rc == 0:
        m = _POWER_PLAN_RE.search(out)
        if m:
            new_guid = m.group(1)
    if new_guid:
        set_power_plan(new_guid)
        return new_guid
    set_power_plan(GUID_HIGH_PERF)
    return GUID_HIGH_PERF


def restore_balanced_power_plan() -> bool:
    return set_power_plan(GUID_BALANCED)


# ---------------------------------------------------------------- 注册表工具

def _read_reg(root, path: str, name: str):
    try:
        with winreg.OpenKey(root, path) as k:
            val, _typ = winreg.QueryValueEx(k, name)
            return val
    except OSError:
        return None


def _write_reg(root, path: str, name: str, value, reg_type=None) -> bool:
    try:
        with winreg.CreateKey(root, path) as k:
            if reg_type is None:
                if isinstance(value, int):
                    reg_type = winreg.REG_DWORD
                else:
                    reg_type = winreg.REG_SZ
            winreg.SetValueEx(k, name, 0, reg_type, value)
            return True
    except OSError:
        return False


def _backup_reg_value(root, path: str, name: str) -> dict | None:
    """备份一个注册表值（供还原用）。"""
    val = _read_reg(root, path, name)
    if val is None:
        return None
    return {"root": int(root), "path": path, "name": name, "value": val}


def _reg_path_str(root, path: str) -> str:
    """把 winreg 根键转成 reg.exe 认识的字符串。"""
    return ("HKCU" if root == winreg.HKEY_CURRENT_USER else "HKLM") + "\\" + path


# ---------------------------------------------------------------- 游戏模式 / HAGS / GameDVR

def is_game_mode_on() -> bool | None:
    v = _read_reg(winreg.HKEY_CURRENT_USER, r"Software\Microsoft\GameBar", "AutoGameModeEnabled")
    return None if v is None else bool(v)


def set_game_mode(on: bool) -> bool:
    return _write_reg(winreg.HKEY_CURRENT_USER, r"Software\Microsoft\GameBar", "AutoGameModeEnabled", int(on))


def is_hags_on() -> bool | None:
    v = _read_reg(
        winreg.HKEY_LOCAL_MACHINE,
        r"SYSTEM\CurrentControlSet\Control\GraphicsDrivers",
        "HwSchMode",
    )
    return None if v is None else (v == 2)


def set_hags(on: bool) -> bool:
    # HwSchMode: 2 = 开启硬件加速 GPU 计划, 1 = 关闭
    return _write_reg(
        winreg.HKEY_LOCAL_MACHINE,
        r"SYSTEM\CurrentControlSet\Control\GraphicsDrivers",
        "HwSchMode",
        2 if on else 1,
    )


def is_game_dvr_on() -> bool | None:
    v = _read_reg(winreg.HKEY_CURRENT_USER, _GAMEDVR_KEY, "GameDVR_Enabled")
    return None if v is None else bool(v)


def set_game_dvr(off: bool) -> bool:
    """off=True 关闭 Xbox Game DVR 后台录制；off=False 恢复开启。"""
    ok1 = _write_reg(winreg.HKEY_CURRENT_USER, _GAMEDVR_KEY, "GameDVR_Enabled", 0 if off else 1)
    ok2 = _write_reg(
        winreg.HKEY_CURRENT_USER, _GAMEDVR_ALLOW_KEY, "GameDVR_Enabled", 0 if off else 1
    )
    return ok1 or ok2  # 任一键写入成功即可（第二个键在部分系统上不存在）


# ---------------------------------------------------------------- 定时器精度

def set_timer_resolution(enable: bool) -> bool:
    """通过注册表 GlobalTimerResolutionRequests 设置 0.5ms 定时器精度（Win10+/需重启生效）。"""
    try:
        return _write_reg(
            winreg.HKEY_LOCAL_MACHINE,
            r"SYSTEM\CurrentControlSet\Control\Session Manager\kernel",
            "GlobalTimerResolutionRequests",
            1 if enable else 0,
        )
    except OSError:
        return False


# ---------------------------------------------------------------- 内存清理

def _purge_standby_list() -> bool:
    """调用 NtSetSystemInformation 清理待机内存列表（需管理员）。"""
    try:
        nt = ctypes.windll.ntdll
        SystemMemoryListInformation = 80
        MemoryPurgeStandbyList = 4
        info = ctypes.c_ulong(MemoryPurgeStandbyList)
        rc = nt.NtSetSystemInformation(
            SystemMemoryListInformation,
            ctypes.byref(info),
            ctypes.sizeof(info),
        )
        return rc == 0
    except Exception:
        return False


def trim_working_set(pid: int) -> bool:
    try:
        h = ctypes.windll.kernel32.OpenProcess(0x00F0, False, pid)  # PROCESS_QUERY|SET_QUOTA|VM
        if not h:
            return False
        try:
            ok = ctypes.windll.psapi.EmptyWorkingSet(h)
            return bool(ok)
        finally:
            ctypes.windll.kernel32.CloseHandle(h)
    except Exception:
        return False


def free_memory(aggressive: bool = False) -> dict:
    """清理内存：修剪所有进程工作集；aggressive 时额外清待机列表（需管理员）。"""
    freed_procs = 0
    if HAS_PSUTIL:
        me = os.getpid()
        for p in psutil.process_iter(["pid"]):
            try:
                if p.info["pid"] != me and trim_working_set(p.info["pid"]):
                    freed_procs += 1
            except Exception:
                continue
    purged = False
    if aggressive:
        purged = _purge_standby_list()
    return {"trimmed": freed_procs, "standby_purged": purged}


# ---------------------------------------------------------------- 后台进程

def load_kill_list() -> list[str]:
    try:
        with open(KILL_LIST_FILE, encoding="utf-8") as f:
            data = json.load(f)
        if isinstance(data, list) and all(isinstance(x, str) for x in data):
            return data
    except Exception:
        pass
    return list(DEFAULT_KILL_LIST)


def save_kill_list(names: list[str]) -> bool:
    try:
        with open(KILL_LIST_FILE, "w", encoding="utf-8") as f:
            json.dump(names, f, ensure_ascii=False, indent=2)
        return True
    except Exception:
        return False


def kill_background_processes(extra: list[str] | None = None) -> list[str]:
    """结束 kill list 中的后台进程，返回实际结束的进程名."""
    names = set(load_kill_list())
    if extra:
        names.update(extra)
    killed = []
    if HAS_PSUTIL:
        me = os.getpid()
        wanted = {n.lower() for n in names}
        for p in psutil.process_iter(["pid", "name"]):
            try:
                nm = (p.info.get("name") or "").lower()
                if nm in wanted and p.info["pid"] != me:
                    p.terminate()
                    killed.append(nm)
            except Exception:
                continue
    return killed


# ---------------------------------------------------------------- 电源细化（CPU 频率/加速模式）

def apply_power_tweaks(max_percent: int = 100, min_percent: int = 5, boost_mode: int = 2) -> bool:
    """细化电源设置：CPU 最大/最小频率、性能加速模式（0 禁用 1 启用 2 激进）。"""
    ok = True
    cmds = [
        ["powercfg", "/setacvalueindex", "SCHEME_CURRENT", _SUB_PROCESSOR, _PROCTHROTTLEMAX, str(max_percent)],
        ["powercfg", "/setdcvalueindex", "SCHEME_CURRENT", _SUB_PROCESSOR, _PROCTHROTTLEMAX, str(max_percent)],
        ["powercfg", "/setacvalueindex", "SCHEME_CURRENT", _SUB_PROCESSOR, _PROCTHROTTLEMIN, str(min_percent)],
        ["powercfg", "/setdcvalueindex", "SCHEME_CURRENT", _SUB_PROCESSOR, _PROCTHROTTLEMIN, str(min_percent)],
        ["powercfg", "/setacvalueindex", "SCHEME_CURRENT", _SUB_PROCESSOR, _PERFBOOSTMODE, str(boost_mode)],
        ["powercfg", "/setactive", "SCHEME_CURRENT"],
    ]
    for c in cmds:
        rc, _ = run_command(c)
        if rc != 0:
            ok = False
    return ok


def restore_power_defaults() -> bool:
    """恢复默认电源细化设置。"""
    ok = True
    for setting, val in ((_PROCTHROTTLEMAX, "100"), (_PROCTHROTTLEMIN, "5"), (_PERFBOOSTMODE, "2")):
        for scope in ("/setacvalueindex", "/setdcvalueindex"):
            rc, _ = run_command(["powercfg", scope, "SCHEME_CURRENT", _SUB_PROCESSOR, setting, val])
            if rc != 0:
                ok = False
    run_command(["powercfg", "/setactive", "SCHEME_CURRENT"])
    return ok


# ---------------------------------------------------------------- 一键加速入口

def boost_full(aggressive: bool = False) -> dict:
    """一键游戏加速：电源计划+内存+进程+游戏模式+定时器+GameDVR+电源细化."""
    result = {
        "power_plan": ensure_high_performance(),
        "memory": free_memory(aggressive=aggressive),
        "killed": kill_background_processes(),
        "game_mode": set_game_mode(True),
        "timer": set_timer_resolution(True),
        "game_dvr": set_game_dvr(True),  # True = 关闭 DVR
        "power_tweaks": apply_power_tweaks(),
    }
    return result


def boost_restore() -> dict:
    """还原常规设置."""
    return {
        "timer": set_timer_resolution(False),
        "game_dvr": set_game_dvr(False),  # False 表示“恢复 DVR”
        "power_plan": restore_balanced_power_plan(),
    }
