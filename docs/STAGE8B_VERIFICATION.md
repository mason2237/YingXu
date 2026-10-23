# 第八阶段 8b：缩放与候选发布包

日期：2026-10-23。授权：“好的，开始下一步”。本轮交付可运行的本机候选包；第八阶段正式发布验收仍有外部条件未完成。

## 交付与代码边界

- 版本 `0.8.0-rc.1` / Windows 文件版本 `0.8.0.1`，图标沿用项目既有资源。
- EXE：`outputs/stage8-release/0.8.0-rc.1/YingXu/YingXu.exe`。
- 同级 `YingXu-0.8.0-rc.1-windows-x64.zip` 是完整运行目录；解压后保留 `_internal`，不能只移动 EXE。EXE 未签名。
- 本轮完整运行目录约 487 MiB，ZIP 204,306,734 字节（约 195 MiB）；精确文件/压缩包 SHA256 随包提供，另记在 `docs/evidence/stage8b_metrics.json`。
- `yingxu/version.py` 共享版本；`window.py` 按当前屏幕可用逻辑尺寸限制初始/最小窗口，将诊断 backend 改为非生产分支延迟导入。未修改核心扫描、匹配或文件执行逻辑。
- `scripts/build_web.py --release --zip` 使用既有 `.venv-web`：PySide6/Qt 6.12.0、WebEngine 6.12.0.140、PyInstaller 6.17.0、hooks 2026.8。无新依赖、上游脚本、网络资源或前端开发服务器。
- 构建采用独立 `work/stage8-build` 和版本化输出，保留以前各阶段 EXE。默认不带 `--release` 仍生成第五阶段诊断试包，明确使用 `run_web_foundation.py`。
- 发布只复制 `WORKSPACE_ASSETS` 中的 53 个磁盘文件；Qt 内置 QWebChannel 不重复落盘。实际资源集合及 SHA256 一致；示例 fixtures/adapter、诊断和效果展览页面不在发布目录。
- 检查 PyInstaller 的 PYZ 清单：`yingxu.web_ui.bridge/service`、旧 Qt/legacy UI 均不在归档，真实 workspace bridge 存在。原 Lens 19 文件未改。
- WebEngine helper、Qt DLL、platform 插件、资源与 locales 已校验；仅剔除本轮构建目录内的 `*.debug.pak`，保留正式 packs。生成 `BUILD_MANIFEST.json`、原许可附件和逐文件 `SHA256SUMS.txt`。构建清单明确记录构建时的 Git 基线/是否未提交及 Python/前端源文件摘要，不把未提交构建冒充最终 Git 提交。

## 定向验证

### Qt 缩放和布局

`work/check_release_readiness.py`，真实源程序窗口和临时中文路径媒体，独立 QSettings/HistoryStore。使用进程级 `QT_SCALE_FACTOR`，**没有修改 Windows 显示设置**。

| 模拟倍率 | 首屏逻辑尺寸 | 最小窗口 | 横向溢出 / 弹窗 | 源码首次就绪 |
| --- | --- | --- | --- | --- |
| 100% | 1280×860 | 900×620 | 无 / 可操作 | 3.015s |
| 125% | 1280×860 | 900×620 | 无 / 可操作 | 2.391s |
| 150% | 1280×860 | 900×620 | 无 / 可操作 | 2.344s |
| 200% | 1248×632 | 900×620 | 无 / 可操作 | 2.265s |

实际本机屏幕可用区域为 2560×1392（100%），200% 模拟为 1280×696。检查初始高度留出标题栏空间、长文件名/列表、End 键到末行、明暗切换、外观弹窗，100% 下另检查最大化/最小化。各轮媒体字节/路径未变，JS 控制台错误为空。此表不认证 1080p 在 200% 等其他显示器组合，也不等价于真实系统 DPI/跨屏。

千行样本：1000 个真实视频 + 1 份字幕，扫描/匹配/DTO 总耗时 22.406s，首屏仅约 12 行 DOM，End 可到 1000 行；50ms 页面心跳计数约 449，耗时期间保持响应。该样本不代表 1000×1000 候选计算，不据此承诺固定帧率。后端耗时仍待分段剖析，未为追求快而削弱路径检查。

### 文件安全和业务

- `unittest discover -s tests`：32 项原业务通过。
- `tests/web/test_workspace.py`：14 项通过（一次性确认、重放、刷新、冲突、取消等）。
- `tests/web/test_boundary.py`：11 项通过；修改的 3 个 Python 模块编译通过。
- `work/check_local_workspace.py`：真实本地入口、原生选择器（仅返回临时目录）、递归扫描/选项、人工关联与确认、候选分页、原生行选择、窄窗/明暗、冻结预览、勾选确认、重复确认仅一次、3 份字幕实际整理、结果/历史/独占导出、刷新恢复和取消全部通过。JS 错误为空。
- 此处真实文件操作由源程序执行，介质全部是临时文件；未声称通过打包版的原生文件选择器执行了同一闭环。

### 独立 EXE

`work/check_packaged_release.mjs` 启动实际候选 EXE；工作目录/历史/临时文件隔离，子进程 PATH 只有 Windows/System32，去掉 Python/Qt 开发路径。Node 仅为外部检查工具，没有打入包。

最终从 ZIP 解压到含中文、空格、`&` 和单引号的新目录，实际启动其中 EXE；其摘要与交付 EXE 一致。修正后的 `--release --zip` 整条构建/独立校验命令已通过。

- 实际 WebEngine 页面/受限 QWebChannel 就绪，native mode 为 `local`，页面 `visibilityState=visible`，进程响应。
- 40 个按钮均有玻璃材质，外观和快捷操作弹窗工作，主页面无横向溢出，无示例 API。
- HTML 中全部样式/脚本引用为 `yingxu://app/` 本地资源，生产目录与静态哈希另外逐文件核验。自定义 scheme 的 Resource Timing 列表为空，因此没有用该空列表声称测量到全部模块请求。
- 实际页面截图 `outputs/stage8b_packaged_workspace.png`；JS 异常/console error 为空。EXE 的本次缓存状态启动时间和内存快照见 `docs/evidence/stage8b_metrics.json`，不是严格冷/热基准或稳态占用。
- 测试仅为自己的进程临时设置回环检查端口，退出关闭。生产入口没有新增调试端口、测试 bridge 或任意命令接口。
- 检查启动器读取的进程原生窗口标题为空；保留这一限制，未将其报成原生标题栏验收通过。页面实际可见和源 Qt 窗口另有验证。退出优先关闭自身窗口，必要时仅终止本次空闲测试进程树。
- 真实原生文件对话框、系统缩放和干净系统仍待最终设备验收。相同主机仅清除 PATH 不能证明没有开发环境的设备已经通过。

## 发现与限制

1. PyInstaller 完成后，构建父进程两次立即检查 helper EXE 报缺失（含正常 Windows 权限）；后续独立进程确认实际文件存在且可运行，根因尚未确认。最终将构建与验证分为独立进程，并提供 `--finalize-existing --zip` 中断续接；仍逐项检查文件/哈希，不移除 helper 或降低要求。构建前保存源摘要，续接时源文件改变则拒绝给旧 EXE 标新摘要。
2. 一次补充的“进程窗口标题”断言失败，原因是启动器拿不到标题；改为记录原始限制，并检查实际页面可见和应用响应。没有宣称这项原生验收已经通过。
   最终 ZIP 首次检查另遇 38/40 按钮计数：原断言早于动态节点下一帧挂载；检查改为等待真实玻璃挂载完成后通过，未改变产品代码或放宽覆盖数量。
3. 本轮缩放/闭环/EXE 日志未出现此前的 SharedImage/mailbox 诊断，但没有严格复现快速反复 resize+theme 的压力场景，不能判定底层问题彻底修复。
4. Qt wheel 的元数据声明与附件不同；两次尝试导出离线 `chrome://credits/` 均 `loadFinished=False`，工具明确失败，没有生成替代/伪造清单。完整 Qt/Chromium 材料、源代码/库替换义务和实际分发许可选择是公开发布门槛。依据 [Qt for Python 的分发区别](https://doc.qt.io/qtforpython-6/commercial/index.html) 与 [Qt WebEngine 许可说明](https://doc.qt.io/qt-6/qtwebengine-licensing.html)，需要逐项核对实际使用的包；现有候选包不宣称完成分发合规。
5. 无撤销、无自动崩溃恢复、未签名；保留上一阶段已记录的功能范围。

## 交接与下一步

提交消息：`build: deliver isolated WebEngine release candidate and DPI checks`；恢复标签：`stage8b-release-candidate`。本轮无电脑控制调用，未关闭用户原有窗口。

验收候选包后再实施 8c：真实 Windows DPI/跨屏/干净设备；万级真实目录、扫描各段和稳态性能；完整分发许可材料与最终发布决定。缺少外部设备时如实记录，不通过改变用户显示/系统设置模拟已通过。
