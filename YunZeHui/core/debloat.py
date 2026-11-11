"""YunZeHui 云泽汇优化 — UWP 预装应用管理（Debloat）."""
from __future__ import annotations

import subprocess

from .admin import _decode

CREATE_NO_WINDOW = getattr(subprocess, "CREATE_NO_WINDOW", 0)


def _ps(script: str, timeout: int = 90) -> tuple[int, str]:
    """运行 PowerShell 脚本，返回 (returncode, stdout+stderr)。

    中文 Windows 的 PowerShell 输出是 GBK/ANSI，必须用 GBK 优先解码，
    否则应用名会变成乱码。失败时把 stderr 一并返回，便于界面提示原因。
    """
    try:
        p = subprocess.run(
            ["powershell", "-NoProfile", "-Command", script],
            capture_output=True, timeout=timeout, creationflags=CREATE_NO_WINDOW)
        return p.returncode, _decode(p.stdout) + _decode(p.stderr)
    except Exception as e:
        return -1, str(e)


# 常见可安全移除的预装应用（PackageFamily 名称关键词）
SAFE_TO_REMOVE = [
    "Microsoft.549981C3F5F10",       # Cortana
    "Microsoft.BingNews",
    "Microsoft.BingWeather",
    "Microsoft.GetHelp",
    "Microsoft.Getstarted",
    "Microsoft.MicrosoftSolitaireCollection",
    "Microsoft.MixedReality.Portal",
    "Microsoft.Office.OneNote",
    "Microsoft.OneConnect",
    "Microsoft.People",
    "Microsoft.PrintDialog",
    "Microsoft.SkypeApp",
    "Microsoft.Todos",
    "Microsoft.Wallet",
    "Microsoft.WindowsFeedbackHub",
    "Microsoft.WindowsMaps",
    "Microsoft.WindowsSoundRecorder",
    "Microsoft.YourPhone",
    "Microsoft.ZuneMusic",            # Groove/媒体播放器
    "Microsoft.ZuneVideo",
    "Clipchamp.Clipchamp",
    "MicrosoftTeams",
    "Microsoft.3DBuilder",
    "Microsoft.3DViewer",
    "Microsoft.Microsoft3DViewer",
    "microsoft.windowscommunicationsapps",  # 邮件和日历
]


def list_uwp_apps() -> list[dict]:
    """列出当前用户已安装的 UWP 应用，返回 [{name, package, removable}].

    枚举失败（例如被组策略/权限限制）时抛出 RuntimeError，让界面能显示原因，
    而不是静默返回空列表让人误以为「没有预装应用」。
    """
    rc, out = _ps(
        "Get-AppxPackage | "
        "ForEach-Object { '{0}|{1}' -f $_.Name, $_.PackageFullName }")
    apps = []
    for line in out.splitlines():
        line = line.strip()
        if "|" not in line:
            continue
        name, full = line.split("|", 1)
        name, full = name.strip(), full.strip()
        if not name or name.startswith(("Get-AppxPackage", "所在位置", "At line", "+", "    +")):
            continue
        removable = any(kw.lower() in name.lower() for kw in SAFE_TO_REMOVE)
        apps.append({"name": name, "package": full, "removable": removable})
    if not apps:
        detail = _first_error(out) or "未返回任何应用"
        raise RuntimeError(detail)
    return apps


def _first_error(text: str) -> str:
    """从 PowerShell 输出里提取第一段有用的错误信息。"""
    for raw in text.splitlines():
        s = raw.strip()
        if not s:
            continue
        if s.startswith(("+", "At line", "CategoryInfo", "FullyQualifiedErrorId",
                         "所在位置", "    +", "-->")):
            continue
        return s[:200]
    return ""


def remove_app(package_full_name: str) -> bool:
    """移除指定 UWP 应用（当前用户）。"""
    rc, _ = _ps(f"Remove-AppxPackage -Package '{package_full_name}'", timeout=180)
    return rc == 0


def restore_app_for_all_users(package_name: str) -> bool:
    """重新注册系统内置应用（对误删的恢复有用，需管理员）。"""
    rc, _ = _ps(
        f"Get-AppxPackage -AllUsers -Name '*{package_name}*' | "
        "ForEach-Object { Add-AppxPackage -Register \"$($_.InstallLocation)\\AppxManifest.xml\" -DisableDevelopmentMode }",
        timeout=180)
    return rc == 0
