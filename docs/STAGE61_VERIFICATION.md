# 6.1 原版效果移植与对照验收

完成：2026-10-22（2026-10-21 开始）。只实施 6.1，完整明暗主题属于下一检查点 6.2；真实用户文件仍由第四阶段 Qt 工作台处理。

## 实际采用与来源

固定上游 `ruiqichenbiec/design-systems`，提交 `7a424c93b9be13cf835b91ea67495fec2ec0584e`。新增的 **19 个 Lens ES module/CSS 文件完全保持原字节**，包括原版 GlassRenderer、JellyController、18 类工厂、光学控件、合成声音及完整本地依赖。`ORIGIN.json` 保存原路径/Git blob，检查使用 Git 的 blob 头及 SHA-1 计算逐项比对；`.gitattributes` 固定 LF。完整 MIT 与旧 focus/modal 来源记录保留。

这次与阶段 6 初始基线的区别是：实际使用上游玻璃/材质/手势/控件代码；旧自写 shader 仅在开发页作为比较对象。项目适配器集中处理 Qt 生命周期、开关/强度、绘制统计和业务回调，未复制重写光学算法。

全量 [82 项清单](UPSTREAM_EFFECTS.md) 和 [结构化记录](upstream-effects.json)：Lens 18 控件 + 4 组合、Lattice 14、Overture 46，另列光学/声音/运动原语。每项包含已采用、待适配、可选展示或暂不采用的具体理由。Lattice/Overture 的待适配项尚未完成本机运行验收，不等于它们已经加入软件。

## 入口与文件

```powershell
& .\.venv-web\Scripts\python.exe .\run_effects_preview.py
& .\.venv-web\Scripts\python.exe .\run_web_preview.py
```

| 位置 | 内容 |
| --- | --- |
| `frontend/vendor/design-systems/lens/` | 19 个原文件、ORIGIN；原版模型与控件 |
| `frontend/js/components/lens-runtime.js` | 公共 runtime 接入、原版/增强参数、背景、Qt 生命周期及只读诊断 |
| `frontend/js/components/upstream-effects.js` | 工作台目录/按钮/状态筛选增强，调用既有真实前端状态 |
| `frontend/js/components/particle-feedback.js` | 保留项目已有短粒子，未冒充 Lattice 点场源码 |
| `frontend/effects.html` / `js/effects-lab.js` / `css/effects-lab.css` | 旧版/原版/增强三列对照、18 类目录、背景及弹窗 |
| `frontend/workspace.html` / `css/lens-adapter.css` | 新工作台材质及标准/增强/关闭入口 |
| `yingxu/web_ui/window.py` / `resources.py` | 新独立页面选项与逐文件资源白名单，不给预览注册 channel |
| `tests/web/test_lens_sources.py` / `work/check_lens_math.mjs` | 原文件/依赖/限制检查，原版纯数学/物理/PCM 检查 |
| `work/check_lens_preview.py` / `check_web_workspace.py` | 实际 WebEngine 材质/控件与完整工作台回归 |
| `work/record_lens_preview.py` / `encode_lens_recording.py` | 实际 Qt 帧录制及 GIF 编码 |

没有安装新运行依赖，没有执行上游构建或演示脚本；只在审查后装载所采用的本地运行模块。应用运行不要求 Node、Pillow 或开发服务器；Node 用于纯函数检查，Pillow 12.3.0 使用 Codex 已有工具运行时，仅编码录制。样本页不注册 QWebChannel，用户目录/执行接口保持禁用。

## 运行效果与生命周期适配

- 工作台目录栏/两按钮/四状态胶囊共七个原版光学表面。正文独立 DOM，原名/评分/状态清晰，完整名称/目标/人工确认等流程保留。筛选沿用上游选择组，点击与方向键都更新同一个 WorkspaceStore，没有视觉选中与实际筛选分离。
- 标准为 Thick `.90/.24/.65`，增强为 `.98/.12/.45`（折射/雾化/色散）；关闭使用实色材质。工作台使用浅蓝曲面，比较页使用高对比纹理；均是应用自身绘制的背景，不采集桌面或文件文字。
- 18 类原版工厂全部创建并可交互，共享固定画布；切换只显示当前控件，退出统一销毁。原版四场景 aurora/sunset/ocean/grid 与自定义背景可切换；这些场景不是完整应用明暗主题。
- 原版滑动开关、胶囊/标签、反光/流光、进度波动、凹槽汇入、放大透镜、卡片滚动、菜单键盘、自由拖动等在开发页演示。进度为明确示例，完成后关停波动；原声音默认关闭且存储为 null，未自动播放。
- 初次逐组件销毁/重建原生画布时遇到 Qt shared-image mailbox 警告。现使用固定少量画布；普通视口隐藏只停绘制/保留缓存，真正销毁删除程序/纹理/缓冲/观察器及登记，由 WebEngine 清理画布。原版着色与物理逻辑不变，这部分平台适配在原文件之外。
- 调用真实 WebGL 扩展模拟上下文丢失时，立即在丢失事件中恢复会停留在 lost。适配层延后 150ms，使用丢失前缓存的扩展对象恢复；最小诊断观测 100ms 为 lost、500ms 已恢复，完整流程复查通过。
- 减少动态遵循系统/手动偏好，按需帧结束后停止；最小化显式取消待执行帧。无 WebGL 的模拟使用新实例 getContext 返回 null，显示原版 CSS 兼容材质；不是多显卡/驱动认证。

## 本轮检查

| 检查 | 结果 |
| --- | --- |
| 既有 Python 业务 | 32 项通过；core/review/operations、旧 Qt UI、旧构建与依赖无差异 |
| Web 与来源 | 14 项通过：原 11 项 + 19 原文件 blob、完整模块/资源闭包、无网络/任意脚本执行等三项 |
| 前端审阅适配器 | 8 项通过，稳定选择、人工确认、旧版本失效、跳过/恢复、大查询、执行拒绝等保留 |
| 原版纯函数 | 7 项通过：材质约束、弹簧中途改目标/收敛、形变面积、坐标/范围、凹槽目标、GPU 预算释放顺序、13 种短音及摩擦 PCM |
| 原版目录实际窗口 | 18 类均可创建并演示；原生 End 键切换凹槽/二维值，自由透镜原生拖动位置从中心改变到 X53%/Y54%；菜单 Escape、进度完成/停波、两变体、弹窗内实际 GL 均通过 |
| 实际像素 | 移除原版材质几何后，同画布 56,457 个像素发生大于指定阈值的 RGB 变化；恢复几何后继续运行，确认渲染器确实作用于图像 |
| 空闲/隐藏/释放 | 玻璃关闭/重新开启、手动减少动态、对照/完整交互后的目录帧停止、实际最小化停帧、原版 GPU 登记最终归零均通过；上下文丢失后立即最小化/恢复的组合检查通过；缓存不等于所有上下文立即归还驱动 |
| 兼容与窗口 | 模拟 WebGL 不可用显示 CSS 回退；恢复可见后共享画布继续工作；900px 窄窗口无页面横向溢出；实际四种原版场景切换检查通过 |
| 完整工作台 | 真实 WebEngine 全流程通过：复制/剪贴板、状态键盘、候选与确认、跳过恢复、搜索/组合事件、预览禁用执行、示例记录、宽窄/最大化、10,000 行、真实 GL 丢失/恢复及刷新 |
| 旧 Web 基础回归 | ping、Python 后台事件、三份目标、样本不变、外部导航拒绝、普通/运行中刷新、延后关闭通过 |
| 电脑控制使用 | 本轮 0 次；由 QtTest/JavaScript 自动化、程序截图和读取图片完成，未重复手动控制桌面 |

单项检查合计 **61 项**（32+14+8+7），GUI/录制另列。声音验证的是 PCM 与默认静音，未人工试听。环境沿用 Windows 11 / Python 3.12.0 / PySide6、Qt 6.12.0 / Chromium 140.0.7339.225。

最后一轮 10,000 行示例：8 个行 DOM、一次可见行渲染约 3.3ms、构造约 115.6ms，JS 堆粗采样 23.1MB。搜索约 281ms 包含防抖/检查等待；动态帧采样发生在一次反馈期间，之后有独立空闲/最小化断言。这不等于真实磁盘扫描性能、全进程组内存或空闲 CPU 基准。

## 证据与复现

- [实际材质对照](../outputs/stage61_comparison.png)、[当前工作台](../outputs/stage61_workspace.png)、[实际操作 GIF](../outputs/stage61_motion.gif)。
- [凹槽吸附](../outputs/stage61_drop_select.png)、[二维透镜](../outputs/stage61_xy_lens.png)、[弹窗](../outputs/stage61_dialog.png)、[进度](../outputs/stage61_progress.png)、[原版海洋背景](../outputs/stage61_ocean.png)。
- [窄窗口](../outputs/stage61_narrow.png)、[普通材质](../outputs/stage61_fallback.png)、[模拟不可用](../outputs/stage61_unavailable.png)、[工作台最小窗口](../outputs/stage61_workspace_minimum.png)。

截图直接来自 Qt/WebEngine 窗口。GIF 为 54 个实际窗口帧、约 6.444 秒、3,982,933 字节，原生 Qt 按压/拖动后凹槽实际选择为双语；无设计稿替换或插值动画。图片/帧/GIF 是本地忽略产物，可重新生成。

```powershell
& .\.venv\Scripts\python.exe -m unittest discover -s tests -v
& .\.venv-web\Scripts\python.exe -m unittest discover -s tests/web -v
node .\work\check_web_adapter.mjs
node .\work\check_lens_math.mjs
& .\.venv-web\Scripts\python.exe .\work\check_lens_preview.py
& .\.venv-web\Scripts\python.exe .\work\check_web_workspace.py
& .\.venv-web\Scripts\python.exe .\work\check_web_foundation.py
& .\.venv-web\Scripts\python.exe .\work\record_lens_preview.py
# 用已安装 Pillow 的工具 Python 运行 work/encode_lens_recording.py，仅用于编码。
```

## 恢复与剩余任务

- 原文件来源检查点：`d445422` / `vendor: preserve audited Lens upstream runtime`。
- 完整本阶段：提交消息 `feat: integrate original Lens optics and comparison lab`，恢复标签 `stage6-1-complete`。
- 第四/五阶段 EXE 未重打包，SHA256 再次与历史记录相同：`3860B7359D386A7CAB1DD34C20C3E33ECDB939EC191C3769768BE94D8F58AA55` / `3B9EF7E6CAC7C1FAFA625E3EECEF0A50B9F61F7013848EEB1E2A338BFC5B9EE3`。
- 6.2 待确认：完整明暗/系统跟随、短主题转换、持久化/防白闪及 Qt/标题栏适配。6.3 待确认：按 82 项清单补齐适用效果和最终视觉一致性；上游搜索工厂接入时须保留现有 IME 保护。
- 7 真实后端全流程与安全 token；8 正式打包、真实多 DPI/跨屏/多设备/干净 Windows 与发行许可。当前没有正式新 EXE，没有文件撤销或崩溃续跑，外观仍为本次页面偏好。
