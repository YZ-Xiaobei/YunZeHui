# YunZeHui 云泽汇优化

Windows 系统优化与游戏加速工具（开源学习项目）。界面基于 PySide6（v2.1.0 全新设计：深色侧栏 + 卡片式布局 + 托盘常驻），逻辑层纯 Python 无 UI 依赖。

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

## 🧪 测试

`powershell
python tests/test_no_duplicate_rows.py
`

回归测试会连续刷新首页 / 硬件信息 / 垃圾清理页面，断言行数不会因重复刷新而增长（v2.0.0 的重复迭代 Bug）。

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

## 📦 v2.1.0 更新内容

### UI 全面重设计
- 深色侧栏 + 分组导航（概览 / 优化 / 工具 / 系统），12 个页面
- 卡片式信息展示、统一设计令牌（`theme.py`），状态卡/信息卡/分区卡三种组件
- 托盘常驻：关闭窗口最小化到托盘，托盘菜单可快速清理内存、开关守护、退出

### 框架重构
UI 层拆成三层：`theme.py`（设计令牌 + 全局 QSS）/ `base.py`（异步 Worker、PageBase、InfoCard、StatCard）/ `pages_main|tools|system.py`（页面）。逻辑层新增 `paths.py`（用户数据目录）与 `winreg_compat.py`（注册表兼容层）。

### 修复的问题

| # | 问题 | 影响 |
|---|---|---|
| 1 | 刷新时列表重复迭代（首页信息卡、垃圾清理勾选、磁盘分析状态栏反复 addRow/addWidget） | 行数无限增长，越刷新越长 |
| 2 | 网络优化用**说明文字**匹配勾选项，实际传的是参数名 | 4 项 TCP 优化一条都写不进注册表 |
| 3 | `NetworkThrottlingIndex` / `SystemResponsiveness` 写到网卡接口键 | 写错位置，永远不生效 |
| 4 | `OpenProcess(0x00F0)` 缺 `PROCESS_QUERY_INFORMATION`/`PROCESS_SET_QUOTA` | 内存工作集修剪永远失败，`trimmed` 恒为 0 |
| 5 | 磁盘目录分析拿 GB 和 MB 阈值比较 | 阈值实际放大 1024 倍，分析结果几乎总是空 |
| 6 | 取 PowerShell 输出用 UTF-8 解码（中文系统是 GBK） | 应用名/报错乱码 |
| 7 | 预装应用枚举失败时静默返回空列表 | 界面显示「共 0 个应用」，误导用户以为没装应用 |
| 8 | 游戏库把**目录**当 exe 路径，且 `三角洲回放` 被误判为游戏 | 往注册表写入无效目录项，检测结果错误 |
| 9 | `_MEI*` 按文件名前缀匹配（实际是目录） | 「安装包残留」永远清 0 字节 |
| 10 | 回收站 PowerShell 命令用了 cmd 的 `%%` 转义 | 回收站扫描/清理恒为 0 字节 |
| 11 | 清空回收站不看返回码，直接把清理前体积当已释放 | 清空失败也报成功 |
| 12 | 电源计划/CPU 频率细化没有还原路径，`boost_restore` 不调用 `restore_power_defaults` | 点「还原」后设置永久残留 |
| 13 | `ensure_high_performance` 忽略 `set_power_plan` 返回值 | 非管理员时谎报「已切到高性能」 |
| 14 | 服务备份无条件覆盖，还原时把原本 disabled 的服务拉起来 | 改坏系统默认值，原本停止的服务被启动 |
| 15 | 自动清理无 mtime 判断，会删正在写入的临时文件 | 可能破坏其他程序 |
| 16 | 配置文件写在包目录旁，装到 Program Files 后写入失败 | 配置存不下、备份丢失 |
| 17 | 服务精简页复选框默认全勾 | 误点一次禁用一整批服务 |
| 18 | 程序化切页时侧栏高亮不跟随 | 导航状态显示错误 |

### 代码签名
本目录 `exe` / `dll` / `pyd` 共 105 个文件全部已 Authenticode 签名（SHA-256 + DigiCert 时间戳），附 `.cer` 公钥证书与证书导入说明。自签名可校验完整性与发布者，但不能消除 SmartScreen 提示。
