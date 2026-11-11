"""YunZeHui 云泽汇优化 — 核心逻辑包."""
from . import (admin, booster, cleaner, debloat, diagnostics, disk, games, guardian,
               hardware, network, paths, services, startup)

__all__ = ["admin", "booster", "cleaner", "debloat", "diagnostics", "disk", "games",
           "guardian", "hardware", "network", "paths", "services", "startup"]
__version__ = "2.1.0"
