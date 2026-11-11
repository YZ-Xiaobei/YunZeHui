"""YunZeHui 云泽汇优化 — 磁盘空间分析."""
from __future__ import annotations

import os
import shutil


def list_drives() -> list[dict]:
    """列出所有本地分区及用量。"""
    out = []
    for letter in "CDEFGHIJKLMNOPQRSTUVWXYZ":
        root = f"{letter}:\\"
        if not os.path.exists(root):
            continue
        try:
            total, used, free = shutil.disk_usage(root)
            out.append({
                "drive": f"{letter}:",
                "total_gb": round(total / (1 << 30), 1),
                "used_gb": round(used / (1 << 30), 1),
                "free_gb": round(free / (1 << 30), 1),
                "percent": round(used / total * 100, 1) if total else 0,
            })
        except OSError:
            continue
    return out


def analyze_directory(root: str, depth: int = 2, min_mb: float = 100) -> list[dict]:
    """分析目录下各级子目录占用，返回大于阈值的 [{path, gb}] 按大小排序。"""
    result = []

    def dir_size(path: str, level: int) -> int:
        total = 0
        try:
            with os.scandir(path) as it:
                for e in it:
                    try:
                        if e.is_file(follow_symlinks=False):
                            total += e.stat().st_size
                        elif e.is_dir(follow_symlinks=False):
                            if level < depth:
                                total += dir_size(e.path, level + 1)
                            else:
                                total += _fast_size(e.path)
                    except OSError:
                        continue
        except OSError:
            pass
        return total

    def _fast_size(path: str) -> int:
        total = 0
        for dirpath, _dirs, files in os.walk(path):
            for f in files:
                try:
                    total += os.path.getsize(os.path.join(dirpath, f))
                except OSError:
                    continue
        return total

    try:
        entries = list(os.scandir(root))
    except OSError:
        return []
    for e in entries:
        if not e.is_dir(follow_symlinks=False):
            continue
        size = dir_size(e.path, 1)
        gb = size / (1 << 30)
        if gb >= min_mb:
            result.append({"path": e.path, "gb": round(gb, 2)})
    result.sort(key=lambda x: -x["gb"])
    return result


def find_large_files(root: str, top_n: int = 20, min_mb: float = 200) -> list[dict]:
    """找出指定盘符下最大的文件。"""
    import heapq
    heap = []
    for dirpath, _dirs, files in os.walk(root):
        for f in files:
            try:
                p = os.path.join(dirpath, f)
                size = os.path.getsize(p)
                if size >= min_mb * (1 << 20):
                    heapq.heappush(heap, (size, p))
                    if len(heap) > top_n:
                        heapq.heappop(heap)
            except OSError:
                continue
    return [{"path": p, "gb": round(s / (1 << 30), 2)} for s, p in sorted(heap, reverse=True)]
