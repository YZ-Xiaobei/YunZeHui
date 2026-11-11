"""YunZeHui 云泽汇优化 — 垃圾清理（14 类目录）."""
from __future__ import annotations

import os
import shutil
import tempfile

# 14 类清理目标：(说明, 目录列表)
CLEAN_TARGETS: list[tuple[str, list[str]]] = [
    ("系统临时文件", [tempfile.gettempdir(), r"C:\Windows\Temp"]),
    ("用户临时文件", [os.path.expandvars(r"%LOCALAPPDATA%\Temp")]),
    ("回收站", ["::RECYCLE_BIN"]),
    ("Windows 更新缓存", [r"C:\Windows\SoftwareDistribution\Download"]),
    ("缩略图缓存", [os.path.expandvars(r"%LOCALAPPDATA%\Microsoft\Windows\Explorer")]),
    ("DirectX 着色器缓存", [os.path.expandvars(r"%LOCALAPPDATA%\D3DSCache")]),
    ("崩溃转储", [r"C:\Windows\Minidump", os.path.expandvars(r"%LOCALAPPDATA%\CrashDumps")]),
    ("Windows 错误报告", [r"C:\ProgramData\Microsoft\Windows\WER"]),
    ("字体缓存", [r"C:\Windows\ServiceProfiles\LocalService\AppData\Local\FontCache"]),
    ("传递优化文件", [r"C:\Windows\ServiceProfiles\NetworkService\AppData\Local\Microsoft\Windows\DeliveryOptimization"]),
    ("预读取", [r"C:\Windows\Prefetch"]),
    ("最近文档记录", [os.path.expandvars(r"%APPDATA%\Microsoft\Windows\Recent")]),
    ("Edge/Chrome 缓存", [
        os.path.expandvars(r"%LOCALAPPDATA%\Google\Chrome\User Data\Default\Cache"),
        os.path.expandvars(r"%LOCALAPPDATA%\Microsoft\Edge\User Data\Default\Cache"),
    ]),
    ("安装包残留", [os.path.expandvars(r"%TEMP%\_MEI*")]),
]


def _iter_files(path: str, pattern: str = "*"):
    """递归列出文件。pattern 为 '*' 时全部匹配，否则按文件名前缀过滤（如 '_MEI'）。"""
    if os.path.isfile(path):
        yield path
        return
    if not os.path.isdir(path):
        return
    try:
        with os.scandir(path) as it:
            for entry in it:
                try:
                    if entry.is_file(follow_symlinks=False):
                        if pattern == "*" or entry.name.startswith(pattern):
                            yield entry.path
                    elif entry.is_dir(follow_symlinks=False):
                        yield from _iter_files(entry.path, pattern)
                except OSError:
                    continue
    except OSError:
        return


def scan_junk() -> list[dict]:
    """扫描各类垃圾大小，返回 [{name, files, bytes}]."""
    out = []
    for name, paths in CLEAN_TARGETS:
        total, count = 0, 0
        for base in paths:
            if base == "::RECYCLE_BIN":
                total, count = _scan_recycle()
                continue
            pattern = None if not base.endswith("*") else base.rsplit("\\", 1)[-1][:-1]  # 去掉尾部 *
            root = base.rsplit("\\", 1)[0] if base.endswith("*") else base
            for f in _iter_files(root, pattern or "*"):
                try:
                    total += os.path.getsize(f)
                    count += 1
                except OSError:
                    continue
        if total > 0:
            out.append({"name": name, "files": count, "bytes": total})
    return out


def _scan_recycle() -> tuple[int, int]:
    """用 PowerShell 清点回收站大小。"""
    import subprocess
    try:
        p = subprocess.run(
            ["powershell", "-NoProfile", "-Command",
             "$s=0;$c=0;Get-ChildItem 'C:\\$Recycle.Bin' -Recurse -Force -EA 0|%%{$s+=$_.Length;$c++};Write-Output \"$s $c\""],
            capture_output=True, timeout=30,
            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
        parts = p.stdout.decode(errors="replace").split()
        if len(parts) >= 2:
            return int(parts[0]), int(parts[1])
    except Exception:
        pass
    return 0, 0


def clean_targets(selected: list[str] | None = None, progress=None) -> list[dict]:
    """执行清理，返回 [{name, freed_bytes}]。selected 为 None 时清理全部。"""
    results = []
    for name, paths in CLEAN_TARGETS:
        if selected is not None and name not in selected:
            continue
        freed = 0
        for base in paths:
            if base == "::RECYCLE_BIN":
                freed += _clean_recycle()
                continue
            pattern = None if not base.endswith("*") else base.rsplit("\\", 1)[-1][:-1]  # 去掉尾部 *
            root = base.rsplit("\\", 1)[0] if base.endswith("*") else base
            for f in _iter_files(root, pattern or "*"):
                try:
                    size = os.path.getsize(f)
                    os.remove(f)
                    freed += size
                except OSError:
                    continue
            # 顺手删除空的子目录
            _remove_empty_dirs(root)
        results.append({"name": name, "freed_bytes": freed})
        if progress:
            progress(name, freed)
    return results


def _clean_recycle() -> int:
    import subprocess
    try:
        before, _ = _scan_recycle()
        subprocess.run(
            ["powershell", "-NoProfile", "-Command", "Clear-RecycleBin -Force -EA 0"],
            capture_output=True, timeout=60,
            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
        return before
    except Exception:
        return 0


def _remove_empty_dirs(root: str) -> None:
    for dirpath, _dirnames, _filenames in list(os.walk(root, topdown=False)):
        try:
            if dirpath != root and not os.listdir(dirpath):
                os.rmdir(dirpath)
        except OSError:
            continue
