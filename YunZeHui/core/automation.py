"""YunZeHui 云泽汇优化 — GPU 监控与自动化."""
from __future__ import annotations

import os
import sys
import time

from .hardware import get_gpu_info

# 只删 2 小时以前创建/修改的临时文件，避免误删正在运行的安装程序临时数据
_MIN_AGE_SECONDS = 2 * 3600


def gpu_snapshot() -> dict:
    """GPU 快照（静态信息；利用率依赖 WMI 性能计数器，失败返回空）。"""
    return {"gpus": get_gpu_info()}


def auto_clean_on_startup(silent: bool = True) -> None:
    """静默自动清理：供 --autoclean 参数调用（只清临时文件，不碰回收站）。"""
    from .cleaner import _iter_files

    # 只清用户临时目录（%WINDIR%\Temp 需要管理员，且更危险）
    import tempfile
    roots = [tempfile.gettempdir(), os.path.expandvars(r"%LOCALAPPDATA%\Temp")]
    mei = getattr(sys, "_MEIPASS", "") or ""
    now = time.time()
    seen = set()
    for base in roots:
        if not base or not os.path.isdir(base):
            continue
        real = os.path.normcase(os.path.abspath(base))
        if real in seen:  # 两个路径可能是同一个目录（正常环境就是这样）
            continue
        seen.add(real)
        for f in _iter_files(base):
            # 绝不删自己（onefile 打包时解包目录就在 TEMP 里）
            if mei and os.path.normcase(os.path.abspath(f)).startswith(os.path.normcase(os.path.abspath(mei))):
                continue
            try:
                if (now - os.path.getmtime(f)) < _MIN_AGE_SECONDS:
                    continue
                os.remove(f)
            except OSError:
                continue

