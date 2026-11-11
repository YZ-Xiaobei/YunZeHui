"""YunZeHui 云泽汇优化 — 垃圾清理（14 类目录）."""
from __future__ import annotations

import os
import shutil
import tempfile

# 14 类清理目标：(说明, 目录列表)
# 特殊标记：
#   ::RECYCLE_BIN  → 清空回收站（PowerShell）
#   ::MEI_DIRS     → 删除 %TEMP% 下的 _MEIxxxx 解包目录（PyInstaller onefile 残留）
CLEAN_TARGETS: list[tuple[str, list[str]]] = [
    ("系统临时文件", [os.path.expandvars(r"%WINDIR%\Temp")]),
    ("用户临时文件", [tempfile.gettempdir()]),
    ("回收站", ["::RECYCLE_BIN"]),
    ("Windows 更新缓存", [os.path.expandvars(r"%WINDIR%\SoftwareDistribution\Download")]),
    ("缩略图缓存", [os.path.expandvars(r"%LOCALAPPDATA%\Microsoft\Windows\Explorer")]),
    ("DirectX 着色器缓存", [os.path.expandvars(r"%LOCALAPPDATA%\D3DSCache")]),
    ("崩溃转储", [os.path.expandvars(r"%WINDIR%\Minidump"),
                  os.path.expandvars(r"%LOCALAPPDATA%\CrashDumps")]),
    ("Windows 错误报告", [os.path.expandvars(r"%PROGRAMDATA%\Microsoft\Windows\WER")]),
    ("字体缓存", [r"C:\Windows\ServiceProfiles\LocalService\AppData\Local\FontCache"]),
    ("传递优化文件", [r"C:\Windows\ServiceProfiles\NetworkService\AppData\Local\Microsoft\Windows\DeliveryOptimization"]),
    ("预读取", [os.path.expandvars(r"%WINDIR%\Prefetch")]),
    ("最近文档记录", [os.path.expandvars(r"%APPDATA%\Microsoft\Windows\Recent")]),
    ("Edge/Chrome 缓存", [
        os.path.expandvars(r"%LOCALAPPDATA%\Google\Chrome\User Data\Default\Cache"),
        os.path.expandvars(r"%LOCALAPPDATA%\Microsoft\Edge\User Data\Default\Cache"),
    ]),
    ("安装包残留（_MEI 解包目录）", ["::MEI_DIRS"]),
]

# 清理时跳过最近 N 小时内修改过的文件，避免删掉别的程序正在用的临时数据
_MIN_AGE_SECONDS = 3600


def _iter_files(path: str, pattern: str = "*"):
    """递归列出文件。pattern 为 '*' 时全部匹配，否则按文件名前缀过滤。"""
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


def _mei_dirs() -> list[str]:
    """列出 %TEMP% 下的 PyInstaller 解包目录 _MEIxxxx（目录名匹配，不是文件前缀）。"""
    root = tempfile.gettempdir()
    out = []
    try:
        with os.scandir(root) as it:
            for e in it:
                try:
                    if e.is_dir(follow_symlinks=False) and e.name.startswith("_MEI"):
                        out.append(e.path)
                except OSError:
                    continue
    except OSError:
        pass
    return out


def _dir_tree_size(path: str) -> tuple[int, int]:
    """递归统计目录大小与文件数。"""
    total, count = 0, 0
    for dirpath, _dirnames, files in os.walk(path):
        for f in files:
            try:
                total += os.path.getsize(os.path.join(dirpath, f))
                count += 1
            except OSError:
                continue
    return total, count


def _is_old_enough(path: str) -> bool:
    """文件修改时间早于阈值才允许删除，防止误删正在写入的临时文件。"""
    import time
    try:
        return (time.time() - os.path.getmtime(path)) >= _MIN_AGE_SECONDS
    except OSError:
        return False


def scan_junk() -> list[dict]:
    """扫描各类垃圾大小，返回 [{name, files, bytes}]."""
    out = []
    for name, paths in CLEAN_TARGETS:
        total, count = 0, 0
        for base in paths:
            if base == "::RECYCLE_BIN":
                rb_bytes, rb_count = _scan_recycle()
                total += rb_bytes
                count += rb_count
                continue
            if base == "::MEI_DIRS":
                for d in _mei_dirs():
                    s, c = _dir_tree_size(d)
                    total += s
                    count += c
                continue
            for f in _iter_files(base):
                try:
                    total += os.path.getsize(f)
                    count += 1
                except OSError:
                    continue
        if total > 0:
            out.append({"name": name, "files": count, "bytes": total})
    return out


def _scan_recycle() -> tuple[int, int]:
    """用 PowerShell 清点回收站大小。

    注意：传给 powershell.exe -Command 的脚本里 `%` 不需要 cmd 式转义（`%%` 会被
    当成未知命令）；这里用 ForEach-Object 语义等价的 foreach 语句写法。
    """
    import subprocess

    from .admin import _decode
    script = ("$s=0;$c=0;"
              "Get-ChildItem 'C:\\$Recycle.Bin' -Recurse -Force -ErrorAction SilentlyContinue | "
              "ForEach-Object { $s += $_.Length; $c++ };"
              "Write-Output \"$s $c\"")
    try:
        p = subprocess.run(
            ["powershell", "-NoProfile", "-Command", script],
            capture_output=True, timeout=60,
            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
        parts = _decode(p.stdout).split()
        if len(parts) >= 2:
            return int(parts[0] or 0), int(parts[1] or 0)
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
            if base == "::MEI_DIRS":
                freed += _clean_mei_dirs()
                continue
            for f in _iter_files(base):
                if not _is_old_enough(f):
                    continue
                try:
                    size = os.path.getsize(f)
                    os.remove(f)
                    freed += size
                except OSError:
                    continue
            # 顺手删除空的子目录
            _remove_empty_dirs(base)
        results.append({"name": name, "freed_bytes": freed})
        if progress:
            progress(name, freed)
    return results


def _clean_mei_dirs() -> int:
    """删除可清理的 _MEI 解包目录，返回释放字节数。"""
    import sys
    freed = 0
    current = getattr(sys, "_MEIPASS", "") or ""
    for d in _mei_dirs():
        # 绝不删当前进程自己的解包目录
        if current and os.path.normcase(os.path.abspath(d)) == os.path.normcase(os.path.abspath(current)):
            continue
        if not _is_old_enough(d):
            continue
        size, _c = _dir_tree_size(d)
        try:
            shutil.rmtree(d, ignore_errors=True)
        except Exception:
            continue
        if not os.path.isdir(d):
            freed += size
    return freed


def _clean_recycle() -> int:
    """清空回收站，返回**实际**释放的字节数（清空失败返回 0）。"""
    import subprocess

    from .admin import _decode
    before, _count = _scan_recycle()
    try:
        p = subprocess.run(
            ["powershell", "-NoProfile", "-Command",
             "Clear-RecycleBin -Force -ErrorAction Stop; Write-Output 'OK'"],
            capture_output=True, timeout=120,
            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
        out = _decode(p.stdout) + _decode(p.stderr)
        if p.returncode != 0 or "OK" not in out:
            return 0
    except Exception:
        return 0
    after, _c2 = _scan_recycle()
    if after >= before:
        return 0
    return before - after


def _remove_empty_dirs(root: str) -> None:
    for dirpath, _dirnames, _filenames in list(os.walk(root, topdown=False)):
        try:
            if dirpath != root and not os.listdir(dirpath):
                os.rmdir(dirpath)
        except OSError:
            continue
