"""YunZeHui 云泽汇优化 — 诊断报告与 GPU 监控."""
from __future__ import annotations

import platform
import time

from .hardware import get_full_report
from .booster import get_stats, list_power_plans


def build_diagnostic_report() -> str:
    """生成完整的诊断报告文本。"""
    hw = get_full_report()
    st = get_stats()
    plans = list_power_plans()
    lines = [
        "=" * 50,
        "YunZeHui 云泽汇优化 — 诊断报告",
        f"生成时间：{time.strftime('%Y-%m-%d %H:%M:%S')}",
        "=" * 50,
        "",
        "【系统】",
        f"  系统：{hw['os']['system']}  版本 {hw['os']['version']}",
        f"  架构：{hw['os']['machine']}  设备类型：{hw['device_type']}",
        "",
        "【CPU】",
        f"  {hw['cpu']['name']}",
        f"  {hw['cpu']['cores']} 核 / {hw['cpu']['threads']} 线程  当前 {hw['cpu']['freq_mhz']} MHz",
        f"  使用率：{st.cpu_percent:.0f}%",
        "",
        "【内存】",
        f"  已用 {hw['memory']['used_gb']} GB / {hw['memory']['total_gb']} GB ({hw['memory']['percent']}%)",
        f"  进程数：{st.processes}",
        "",
        "【显卡】",
    ]
    for g in hw["gpus"]:
        vram = f"  显存 {g['vram_mb']} MB" if g["vram_mb"] else ""
        lines.append(f"  {g['name']}{vram}")
    lines += [
        "",
        "【电源】",
        f"  当前计划：{st.power_plan}",
    ]
    for guid, name in plans:
        lines.append(f"  - {name} ({guid[:8]}...)")
    lines += [
        "",
        "【游戏相关设置】",
        f"  游戏模式：{'开' if st.game_mode else ('关' if st.game_mode is not None else '未设置')}",
        f"  硬件加速 GPU 计划：{'开' if st.hags else ('关' if st.hags is not None else '未设置')}",
    ]
    if hw.get("battery"):
        lines.append("")
        lines.append(f"【电池】{hw['battery']['percent']}%  {'已接通电源' if hw['battery']['plugged'] else '使用电池'}")
    lines.append("")
    return "\n".join(lines)


def save_report(path: str) -> bool:
    try:
        with open(path, "w", encoding="utf-8") as f:
            f.write(build_diagnostic_report())
        return True
    except OSError:
        return False
