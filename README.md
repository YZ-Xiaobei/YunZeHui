# YunZeHui 云泽汇优化

Windows 系统优化与游戏加速工具（开源学习项目）。界面基于 PySide6，逻辑层纯 Python 无 UI 依赖。

## ✨ 功能

| 模块 | 说明 |
|---|---|
| 🏠 首页概览 | CPU / 内存 / 磁盘实时状态、设备类型识别 |
| 🚀 游戏加速 | 一键切换高性能电源计划、清理内存、结束后台进程、开游戏模式、0.5ms 定时器、关 Game DVR、CPU 频率细化 |
| 🛡️ **动态内存守护** | 后台监控内存水位，超阈值自动分层清理；检测到游戏启动时预清理 |
| 🧹 垃圾清理 | 14 类系统垃圾扫描 → 勾选 → 清理 |
| 🎮 游戏库 | 自动检测三角洲行动 / CS2 / 我的世界 / PUBG，关闭全屏优化 |
| 📋 启动项管理 | Run 键 + 启动文件夹，禁用自动备份、可恢复 |
| 🌐 网络优化 | TcpAckFrequency / TcpNoDelay / 节流解除 / 系统响应性，DNS 刷新 |
| 🔧 服务精简 | 临时禁用 SysMain / DiagTrack / WSearch 等，全部可一键还原 |
| 📦 预装清理 | 扫描卸载 UWP 预装应用（仅当前用户，可恢复） |
| 💾 磁盘分析 | 分区用量、大目录占用分析 |
| 🖥️ 硬件信息 | CPU / 内存 / GPU（含显存）/ 电池 / 温度，可导出诊断报告 |
| ⚙️ 设置 | 开机自启、提权重启、后台清理进程列表编辑 |

**托盘常驻**：关闭窗口最小化到托盘，托盘右键可快速清理内存、开关守护、退出。

## 🚀 运行

```powershell
pip install PySide6 psutil
python -m YunZeHui              # 启动界面
python -m YunZeHui --autoclean  # 静默清理临时文件
```

系统级功能（电源切换、待机内存清理、HKLM 写入、服务禁用）需要管理员权限，可在「设置」页一键提权重启。

## 📦 打包

```powershell
pip install pyinstaller
python build_exe.py     # 输出 dist/YunZeHui/ 免安装目录
```

## 🧠 动态内存守护原理

Windows 的 standby list（待机缓存）会占用大量"假性可用"内存。守护功能采用**分层清理**策略，参考 ISLC 的做法：

1. **温和层**：`EmptyWorkingSet` 修剪所有进程工作集（无需管理员）
2. **标准层**：额外结束后台进程（kill list 可自定义）
3. **激进层**：`NtSetSystemInformation` 清理待机内存列表（需管理员）

触发条件：内存占用超过阈值（默认 85%）或检测到游戏进程启动，且有冷却时间避免频繁清理。

## 🔗 参考与致谢

本项目**全部代码自主实现**，未复制任何第三方源码。功能思路参考了以下公开项目与资料：

| 项目 | 协议 | 参考内容 |
|---|---|---|
| [Atlas-OS/Atlas](https://github.com/Atlas-OS/Atlas) | GPL-3.0 | Windows 服务精简思路、可逆备份设计 |
| [hellzerg/optimizer](https://github.com/hellzerg/optimizer) | GPL-3.0 | 注册表优化项清单、启动项管理思路 |
| [memstechtips/Winhance](https://github.com/memstechtips/Winhance) | - | Debloat（UWP 卸载）功能设计 |
| [rayenghanmi/RyTuneX](https://github.com/rayenghanmi/RyTuneX) | AGPL-3.0 | 系统调优分类方式 |
| [Diorser/LiteMonitor](https://github.com/Diorser/LiteMonitor) | - | 内存清理与硬件监控指标设计 |
| [ISLC (Intelligent Standby List Cleaner)](https://www.wagnardsoft.com/) | - | 待机内存列表清理原理（`NtSetSystemInformation`） |
| FrameBoost 极帧加速 | - | 功能范围参考（通过公开逆向分析了解其功能，代码完全重写） |

> 以上项目均为**思路参考**，本项目不包含它们的任何代码。各项目的许可证与版权归其作者所有。

## 🐛 已知限制

- 待机列表清理在部分机器上会引起短暂卡顿，默认需手动开启"激进模式"
- 温度传感器在多数台式机上不可用（硬件/驱动限制），属正常现象
- 未做代码签名，首次运行可能触发 SmartScreen，点「更多信息 → 仍要运行」

## 📄 许可

本项目代码采用 MIT License，可自由使用、修改、分发（保留版权声明）。

## ⚠️ 免责声明

系统优化工具涉及注册表与服务修改，请在使用前**创建系统还原点**。作者不对因使用本工具造成的任何系统问题负责。
