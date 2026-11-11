"""YunZeHui 云泽汇优化 — 游戏库检测与专属优化."""
from __future__ import annotations

import os

try:
    import winreg
except ImportError:
    winreg = None

# 内置四款游戏专属配置（安装路径检测关键词 + 优化项）
KNOWN_GAMES = [
    {
        "id": "deltaforce",
        "name": "三角洲行动",
        "exe_keywords": ["deltaforce", "三角洲"],
        "paths": [r"D:\WeGame\deltaforce", r"C:\WeGame\deltaforce"],
        "processes_to_close": ["wegame_helper.exe", "qqexternal.exe"],
    },
    {
        "id": "cs2",
        "name": "CS2",
        "exe_keywords": ["cs2"],
        "paths": [r"D:\Steam\steamapps\common\Counter-Strike Global Offensive", r"C:\Program Files (x86)\Steam\steamapps\common\Counter-Strike Global Offensive"],
        "processes_to_close": ["steamwebhelper.exe"],
    },
    {
        "id": "minecraft",
        "name": "我的世界",
        "exe_keywords": ["minecraft", "javaw"],
        "paths": [r"C:\Program Files (x86)\Minecraft Launcher", r"D:\Minecraft"],
        "processes_to_close": [],
    },
    {
        "id": "pubg",
        "name": "PUBG",
        "exe_keywords": ["tslgame", "pubg"],
        "paths": [r"D:\Steam\steamapps\common\PUBG", r"D:\WeGame\pubg"],
        "processes_to_close": ["steamwebhelper.exe"],
    },
]

# 附加检测的常见安装根目录
SEARCH_ROOTS = ["D:\\", "E:\\", "F:\\", "C:\\Program Files", "C:\\Program Files (x86)"]


def detect_installed_games() -> list[dict]:
    """检测已安装的内置游戏，返回 [{..., installed, exe_path}]。"""
    found = []
    for g in KNOWN_GAMES:
        installed, exe_path = False, None
        # 先查指定路径
        for p in g["paths"]:
            if os.path.isdir(p):
                installed, exe_path = True, p
                break
        # 没找到则在常见根目录浅搜一层
        if not installed:
            for root in SEARCH_ROOTS:
                if not os.path.isdir(root):
                    continue
                try:
                    for entry in os.scandir(root):
                        nm = entry.name.lower()
                        if any(kw in nm for kw in g["exe_keywords"]):
                            if entry.is_dir():
                                installed, exe_path = True, entry.path
                                break
                            if entry.name.lower().endswith(".exe"):
                                installed, exe_path = True, entry.path
                                break
                except OSError:
                    continue
                if installed:
                    break
        # 最后查开始菜单快捷方式
        if not installed:
            shortcut_dir = os.path.expandvars(r"%PROGRAMDATA%\Microsoft\Windows\Start Menu\Programs")
            for dirpath, _dirs, files in os.walk(shortcut_dir):
                if any(kw in f.lower() for kw in g["exe_keywords"] for f in files):
                    installed = True
                    break
        found.append({**g, "installed": installed, "exe_path": exe_path or ""})
    return found


def is_fullscreen_optimized(exe_path: str) -> bool | None:
    """检测exe的全屏优化是否已关闭（关闭 = 游戏性能更好）。"""
    if not exe_path or not os.path.isfile(exe_path) or winreg is None:
        return None
    key = r"Software\Microsoft\Windows NT\CurrentVersion\AppCompatFlags\Layers"
    try:
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, key) as k:
            val, _ = winreg.QueryValueEx(k, exe_path.upper())
            return "DISABLEDXMAXIMIZEDWINDOWEDMODE" in str(val).upper()
    except OSError:
        return None


def set_fullscreen_optimized_off(exe_path: str, off: bool = True) -> bool:
    """关闭exe的全屏优化（写入兼容性标志）。off=False 时删除该标志恢复默认。"""
    if not exe_path:
        return False
    key = r"Software\Microsoft\Windows NT\CurrentVersion\AppCompatFlags\Layers"
    try:
        if off:
            flags = "~ DISABLEDXMAXIMIZEDWINDOWEDMODE"
            with winreg.CreateKey(winreg.HKEY_CURRENT_USER, key) as k:
                winreg.SetValueEx(k, exe_path.upper(), 0, winreg.REG_SZ, flags)
        else:
            with winreg.OpenKey(winreg.HKEY_CURRENT_USER, key, 0, winreg.KEY_WRITE) as k:
                winreg.DeleteValue(k, exe_path.upper())
        return True
    except OSError:
        return False


def get_game_boost_plan(game: dict) -> dict:
    """为指定游戏生成优化计划。"""
    return {
        "game": game["name"],
        "installed": game["installed"],
        "close_processes": game["processes_to_close"],
        "fullscreen_off": True,
    }
