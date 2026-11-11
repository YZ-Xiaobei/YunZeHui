"""YunZeHui 云泽汇优化 — 游戏库检测与专属优化."""
from __future__ import annotations

import os

from .winreg_compat import winreg

# 内置四款游戏专属配置（安装路径检测关键词 + 优化项）
KNOWN_GAMES = [
    {
        "id": "deltaforce",
        "name": "三角洲行动",
        "exe_keywords": ["deltaforce", "三角洲行动"],
        "exe_names": ["deltaforceclient-win64-shipping.exe", "deltaforce.exe"],
        "paths": [r"D:\WeGame\deltaforce", r"C:\WeGame\deltaforce"],
        "processes_to_close": ["wegame_helper.exe", "qqexternal.exe"],
    },
    {
        "id": "cs2",
        "name": "CS2",
        "exe_keywords": ["cs2", "counter-strike"],
        "exe_names": ["cs2.exe"],
        "paths": [r"D:\Steam\steamapps\common\Counter-Strike Global Offensive",
                  r"C:\Program Files (x86)\Steam\steamapps\common\Counter-Strike Global Offensive"],
        "processes_to_close": ["steamwebhelper.exe"],
    },
    {
        "id": "minecraft",
        "name": "我的世界",
        "exe_keywords": ["minecraft"],
        "exe_names": ["minecraft.exe", "minecraftlauncher.exe"],
        "paths": [r"C:\Program Files (x86)\Minecraft Launcher", r"D:\Minecraft"],
        "processes_to_close": [],
    },
    {
        "id": "pubg",
        "name": "PUBG",
        "exe_keywords": ["tslgame", "pubg"],
        "exe_names": ["tslgame.exe", "pubg.exe"],
        "paths": [r"D:\Steam\steamapps\common\PUBG", r"D:\WeGame\pubg"],
        "processes_to_close": ["steamwebhelper.exe"],
    },
]

# 目录名里带这些词的一律不算游戏安装（录像/存档/回放/缓存目录很常见）
_EXCLUDE_WORDS = ["回放", "錄像", "录像", "replay", "replays", "save", "saved",
                  "screenshots", "cache", "log", "logs", "backup", "config", "mods"]

# 附加检测的常见安装根目录
SEARCH_ROOTS = ["D:\\", "E:\\", "F:\\", "C:\\Program Files", "C:\\Program Files (x86)"]

# 在候选目录里找主 exe 的最大深度（避免全盘遍历太慢）
_FIND_EXE_DEPTH = 3


def _looks_like_junk(name: str) -> bool:
    low = name.lower()
    return any(w in low for w in _EXCLUDE_WORDS)


def _find_exe_under(root: str, exe_names: list[str], depth: int,
                    keywords: list[str] | None = None) -> str | None:
    """在 root 下浅层查找主程序 exe，返回完整路径或 None。

    优先精确匹配 exe_names；其次匹配「文件名含游戏关键词」的 exe
    （很多游戏主程序名带 -Win64-Shipping 后缀，精确名单覆盖不全）。
    """
    if depth < 0 or not root:
        return None
    try:
        entries = list(os.scandir(root))
    except OSError:
        return None
    # 先找当前层的目标 exe
    for e in entries:
        try:
            if e.is_file(follow_symlinks=False):
                low = e.name.lower()
                if low in exe_names:
                    return e.path
                if keywords and low.endswith(".exe") and any(k in low for k in keywords):
                    return e.path
        except OSError:
            continue
    # 再往下一层
    for e in entries:
        try:
            if e.is_dir(follow_symlinks=False) and not _looks_like_junk(e.name):
                hit = _find_exe_under(e.path, exe_names, depth - 1, keywords)
                if hit:
                    return hit
        except OSError:
            continue
    return None


def _resolve_lnk(lnk_path: str) -> str:
    """把 .lnk 快捷方式解析成目标 exe 路径；失败返回空字符串。

    用 WScript.Shell COM 解析（Windows 自带，无需额外依赖）。
    """
    import subprocess

    from .admin import _decode
    esc = lnk_path.replace("'", "''")
    script = (f"$s=(New-Object -ComObject WScript.Shell).CreateShortcut('{esc}');"
              "if($s.TargetPath){Write-Output $s.TargetPath}")
    try:
        p = subprocess.run(
            ["powershell", "-NoProfile", "-Command", script],
            capture_output=True, timeout=20,
            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
        target = _decode(p.stdout).strip().splitlines()
        path = target[0].strip() if target else ""
        if path and os.path.isfile(path) and path.lower().endswith(".exe"):
            return path
    except Exception:
        pass
    return ""


def _detect_one(g: dict) -> tuple[bool, str]:
    """检测单个游戏，返回 (installed, exe_path)。exe_path 一定是 exe 文件而不是目录。"""
    exe_names = [n.lower() for n in g.get("exe_names", [])]
    keywords = [k.lower() for k in g["exe_keywords"]]

    # 1) 已知安装路径
    weak = None
    for p in g["paths"]:
        if os.path.isdir(p) and not _looks_like_junk(os.path.basename(p)):
            hit = _find_exe_under(p, exe_names, _FIND_EXE_DEPTH, keywords)
            if hit:
                return True, hit
            weak = p  # 目录在但没找到 exe（可能是启动器目录），作为弱证据
            break

    # 2) 常见根目录浅搜：只认 exe 文件名或「含关键词且不是录像/存档目录」的子目录
    for root in SEARCH_ROOTS:
        if not os.path.isdir(root):
            continue
        try:
            entries = list(os.scandir(root))
        except OSError:
            continue
        for e in entries:
            try:
                low = e.name.lower()
                if _looks_like_junk(low):
                    continue
                if e.is_file(follow_symlinks=False):
                    if low in exe_names or (low.endswith(".exe") and any(k in low for k in keywords)):
                        return True, e.path
                elif e.is_dir(follow_symlinks=False) and any(k in low for k in keywords):
                    hit = _find_exe_under(e.path, exe_names, _FIND_EXE_DEPTH, keywords)
                    if hit:
                        return True, hit
            except OSError:
                continue

    # 3) 开始菜单快捷方式：解析 .lnk 拿到真实 exe 路径
    shortcut_dir = os.path.expandvars(r"%PROGRAMDATA%\Microsoft\Windows\Start Menu\Programs")
    for dirpath, _dirs, files in os.walk(shortcut_dir):
        for f in files:
            fl = f.lower()
            if not fl.endswith(".lnk") or _looks_like_junk(fl):
                continue
            if any(k in fl for k in keywords):
                target = _resolve_lnk(os.path.join(dirpath, f))
                if target:
                    # 快捷方式常指向 launcher.exe；向上 2 层找真正的游戏主程序
                    base = os.path.dirname(target)
                    for _ in range(3):
                        hit = _find_exe_under(base, exe_names, 2, keywords)
                        if hit:
                            return True, hit
                        parent = os.path.dirname(base)
                        if parent == base or len(parent) <= 3:
                            break
                        base = parent
                    return True, target
                weak = ""  # 有快捷方式但解析失败：算装过，只是拿不到路径

    return (True, "") if weak is not None else (False, "")


def detect_installed_games() -> list[dict]:
    """检测已安装的内置游戏，返回 [{..., installed, exe_path}]。"""
    found = []
    for g in KNOWN_GAMES:
        try:
            installed, exe_path = _detect_one(g)
        except Exception:
            installed, exe_path = False, ""
        found.append({**g, "installed": installed, "exe_path": exe_path})
    return found


def is_fullscreen_optimized(exe_path: str) -> bool | None:
    """检测exe的全屏优化是否已关闭（关闭 = 游戏性能更好）。"""
    if not exe_path or not os.path.isfile(exe_path) or winreg is None:
        return None
    key = r"Software\Microsoft\Windows NT\CurrentVersion\AppCompatFlags\Layers"
    try:
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, key) as k:
            val, _ = winreg.QueryValueEx(k, exe_path)
            return "DISABLEDXMAXIMIZEDWINDOWEDMODE" in str(val).upper()
    except OSError:
        return None


def set_fullscreen_optimized_off(exe_path: str, off: bool = True) -> bool:
    """关闭exe的全屏优化（写入兼容性标志）。off=False 时删除该标志恢复默认。

    只接受真实存在的 .exe 文件；传目录/空路径直接返回 False，
    否则会把目录路径当成兼容性键名写进注册表（无效项）。
    """
    if not exe_path or not os.path.isfile(exe_path) or not exe_path.lower().endswith(".exe"):
        return False
    if winreg is None:
        return False
    key = r"Software\Microsoft\Windows NT\CurrentVersion\AppCompatFlags\Layers"
    try:
        if off:
            flags = "~ DISABLEDXMAXIMIZEDWINDOWEDMODE"
            with winreg.CreateKey(winreg.HKEY_CURRENT_USER, key) as k:
                winreg.SetValueEx(k, exe_path, 0, winreg.REG_SZ, flags)
        else:
            with winreg.OpenKey(winreg.HKEY_CURRENT_USER, key, 0, winreg.KEY_WRITE) as k:
                try:
                    winreg.DeleteValue(k, exe_path)
                except FileNotFoundError:
                    pass
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
