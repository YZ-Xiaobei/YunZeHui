"""winreg 兼容层：非 Windows 环境（或 winreg 不可用）下提供一个「读取全失败」的替身。

各模块原本写的是：

    try:
        import winreg
    except ImportError:
        winreg = None

但调用处并没有做 None 判断，一旦 winreg 为 None，`winreg.HKEY_CURRENT_USER`
会直接抛 AttributeError 把整个页面/报告拖崩。这里改成统一导入：

    from .winreg_compat import winreg

替身对象的常量照常存在，任何键操作都抛 OSError——各模块的
`except OSError` 分支本来就能正确处理这种「读不到」的情况。
"""
from __future__ import annotations

try:  # pragma: no cover - 正常 Windows 环境走这里
    import winreg as _real

    winreg = _real
    HAS_WINREG = True
except ImportError:  # pragma: no cover - 仅非 Windows
    HAS_WINREG = False

    class _NoWinReg:
        """常量齐全、所有操作都失败的 winreg 替身。"""

        HKEY_CLASSES_ROOT = 0x80000000
        HKEY_CURRENT_USER = 0x80000001
        HKEY_LOCAL_MACHINE = 0x80000002
        HKEY_USERS = 0x80000003
        HKEY_CURRENT_CONFIG = 0x80000005

        KEY_READ = 0x20019
        KEY_WRITE = 0x20006
        KEY_ALL_ACCESS = 0xF003F

        REG_SZ = 1
        REG_EXPAND_SZ = 2
        REG_BINARY = 3
        REG_DWORD = 4
        REG_MULTI_SZ = 7

        def _fail(self, *args, **kwargs):
            raise OSError("winreg 在当前平台不可用")

        OpenKey = _fail
        CreateKey = _fail
        CreateKeyEx = _fail
        QueryValueEx = _fail
        SetValueEx = _fail
        DeleteValue = _fail
        EnumKey = _fail
        EnumValue = _fail
        CloseKey = _fail

    winreg = _NoWinReg()

__all__ = ["winreg", "HAS_WINREG"]
