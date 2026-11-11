"""YunZeHui 云泽汇优化 — 管理员权限检测与提权."""
from __future__ import annotations

import ctypes
import os
import subprocess
import sys


def is_admin() -> bool:
    """检测当前进程是否以管理员权限运行."""
    try:
        return bool(ctypes.windll.shell32.IsUserAnAdmin())
    except Exception:
        return False


def _decode(raw: bytes) -> str:
    """解码命令输出：中文 Windows 的 powercfg 等输出为 GBK/ANSI，UTF-8 环境则是 UTF-8。
    用 cp936/GBK 优先尝试（中文系统），失败再用 UTF-8。"""
    if not raw:
        return ""
    for enc in ("gbk", "utf-8"):
        try:
            return raw.decode(enc)
        except UnicodeDecodeError:
            continue
    return raw.decode("latin-1", errors="replace")


def run_command(args: list[str], timeout: int = 30) -> tuple[int, str]:
    """运行一条系统命令（如 powercfg），返回 (returncode, 文本输出)."""
    try:
        p = subprocess.run(
            args,
            capture_output=True,
            timeout=timeout,
            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
        )
        return p.returncode, _decode(p.stdout) + _decode(p.stderr)
    except (OSError, subprocess.TimeoutExpired) as e:
        return -1, str(e)


def run_elevated_command(args: list[str], timeout: int = 60) -> tuple[int, str]:
    """需要管理员权限的命令：已是管理员则直接运行，否则经 UAC 提权运行."""
    if is_admin():
        return run_command(args, timeout=timeout)
    try:
        params = " ".join(f'"{a}"' if " " in a else a for a in args)
        rc = ctypes.windll.shell32.ShellExecuteW(
            None, "runas", "cmd.exe", f"/c {params}", None, 0  # SW_HIDE
        )
        # ShellExecuteW 返回 >32 表示成功启动
        if rc > 32:
            return 0, ""
        return rc, "UAC 提权被拒绝或失败"
    except Exception as e:
        return -1, str(e)


def relaunch_as_admin() -> bool:
    """请求以管理员身份重新启动本程序（UAC 弹窗）。成功则退出当前进程。"""
    try:
        exe = sys.executable
        # 源码运行：python.exe <入口脚本 或 -m YunZeHui>
        if exe.lower().endswith(("python.exe", "pythonw.exe")):
            main_script = os.path.abspath(sys.argv[0]) if sys.argv else ""
            if main_script and os.path.isfile(main_script):
                params = f'"{main_script}"'
            else:
                params = "-m YunZeHui"
        else:
            # PyInstaller 打包：直接重启自身
            exe = sys.executable
            params = ""
        rc = ctypes.windll.shell32.ShellExecuteW(None, "runas", exe, params or None, None, 1)
        if rc > 32:
            os._exit(0)
        return False
    except Exception:
        return False
