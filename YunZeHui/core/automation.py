"""YunZeHui 云泽汇优化 — GPU 监控与自动化."""
from __future__ import annotations

import os

from .hardware import get_gpu_info


def gpu_snapshot() -> dict:
    """GPU 快照（静态信息；利用率依赖 WMI 性能计数器，失败返回空）。"""
    return {"gpus": get_gpu_info()}


def auto_clean_on_startup(silent: bool = True) -> None:
    """静默自动清理：供 --autoclean 参数调用（只清临时文件，不碰回收站）。"""
    from .cleaner import CLEAN_TARGETS, _iter_files
    for _name, paths in CLEAN_TARGETS[:2]:  # 只清系统临时 + 用户临时
        for base in paths:
            if base == "::RECYCLE_BIN":
                continue
            if not os.path.isdir(base):
                continue
            for f in _iter_files(base):
                try:
                    os.remove(f)
                except OSError:
                    continue
