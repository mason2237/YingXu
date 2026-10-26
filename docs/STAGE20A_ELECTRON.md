# 阶段 20A：Electron 渲染架构对比

2026-10-26。阶段 A 的独立原型、功能与 HDR 验证已完成，独立 Windows 呈现补验现已通过。此前权限拒绝和无效尝试保留为历史。用户已条件授权通过后继续 B；本轮提交补验检查点后进入 B，C 仍等待验收。

## 授权与阶段边界

用户先确认实现 A，随后条件授权 A 门槛全部通过后继续 B。目标为日常交互高刷，保留主要液态玻璃及系统 HDR，允许简化次要烟雾、粒子和按钮效果。B 已接续，C 正式 EXE 仍需后续确认，不推送远端，不重跑干净系统。

## 当前实现

- 新入口 `run_electron.py`；容器 `desktop/electron/`；原 `run.py` 和 rc.12 包保留。
- 使用普通 BrowserWindow 和 Chromium 合成，不使用离屏网页、Qt 转贴纹理或 CPU 整页拷贝。
- `frontend/js/channel.js` 提供宿主适配；Qt 和 Electron 共用原网页、主题、Lens 与弹窗行为，不注入假 Qt 全局。
- `yingxu/desktop_host/` 使用 QCoreApplication 和原 WorkspaceBridge/WorkspaceService/QThread；仅增加可注入设置及服务类型。协议仍为 v1，请求编号、会话、事件顺序、去重和原确认机制保留。stdout 为 NDJSON，日志走 stderr，无本地 TCP 服务。
- 仅允许扫描、查询、候选读取、名称预览、隔离设置及登记文件的复制名称/定位。后端拒绝人工改配、整理执行及在线字幕。旧页面的目录对话框结果失效；不自动重发请求。
- 本地页面沙箱、contextIsolation、无 Node、校验 IPC 主窗口来源；资源限制在 frontend，阻止远程请求、任意导航和新窗口。
- HDR 仅使用工具栏局部 WebGPU canvas，`rgba16float` + `toneMapping: extended`，按需更新。系统 HDR 状态来自既有 Windows 只读接口。配置支持与实际输出分开标注，未验证时不声称 nativeHdrActive。
- 原型目录拖入尚未移植，界面引导使用真实目录选择按钮。所有原型配置、缓存、历史与诊断产物在忽略的 work 中。

## 测试与测量约定

同一台机器、同一个 300 视频/300 字幕临时目录、1280×860 网页视口、1 倍缩放、暗色/增强玻璃。普通用户运行保持原行为；诊断窗口临时置顶、请求显示器唤醒，退出释放，不修改系统电源计划或 HDR 开关。媒体不执行整理。

保留两组特效：full 为原增强效果；moderate 仅关闭雾气和短粒子。每个变体三轮，每轮 30 秒，由悬停、拖拽、连续滚轮各 10 秒组成。正式对照使用绝对时间定速的 60 次/秒输入，不等待上一个指针事件回包；记录实际数量并限制积压。初始等待回包的探索结果保留在 `architecture-a/`，隐藏启动的 Electron 初测在 `architecture-a-fixed60/` 中，均不混入最终可见窗口结果。最终 Qt 基线沿用可见的 `architecture-a-fixed60/qt-*`；Electron 使用 `architecture-a-visible/`。记录 rAF 间隔、长任务、Chromium 追踪、CPU 指标和截图。静止等待不计为掉帧。rAF 指标不等同于显示器实际帧率。

Qt 对比使用从 `228773c` 导出的冻结源码，位于忽略的 `work/test-results/architecture-a/`；没有切换或改写正式检出。Qt 不支持 Playwright 的浏览器上下文控制，统一使用最小原生 CDP 客户端传送交互。

初始测试启动器错误地对 Electron GUI 使用 `windowsHide:true`，首次显示受到 Windows 启动参数影响，产生“CDP 有界面而系统捕获灰屏”的无效结果。已改为正常可见启动，正式 Electron 数据只取 `architecture-a-visible/`，采样前断言原生窗口可见并截取系统画面。Qt 冻结基线的可见系统截图及数据保留在 `architecture-a-fixed60/`；此前 Electron 隐藏窗口数据弃用，不作为性能收益证明。最小化检查也改为无焦点/可见性模拟的原生 CDP，避免 Playwright 模拟干扰。

本机 Windows Graphics Capture 已通过：R16G16B16A16_FLOAT 的三段校准采样约为 2.99935、14.85677、75.91667，确认超过同画面 SDR 白点。它证明合成信号的扩展范围，不测面板峰值亮度。软件运行时不会把画布“配置成功”自动等同于所有设备 HDR 均已验收。一次捕获助手的显式 RoUninitialize 访问冲突已通过独立进程生命周期修复；旧失败记录保留。

最初 PresentMon 2.6.0 的 ETW 被 Windows 拒绝。用户随后授权继续管理员诊断，现仅对校验过的官方 PresentMon 进行有时限的提权采集，映序/Electron/Python 保持普通权限；未调整系统权限、组成员或 HDR 开关。补验见下节。

## 独立呈现补验（2026-10-26）

增强/简化各 3×30 秒，继续原 300 视频、相同视口/缩放/HDR/定速输入。新增 `scripts/start_presentmon_capture.ps1` 将采集锁定本轮 GPU PID，`profile_architecture.mjs --presentmon --presentation-root=...` 同步保存 QPC 锚点与交互边界。采集只调用官方已校验二进制，135 秒后退出，产物保存在忽略的测试目录。

`scripts/analyze_presentmon.py` 仅统计具有有效 DisplayedTime 的帧，以 CPUStartQPCTime + DisplayLatency 求实际呈现时刻；排除每阶段边缘 250ms，要求单一交换链覆盖全部悬停、拖拽和滚动阶段至少 95%，排除局部/空闲 HDR 交换链。不把 CPU FrameTime、rAF 或网页截图当实际呈现。3 项针对慢帧、缺失覆盖、NA 帧、仅悬停叠加层与多流歧义的测试通过。公开结果 `docs/evidence/stage20a-presentation.json` 含逐轮数值和原始文件摘要。

最终增强为 178.949–180.001fps，简化为 172.319–179.999fps；两档 p95 最大 5.6401ms、>25ms 最大 0.0603%，均通过门槛。原有 HDR/设置/生命周期验证沿用，不重复全套。两次早先 CDP 输入超时、一次诊断子进程模块路径错误及未同步覆盖的采集均保留，不计有效轮次。输入超时原因未确定；不能将其直接定性为产品崩溃或宣称所有长期偶发问题已排除。Qt 的独立 ETW 未补采，Qt rAF/Chromium 对比仍采用原有效基线。未测面板峰值亮度或 GPU 利用率。

## 验收门槛与后续

- 连续交互网页更新和实际呈现均平均 ≥120fps，实际间隔 p95 ≤11.2ms，>25ms 比例 <1%。
- 20 次设置开关、无内容消失，窗口尺寸/可见截图正常；静止和最小化停止额外绘制。
- 系统 HDR、浮点画布与超出 SDR 白点的实际合成高光同时验证。普通截图不测面板亮度。
- 任一关键门槛未证实，阶段 A 结束后不进入 B。报告实测收益和限制，再由用户决定后续范围。

## 最终测量结果

下表为三轮范围，网页 rAF 更新率；最后一列来自 Chromium 的中间合成提交事件，均不等同于独立验证的屏幕扫描呈现帧率。

| 宿主 / 效果 | 悬停 Hz | 拖拽 Hz | 滚动 Hz | 网页间隔 p95 上限 | Chromium 合成提交 Hz |
| --- | ---: | ---: | ---: | ---: | ---: |
| rc.12 Qt / full | 59.8–60 | 59.8–60 | 60 | 16.8ms | 59.88 |
| rc.12 Qt / moderate | 59.7–60 | 59.8–60 | 59.7–59.9 | 16.8ms | 59.87 |
| Electron / full | 180 | 179.1–180 | 143.5–150.83 | 11.2ms | 178.45 |
| Electron / moderate | 180–180.02 | 179.19–180 | 145.75–146.06 | 11.2ms | 177.90 |

各组没有 JS >50ms 长任务。Electron 单项 >25ms 的最坏比例为 0.11%，主要在首轮拖拽；其余多数为 0。降低次要效果未改变 Qt 的约 60Hz 更新上限；数据支持继续研究 Electron 直接呈现路径，不能据此把全部卡顿归结为单一原因或保证所有设备流畅。

记录的 CDP 所报 Chromium 进程工作集范围为 Qt full 689–1084 MiB、moderate 642–983 MiB，Electron full 767–850 MiB、moderate 761–832 MiB。Electron 的独立 Python 子进程不在该口径内，不能声称这是整应用内存。30 秒的 Chromium CPU 时间在 JSON 中逐轮保存，GPU 利用率未测得。启动测点不同（Qt 包含首次样本扫描、Electron 在选择目录前），只记录观测值，不据此比较冷启动快慢。

完整可公开摘要为 `docs/evidence/stage20a-electron.json`；原始 trace.json.gz、逐轮结果、系统/网页截图和失败记录位于忽略的 `work/test-results/`，不上传个人路径、临时会话或二进制。

## 验证及修改范围

- 31 项 Python 安全/服务/外观测试通过，其中新增 6 项覆盖真实扫描预览、持有实际确认令牌仍无法执行、路径参数拒绝、重复扫描去重、旧页面/错误目录回调失效和 stdio EOF 正常退出。
- 5 项 Node 主题回归通过。当前 Qt 入口集成检查通过：5000 行组件、120 视频真实扫描与 8 个实际滚轮、主题/缩放/最小化/两次重载、设置淡出与空闲停帧；无 JS/Python 错误。原 Qt 正式入口可运行。
- 最终可见 Electron 原型通过真实 300 视频/300 字幕扫描、搜索、主题切换、名称预览禁用执行、重载重连、20 次设置开关、空闲无 GL/HDR 多余绘制、原生最小化恢复/缩放及 WGC HDR 输出；无页面脚本异常。扫描样本没有被整理或覆盖。
- `start_electron.cmd` 以无调试参数、独立空配置实际启动，可见窗口/正常空状态及 WM_CLOSE 退出通过；python.exe 和 pythonw.exe 两种 stdio 后台的握手/EOF 退出均验证通过。
- 文件组：`desktop/electron/` 与 `run_electron.py` / `start_electron.cmd` 为新容器及入口；`yingxu/desktop_host/` 为后台适配；`frontend/js/channel.js`、客户端和外观/弹窗消费方为通用宿主边界；`frontend/js/hdr-layer.js` 与 prototype-mode.js 为可选高光和只读能力呈现；原服务仅增加构造注入，核心扫描/匹配/整理代码不改。
- 新测试/复现工具位于 `tests/web/test_electron_backend.py` 与 `scripts/*electron*` / `*architecture*` / `cdp_*` / 捕获助手；计划、进度、README、第三方说明及原文许可证已同步。未构建新 EXE、未删除 rc.12、未上传 GitHub。

## 运行与续接

```powershell
.venv-web/Scripts/python.exe run_electron.py --preview
.venv-web/Scripts/python.exe run_electron.py --preview --effects=moderate
# B 起默认/双击为完整工作台；正式 Qt 仍使用 run.py
```

依赖首次准备、可选 WGC 轮子及权限说明见 README 和 `desktop/electron/requirements-probe.txt`。用于复现的命令：

```powershell
.venv-web/Scripts/python.exe -m unittest tests.web.test_electron_backend tests.web.test_workspace tests.web.test_appearance -q
node work/check_theme_transition.mjs
node scripts/check_electron.mjs
node scripts/profile_architecture.mjs --host=qt --effects=full
node scripts/profile_architecture.mjs --host=qt --effects=moderate
node scripts/profile_architecture.mjs --host=electron --effects=full
node scripts/profile_architecture.mjs --host=electron --effects=moderate
node scripts/analyze_architecture.mjs
```

不因接续会话重复运行已通过的全部检查。独立交叉证据现已补齐，用户已明确条件授权通过后继续 20B，无需再次询问开始许可。随后 20C 再验证冻结后台的 MediaInfo 助手入口与独立 EXE，仍须阶段验收，不提前发布。

恢复基线为 `228773c95e8ab9c1c786354ad0d8b026f11826f0`。本阶段提交消息为 `feat: add isolated Electron rendering prototype and benchmark evidence`，使用 `git log -1` 获取本阶段最终提交。保留全部旧提交与验证记录。

## 06:15 单次条件续接

用户授权在 2026-10-26 香港时间 06:15 仅当 A 全部验收通过时继续 B。06:16 定向复核 PresentMon 的一秒 ETW 预检，退出码仍为 6，错误为 Access denied；当前进程非管理员。未获得独立屏幕呈现证据，不能把此前 rAF/合成指标替代该项，因此未进入 B。没有改变系统权限或重跑既有通过项。摘要在 `docs/evidence/stage20a-0615-gate.json`，原始结果在 `work/test-results/stage20a-scheduled-0615/`。实现恢复提交固定为 `566d73ea964599c42021c3175c4692c8f61a757a`；本轮仅保存复核记录并停止单次续接。
