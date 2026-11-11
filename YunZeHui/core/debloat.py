"""YunZeHui 云泽汇优化 — UWP 预装应用管理（Debloat）."""
from __future__ import annotations

import subprocess

CREATE_NO_WINDOW = getattr(subprocess, "CREATE_NO_WINDOW", 0)


def _ps(script: str, timeout: int = 60) -> tuple[int, str]:
    try:
        p = subprocess.run(
            ["powershell", "-NoProfile", "-Command", script],
            capture_output=True, timeout=timeout, creationflags=CREATE_NO_WINDOW)
        out = p.stdout.decode("utf-8", errors="replace")
        return p.returncode, out
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
    """列出当前用户已安装的 UWP 应用，返回 [{name, package, removable}]."""
    rc, out = _ps(
        "Get-AppxPackage | "
        "ForEach-Object { '{0}|{1}' -f $_.Name, $_.PackageFullName }")
    apps = []
    if rc == 0:
        for line in out.splitlines():
            line = line.strip()
            if "|" not in line:
                continue
            name, full = line.split("|", 1)
            removable = any(kw.lower() in name.lower() for kw in SAFE_TO_REMOVE)
            apps.append({"name": name, "package": full, "removable": removable})
    return apps


def remove_app(package_full_name: str) -> bool:
    """移除指定 UWP 应用（当前用户）。"""
    rc, _ = _ps(f"Remove-AppxPackage -Package '{package_full_name}'", timeout=120)
    return rc == 0


def restore_app_for_all_users(package_name: str) -> bool:
    """重新注册系统内置应用（对误删的恢复有用，需管理员）。"""
    rc, _ = _ps(
        f"Get-AppxPackage -AllUsers -Name '*{package_name}*' | "
        "ForEach-Object { Add-AppxPackage -Register \"$($_.InstallLocation)\\AppxManifest.xml\" -DisableDevelopmentMode }",
        timeout=180)
    return rc == 0
