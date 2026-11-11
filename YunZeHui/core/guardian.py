"""YunZeHui 云泽汇优化 — 动态内存守护.

参考 ISLC / Process Lasso 的思路：
- 后台线程持续监控内存水位
- 超过阈值或检测到游戏进程启动时，自动执行分层清理
- 分层策略：温和（修剪工作集）→ 标准（+后台进程清理）→ 激进（+待机列表清除，需管理员）
"""
from __future__ import annotations

import json
import os
import threading
import time
from dataclasses import dataclass, field

try:
    import psutil
    HAS_PSUTIL = True
except ImportError:
    psutil = None
    HAS_PSUTIL = False

from .booster import free_memory, kill_background_processes, load_kill_list
from .paths import data_file

CONFIG_FILE = data_file("guardian.json")

# 常见游戏进程关键词（用于自动检测游戏启动）
GAME_KEYWORDS = [
    "cs2", "deltaforce", "tslgame", "pubg", "minecraft", "javaw",
    "unreal", "ue4", "ue5", "game", "launch_game",
]

DEFAULT_CONFIG = {
    "enabled": False,
    "threshold_percent": 85,      # 内存超过此百分比触发清理
    "interval_seconds": 10,       # 检查间隔
    "aggressive": False,          # 激进模式：清待机列表（需管理员）
    "auto_kill_on_threshold": True,   # 达阈值时顺便结束后台进程
    "game_detect_enabled": True,  # 检测到游戏启动时立即清理
    "cooldown_seconds": 60,       # 两次清理之间的最小间隔
}


@dataclass
class GuardianEvent:
    time: str
    reason: str        # threshold / game_start / manual
    mem_percent: float
    freed_mb: float
    trimmed: int
    killed: int

    def to_dict(self) -> dict:
        return {
            "time": self.time, "reason": self.reason,
            "mem_percent": round(self.mem_percent, 1),
            "freed_mb": round(self.freed_mb, 1),
            "trimmed": self.trimmed, "killed": self.killed,
        }


def load_config() -> dict:
    try:
        with open(CONFIG_FILE, encoding="utf-8") as f:
            cfg = json.load(f)
        if isinstance(cfg, dict):
            merged = dict(DEFAULT_CONFIG)
            merged.update({k: v for k, v in cfg.items() if k in DEFAULT_CONFIG})
            return merged
    except Exception:
        pass
    return dict(DEFAULT_CONFIG)


def save_config(cfg: dict) -> bool:
    try:
        with open(CONFIG_FILE, "w", encoding="utf-8") as f:
            json.dump(cfg, f, ensure_ascii=False, indent=2)
        return True
    except Exception:
        return False


def find_game_processes() -> list[str]:
    """找出正在运行的游戏进程名."""
    if not HAS_PSUTIL:
        return []
    found = set()
    for p in psutil.process_iter(["name"]):
        try:
            nm = (p.info.get("name") or "").lower()
            if any(kw in nm for kw in GAME_KEYWORDS):
                found.add(nm)
        except Exception:
            continue
    return sorted(found)


class MemoryGuardian(threading.Thread):
    """动态内存守护线程。全程容错，绝不抛异常中断。"""

    def __init__(self):
        super().__init__(daemon=True, name="YunZeHui-MemoryGuardian")
        self._stop_event = threading.Event()
        self._lock = threading.Lock()
        self.cfg = load_config()
        self.events: list[GuardianEvent] = []       # 最近事件（内存中保留 50 条）
        self.last_game_procs: set[str] = set()
        self._last_clean_time = 0.0
        self.running = False

    # ---------- 控制 ----------

    def start_guardian(self):
        with self._lock:
            if not self.running:
                self.cfg = load_config()
                self.running = True
                self._stop_event.clear()
                self.start()

    def stop_guardian(self):
        with self._lock:
            self.running = False
        self._stop_event.set()

    def update_config(self):
        """外部改了配置后调用，线程下次循环自动生效。"""
        self.cfg = load_config()

    def trigger_manual(self) -> GuardianEvent | None:
        """手动触发一次清理。"""
        return self._do_clean("manual")

    # ---------- 主循环 ----------

    def run(self):
        while not self._stop_event.is_set():
            try:
                self._tick()
            except Exception:
                pass
            self._stop_event.wait(max(2, int(self.cfg.get("interval_seconds", 10))))

    def _tick(self):
        if not HAS_PSUTIL:
            return
        cfg = self.cfg
        vm = psutil.virtual_memory()
        percent = vm.percent

        # 1) 游戏启动检测
        if cfg.get("game_detect_enabled"):
            now_games = set(find_game_processes())
            new_games = now_games - self.last_game_procs
            self.last_game_procs = now_games
            if new_games and self._cooldown_ok():
                self._do_clean("game_start", percent)
                return

        # 2) 阈值检测
        threshold = float(cfg.get("threshold_percent", 85))
        if percent >= threshold and self._cooldown_ok():
            self._do_clean("threshold", percent)

    def _cooldown_ok(self) -> bool:
        return (time.time() - self._last_clean_time) >= max(10, int(self.cfg.get("cooldown_seconds", 60)))

    # ---------- 清理 ----------

    def _do_clean(self, reason: str, mem_percent: float | None = None) -> GuardianEvent | None:
        self._last_clean_time = time.time()
        if mem_percent is None:
            try:
                mem_percent = psutil.virtual_memory().percent
            except Exception:
                mem_percent = 0
        before = self._mem_available_mb()
        freed_procs = 0
        killed = 0

        # 分层 1：温和 —— 修剪所有进程工作集
        r = free_memory(aggressive=False)
        freed_procs = r.get("trimmed", 0)

        # 分层 2：达阈值或手动 —— 结束 kill list 后台进程
        if reason in ("threshold", "manual") and self.cfg.get("auto_kill_on_threshold"):
            killed = len(kill_background_processes())

        # 分层 3：激进 —— 清待机列表（需管理员）
        aggressive = bool(self.cfg.get("aggressive"))
        if aggressive:
            r2 = free_memory(aggressive=True)
            freed_procs = max(freed_procs, r2.get("trimmed", 0))

        time.sleep(1.5)  # 等系统释放
        after = self._mem_available_mb()
        freed_mb = max(0.0, after - before)

        ev = GuardianEvent(
            time=time.strftime("%H:%M:%S"),
            reason=reason,
            mem_percent=mem_percent,
            freed_mb=freed_mb,
            trimmed=freed_procs,
            killed=killed,
        )
        self.events.append(ev)
        if len(self.events) > 50:
            self.events = self.events[-50:]
        return ev

    @staticmethod
    def _mem_available_mb() -> float:
        if HAS_PSUTIL:
            try:
                return psutil.virtual_memory().available / (1 << 20)
            except Exception:
                pass
        return 0.0


# 全局单例
_guardian: MemoryGuardian | None = None


def get_guardian() -> MemoryGuardian:
    global _guardian
    if _guardian is None:
        _guardian = MemoryGuardian()
    return _guardian
