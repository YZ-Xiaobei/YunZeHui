"""YunZeHui 云泽汇优化 — 用户数据目录解析.

为什么需要这个模块：
程序要把 guardian.json / kill_list.json / services_backup.json / startup_backup.json
这些「用户数据」写到磁盘。如果直接写在包目录旁边，用 PyInstaller 打包成
onedir 后路径会落到 `_internal\\YunZeHui\\` 里；一旦程序被放到
`C:\\Program Files` 这类只读目录，写入就会失败（配置存不下来、还原备份丢失）。

所以统一改为写入用户可写目录：
- 有 %APPDATA% → `%APPDATA%\\YunZeHui`
- 否则 → `~/.yunzehui`

同时做一次静默迁移：老版本放在包目录旁的 JSON 会自动复制过来。
"""
from __future__ import annotations

import os
import shutil

APP_DIR_NAME = "YunZeHui"


def data_dir() -> str:
    """返回可写的数据目录（会自动创建）。"""
    base = os.environ.get("APPDATA") or os.path.expanduser("~")
    d = os.path.join(base, APP_DIR_NAME)
    try:
        os.makedirs(d, exist_ok=True)
    except OSError:
        # 极端情况下回退到临时目录，保证程序不崩
        import tempfile
        d = os.path.join(tempfile.gettempdir(), APP_DIR_NAME)
        try:
            os.makedirs(d, exist_ok=True)
        except OSError:
            pass
    return d


def legacy_dir() -> str:
    """老版本写入位置（包目录的上一级，即 YunZeHui\\ 所在目录）。"""
    return os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def data_file(name: str) -> str:
    """返回用户数据文件的完整路径；老位置存在而新位置不存在时自动迁移一次。"""
    target = os.path.join(data_dir(), name)
    if not os.path.exists(target):
        old = os.path.join(legacy_dir(), name)
        if os.path.isfile(old):
            try:
                shutil.copy2(old, target)
            except OSError:
                # 迁移失败就用旧路径继续用，别让功能直接坏掉
                return old
    return target
