# 映序 UI/UX 重构进度

更新时间：2026-10-23。本文路径均相对项目根目录。

## 当前阶段及授权

- 最新授权：用户明确要求发布，并确认公开仓库 `mason2237/YingXu`，已完成设备登录授权；阶段 8d 已公开源码和 `v0.8.0-rc.2` 预发布版。取消干净 Windows 验收门槛，控制许可/测试范围。原创部分按用户明确选择采用官方原文 PolyForm Noncommercial 1.0.0，非商业使用，商业用途需单独授权。保留“余量不足先保存停止”和“少检查、少电脑控制”的约定。
- 主计划 `docs/DESIGN_PLAN.md`；接口约定 `docs/WEB_UI_MIGRATION.md`；本轮记录 `docs/STAGE8C_PUBLICATION.md`；公开步骤 `docs/PUBLISHING.md`。全部历史测试/阶段记录与 Git 提交保留。
- 阶段 4：变更预览、确认执行、结果和本地记录已实现；验证见 `docs/STAGE4_VERIFICATION.md`，代码恢复点 `d3db0fe` / `stage4-complete`。
- 阶段 3：匹配与审阅功能已完成；记录见 `docs/STAGE3_VERIFICATION.md`。
- 阶段 2：已完成。Qt 骨架、扫描预览、两种尺寸真实窗口、打包与 EXE 启动检查通过；恢复标签 `stage2-complete`。
- 阶段 1：已完成。核心、真实 GUI、打包及 EXE 启动检查通过；提交及恢复标签为 `stage1-complete`。
- 阶段 5：独立 Web 宿主、本地资源、双向通信、核心只读样本、验证和技术试包已完成；完整用户整理仍可使用第四阶段 Qt 工作台。
- 阶段 6：本地 Web 工作台、虚拟列表、候选/预览/记录、受控玻璃/粒子、可交互测试适配器已完成。只使用显式示例入口；真实文件接入和最终打包尚未实施。

## 8d：GitHub 公开发布（当前完成）

- 公开仓库：[mason2237/YingXu](https://github.com/mason2237/YingXu)；预发布版：[v0.8.0-rc.2](https://github.com/mason2237/YingXu/releases/tag/v0.8.0-rc.2)，2026-10-23 发布。三个资产为 Windows 完整运行包、对应源码 ZIP 和 SHA256SUMS。
- 从 8c 的干净源码 ZIP 建立独立仓库，初始公开提交 `71005b2245b3eb5d3ae1c6e50ef947d9db8e6b98`，对应原本地快照 `c3ea9a73eb569fd30eb87b5651fa14b6c4251767`；Release 标签固定在该初始提交。原仓库完整历史留在本地，未推送旧路径历史。
- 使用无登录凭据的公开请求确认仓库/Release 可见、`draft=false` / `prerelease=true`、标签提交正确、LICENSE 字节相同；GitHub 返回的两个 ZIP 及校验文件 SHA256 均匹配本地。未重新构建或改变应用代码，未重复既有应用测试，也未进行干净 Windows 系统测试。
- README 增加真实下载入口；发布结果见 `docs/STAGE8D_GITHUB_RELEASE.md`、`docs/evidence/stage8d_github_publication.json`。8c 的测试、输出 ZIP、旧提交及恢复标签完整保留。发布资产不因本次文档更新重新打包，校验值保持不变。
- 本地恢复提交消息 `docs: record public GitHub release`，标签 `stage8d-published`；公开仓库另追加发布链接和记录的文档提交，不移动 Release 标签。发布辅助脚本/状态只在被忽略的 `work/public-release/`，不包含明文凭据；认证由系统 Git Credential Manager 保存。
- 当前交付已完成。后续按用户新需求修改功能；维护公开仓库时从其 `main` 继续，勿将原开发仓库历史合并/推送过去。未实现撤销、EXE 未签名及非干净系统验证的边界不变。

## 8c：GitHub 基本发布准备（历史完成记录）

- 原创部分采用官方 PolyForm Noncommercial 1.0.0，根 LICENSE 不改条款，与官方文本 SHA256 相同。NOTICE 使用项目作者/贡献者的通用署名，不把提交工具名冒充版权人；第三方原有署名保持。
- 更新 README、运行包说明、依赖与 LGPL 库替换说明、Release 文案。明确当前 Windows 已验证、没有做干净系统测试；该项不阻塞本轮，也不继续追加跨屏/万级性能/签名要求。
- 许可检查发现旧默认 QML hook 收集整个 QML 树，带入未使用的 GPL/商业插件。项目 hook 限制 QtQml、QtGui、QtQuick 收集范围；拒绝额外 QML 树与 Charts/3D/Pdf/虚拟键盘等库。只调整打包，文件整理业务未改。
- 已收集 183 份原文/官方模块署名资料（含 125 份 WebEngine 第三方资料），记录来源与 SHA256；PyPI 官方明确 wheel 内容适用开源与商业两种授权，不能因只附商业文本而否认 LGPL。第三方 MIT/LGPL 权利独立保留，完整文本/源码入口/替换方法随包提供。
- 公开内容检查：当前文件中无检测到的密钥或开发机路径；不再跟踪两份生成 spec，磁盘文件保留。历史对象检查发现 62 处开发路径、未发现所检测格式的密钥。历史不改写；提供不含 .git 的干净源码 ZIP，公开时建议从它建立新仓库，避免带出旧路径。
- 版本 `0.8.0-rc.2`：保留 rc.1 和原 Git 恢复点。构建及最终 EXE 只补受影响的启动/通信/实际界面检查；57 项业务/后端/边界和真实整理闭环直接沿用已完成结果，不重复未受影响的测试。
- 本轮生成本地 GitHub Release 材料；不自动创建远程库、推送或公开 Release。恢复标签 `stage8c-public-ready`，提交消息 `release: prepare noncommercial GitHub source and Windows assets`。精确结果与输出位置见本轮记录。

## 8b：缩放与 EXE 候选包（历史完成记录）

- 新版 `0.8.0-rc.1` 独立 onedir 包，入口 `outputs/stage8-release/0.8.0-rc.1/YingXu/YingXu.exe`；完整目录 ZIP 与 SHA256 同级提供。旧 EXE、Qt 入口、19 个原 Lens 文件和业务模块保留。
- `scripts/build_web.py --release --zip`：只打入 53 个生产前端文件（QWebChannel 脚本由 Qt 内置资源提供），示例/诊断前端物理剔除，诊断 Python 后端和旧 UI 不进入发布归档；校验 WebEngine helper/资源/locales、静态资源哈希，生成版本、构建/许可清单和包内 SHA256。
- 修正窗口在高 DPI 下启动高度超出屏幕的问题，按可用逻辑区域限制初始/最小尺寸。真实 Qt 窗口完成 100/125/150/200% `QT_SCALE_FACTOR` 模拟、900×620、小窗详情/弹窗及最大化/最小化；无横向溢出，实际系统缩放和跨屏仍待外部设备验收。
- 千行真实扫描仅渲染约 12 行 DOM，End 可达末行；1000 视频+1 字幕扫描约 22.4s，50ms 页面心跳约 449 次、界面可响应。该数字是扫描/匹配/DTO总耗时，不是匹配算法或滚动帧率成绩。尚未完成万级真实匹配和稳态 CPU/GPU 性能认证。
- 32 项原业务、14 项后端、11 项边界检查通过；一次真实窗口闭环完成 3 份字幕整理、重复确认防重放、记录/独占导出和取消。新 EXE 在无 Python/Node 的子进程 PATH、独立临时工作目录启动，真实通信/页面可见/按钮与弹窗通过，JS 错误为空；测试使用临时回环检查端口并在退出时关闭，生产启动不启用该端口。
- 许可门槛：依赖元数据声明开源许可，但本机 Qt wheel 只附商业许可文本；Chromium 内置 credits 页加载失败。候选包保留原附件并明确记录缺项，未宣称可公开分发。干净 Windows、真实跨屏/DPI、完整 Qt/Chromium 许可材料和最终签名/发布仍为后续 8c。
- 恢复提交消息 `build: deliver isolated WebEngine release candidate and DPI checks`，标签 `stage8b-release-candidate`。详见本轮验收文档。电脑控制工具调用 0 次；未关闭用户可能正在使用的旧源码窗口。验收后再进入 8c，不自动跨阶段。

## 8a：全按钮玻璃与弹性/进度（历史完成记录）

- 页面内所有 button 自动获得统一玻璃材质；动态候选/记录/翻页/关闭/快捷操作同样覆盖。主操作、筛选和弹窗主操作复用原版 Lens GPU，小型/文字/图标按钮使用 CSS 玻璃并接原版 JellyController，不为每按钮分配画布。
- 每轴 12px 内拖动、形变、回弹；超过 5px 的真正拖动不触发点击，减少动态时也保留防误触。键盘与普通轻点保留原行为；人工确认与后端一次性凭证均未改变。
- 原版光学进度接真实 done/total，启用波纹/折射与完成状态；未知总量不伪报百分比。任务加载时暂停被遮住的雾气，结束停波纹；相邻停止/整理按钮保持红蓝语义。
- 定向真实窗口：40→59 个按钮全覆盖，反复弹窗 Lens canvas 最多 6（另有独立雾气），原生鼠标拖动/回弹/轻点、拖确认不改文件、真实 1/3 进度、减少动态与实际整理单批成功通过，控制台无错误。7 个 JS 语法、2 个 Python 编译、3 项来源检查通过，旧诊断/示例启动继续通过。电脑控制 0 次，未重复全面业务/DPI验收。
- 截图与 11 帧真实 GIF：`outputs/stage8a_*.png`、`stage8a_jelly_motion.gif`。详情见 `docs/STAGE8A_VERIFICATION.md`。原 19 个 Lens 文件和文件整理核心未改。
- 恢复提交消息 `feat: unify glass buttons jelly gestures and optical task progress`；标签 `stage8a-controls-complete`。效果需重启旧源码窗口后加载新增资源；未关闭可能正在使用的旧窗口。本轮不打包 EXE，等待用户验收再继续其余阶段 8。

## 阶段 7：真实工作台整合（历史完成记录）

- 默认 `run_web.py` 为真实本地工作台：选目录/扫描选项/递归扫描、原匹配及多语言候选、搜索筛选排序、人工关联/确认/跳过、冻结预览、一次性明确确认、实际整理/停止、结果/历史/独占 JSON 导出、按 ID 打开位置和复制名称。
- Python 持有原 ReviewPlan/快照/任务；生产白名单只接受稳定 ID 与版本，不接受任意路径/命令。生产 profile 拒绝 fixtures/诊断资产，页面刷新只恢复实际状态/结果，不重复文件操作。
- 修复审阅后列表 busy 未解除造成的变暗/鼠标失效；防止异步旧详情覆盖新筛选，恢复失败后的分页控件；路径读取提示可展开查看。
- 本轮：32 项原业务 + 14 项后端 + 11 项边界 + 8 项前端适配器通过，9 个 JS 语法和 3 个 Python 编译通过。真实窗口完成临时目录整理 3 份字幕、候选分页/人工确认、原生鼠标选行、明暗/窄屏、取消、重复点击、刷新结果、真实历史、导出防覆盖。诊断/现代示例两个保留入口继续通过启动检查；电脑控制调用 0 次。
- 实际截图 `outputs/stage7_workspace_light.png`、`stage7_workspace_narrow_dark.png`、`stage7_preview_light.png`、`stage7_results_light.png`。详细证据、首轮测试等待和 Chromium 合成诊断见 `docs/STAGE7_VERIFICATION.md`。
- 保留入口：`run_web_foundation.py`（诊断）、`run_web_preview.py`（显式示例）、`run_preview.py`（原完整 Qt 工具）。原 19 个 Lens 文件、核心文件处理模块、既有 EXE 未改；本轮不打包 EXE。
- 恢复提交消息：`feat: connect real local web workspace and guarded file workflow`；标签 `stage7-complete`。下一步阶段 8：视觉/性能细修、真实 DPI/跨屏/设备验证、开发资源物理剔除与正式 EXE，等待用户确认。

## 阶段 7：后端与接入草稿（2026-10-22 历史检查点）

- 后端恢复点：`26316d3` / `stage7-backend-checkpoint`。严格接口、单后台任务、真实扫描/审阅/冻结预览、一次性确认、防重复执行、取消/停止、真实结果/历史/独占导出已实现。原 core/review 只补可选进度/取消钩子，原文件执行算法沿用。
- 已保存未启用草稿：WebWindow 的 workspace 模式、原生选目录/拖入/复制/打开位置/导出、安全关窗；共享 QWebChannel、LocalAdapter、真实工作台控件及 CSS。前端 workspace/store/dialogs 仍使用示例逻辑，禁止把 workspace=True 当成可交付入口。
- 可运行入口保持：`run_preview.py`（完整真实 Qt 工具）、`run_web_preview.py`（现代 Web 示例）、`run_web.py`（Web 通信诊断）。`run_web_foundation.py` 预留诊断独立入口；下次完成前端后才切换默认入口。
- 当前检查：14 项后端、11 项通信边界、5 个 JS 语法和 7 个 Python 编译通过；诊断/现代示例两个真实窗口启动、QWebChannel 和控制台检查通过。原 32 项业务在本轮后端检查点已通过。精确续接步骤写在 `docs/STAGE7_PROGRESS.md`。
- 本恢复点标签为 `stage7-ui-checkpoint`，不标记 stage7-complete；本轮不打包 EXE。电脑控制工具调用 0 次。

## 6.3b 工作台反馈与快捷操作（历史完成记录）

- 新增 Ctrl+K 快捷操作：搜索、状态筛选、候选字幕、跳过/恢复、预览、记录、外观及示例切换共 12 个实际动作；支持中文输入保护、方向键/Home/End、Enter 和禁用状态。输入只用于筛选固定动作，不执行命令。
- 从固定上游 Overture 定向改编通知、命令列表、提示和 Drawer 运动。通知有进入/退出、计时线、指针/焦点/隐藏暂停、成功/错误语义；位于原生 top layer，关闭候选弹窗后仍能显示。没有加入虚构的文件撤销。
- 使用未修改的 Lens `createOpticalProgress` 显示适配器实际 done/total，未知总量只显示读取状态；空目录/读取错误的初始总量已纠正。没有用定时器增加进度，也没有额外分配 WebGL 画布。
- 窄窗口将同一个详情节点移入原生模态抽屉，保留原按钮及 GPU 对象；Tab 不进入背景，Escape 关闭并还原节点/焦点。宽窗口仍并列显示详情。图标提示可通过键盘聚焦显示。
- 统一候选/预览/记录浮层、空/错/搜索无结果提示；记录按提供的成功/跳过/异常数量绘制分布，并保留原错误原因。顶部流程随准备/审阅/预览更新。浮层打开时暂停背景烟雾和粒子。
- 必要检查：8 个修改 JS 文件语法、Python 编译、4 项雾气调度检查通过；一个定向真实窗口脚本通过快捷操作/IME、候选通知、21 次实际进度更新、10,000 条示例、筛选空状态、窄屏焦点/还原、深色及减少动态。未重跑全套业务/GPU/DPI 回归，电脑控制工具调用 0 次。
- QtTest 的鼠标坐标未命中原生通知 popover；悬停暂停按明确的指针进入/离开事件验证，另验证了 DOM 键盘焦点暂停，不宣称完成了人工鼠标体感验收。截图采集增加短等待，避开入场动画中的未合成画面。
- 代码：`workspace-feedback.js`、`workspace-overlays.js`、`feedback.css` 及工作台/弹窗/资源适配；详细文件与限制见 `docs/STAGE63B_VERIFICATION.md`。浅色快捷操作、候选、通知、结果及深色窄屏截图在 `outputs/stage63b_*.png`。
- 恢复点：提交消息 `feat: unify workspace feedback and quick actions` / 标签 `stage6-3b-complete`。原 19 个 Lens 文件和 Python 文件操作模块未修改；网页仍只注册 appearance，执行真实整理仍禁用。
- 下一阶段为 7：将真实目录/扫描/审阅/冻结预览/确认执行/记录接入现有 Python，保留安全检查与不覆盖机制。阶段 8 再进行全面性能、真实 DPI/设备和正式 EXE；6.3a 所记深色帧率限制仍存在，本轮未重新测量帧率。

## 6.3a 材质修订：轻雾、光丝与薄玻璃（历史完成记录）

- 去掉鼠标带动整片旋转、按行切开的浓雾；改成连续向上飘散的细雾，稀疏断续、柔和消散。局部加入光丝与光晕，仍在文字下方，共用原雾气画布。选中色面减弱，原左侧选中标记保留。
- 雾气噪声每像素从 16 次降为 5 次，移除三角函数哈希；绘制尺寸由 0.8 倍改为 0.5 倍，像素数约减少 61%。调度从约 30 提至 60 次/秒目标，累计时间预算适配不同刷新率；悬停插值按时间计算。空闲/隐藏/减少动态的停止规则保留。
- 顶部目录栏减小内边距和折射/色散，弱化整层光学不透明度与描边、换用低对比背景；取消整条工具栏的按压形变，按钮仍用原版 Lens。其他主操作按钮的增强材质保留。
- 按“少检查”仅做修改文件语法检查和短实际窗口查看；首轮发现亮边/测量问题后补看一次，没有运行整套 80 项回归。最终短采样：浅色约 **50.4**、深色约 **37.5** 次雾气绘制/秒，控制台无错误；不宣称稳定 60 FPS 或显示器实际呈现帧率。
- 最终截图 `outputs/stage63a_refined_light.png` / `stage63a_refined_dark.png`。说明及限制见 `docs/STAGE63A_REFINEMENT.md`；短查看脚本 `work/preview_material_refinement.py`。未使用电脑控制工具，未新增依赖。
- 恢复点：提交消息 `perf: lighten vapor and toolbar optics`，标签 `stage6-3a-refined`。待办：用户确认后再按原计划处理 6.3b、真实文件整合 7、发布 8；深色尚未稳定达到 60 次/秒，不扩展为全面性能排查。

## 6.3a 气态列表与液态操作按钮（原始交付记录）

- `list-mist.js` 为项目自写的程序化雾气 shader：全列表共一个低分辨率画布，位于文字和虚拟行下方；行内雾气、悬停聚拢、选中反馈。普通行弱化、雾气不透明度封顶，文字不模糊。不是 Lattice 源码或物理流体模拟。
- `liquid-actions.js` 用未改动的原版 Lens 为“更换/确认字幕、跳过/恢复、预览变更”提供折射、高光与弹性。每个操作组共用画布，按真实按钮边界裁切；当前工作台四个 Lens 画布 + 一个雾气画布，10 个玻璃表面，无每行/每按钮新增上下文。
- 详情底部两个真实按钮保持 DOM 身份；标签、主次状态和业务回调随当前选中项更新。连续 25 次选择后手势 body 仍为 2，避免节点替换积累 GPU/手势对象；不修改文件处理逻辑。
- 外观新增 `mistEnabled` 严格布尔偏好，默认开启，原五字段设置兼容恢复；固定 appearance/v1 现为六字段，不新增原生方法或文件权限。雾气与玻璃可独立关闭，系统/手动减少动态时静态且无指针流动，空闲/隐藏/最小化停帧，WebGL 不可用返回普通列表/按钮。
- 顺带修复切换示例后旧“0 条载入”通知残留的问题；新载入开始清理上一条通知。
- 原业务 32 + Web/来源/外观 24 + 适配器 8 + Lens 数学/PCM 7 + 主题原语 5 + 雾气调度 4，共 **80 项**通过；新材质、原工作台和主题三组真实窗口检查通过。调度覆盖 60/120/144/240Hz 时间戳、停帧和长帧限幅；原版 19 文件 SHA 未变，阶段 4/5 EXE 哈希未变，电脑控制工具调用 0 次。
- 实际截图 `outputs/stage63a_final_light.png`、`stage63a_final_dark.png`，另有按压、最小窗口和无 WebGL 回退；真实 QTest 录制 `outputs/stage63a_materials.gif`。详情和限制见本阶段验收记录。
- 当前沙箱不能正常启动 WebEngine，默认临时位置也影响 QSettings；测试环境改用 work/test-results 内临时目录，GUI 经批准在正常桌面运行。没有为通过检查关闭 WebEngine 安全功能或改应用存储策略。
- 恢复点：提交消息 `feat: add vapor list and liquid glass actions` / 标签 `stage6-3a-complete`。下一步等待本轮视觉验收，再评估 6.3b 剩余适用效果；真实 Python 文件整合 7、正式 EXE 8。

## 6.2 明暗主题与转换（完成记录，后续材质按 6.3a）

- 顶部快速选择与外观面板提供浅色 / 深色 / 跟随系统，共享同一状态。`QSettings("YingXu", "SubtitleOrganizer")` 的 `appearance/v1` 只保存五项外观偏好；默认 system、增强、玻璃/粒子开启、手动减少动态关闭。系统减少动画始终优先。
- 新 `yingxu/web_ui/appearance.py`：严格白名单、布尔/枚举校验、原子拒绝非法请求、保存失败提示、损坏设置回退、重复设置不重复发信号。网页只注册 `appearance.getState/update/changed`，没有目录、文件任务、任意命令或阶段 5 的业务 bridge。
- `DocumentCreation/MainWorld` 在 HTML/CSS 首次显示前应用主题；刷新前保持最新注入，WebEngine 页面背景、Qt 窗口 palette 与 Windows DWM 标题栏同步。QStyleHints 只观察系统，不覆盖或更改 OS 偏好。
- `tokens.css` 及阅读/弹窗/状态/通知/焦点/禁用/滚动条语义化；原 19 个 Lens 文件未修改。适配层同步绘制深浅背景并使用原版 ocean/grid 的 shader 暗色染色开关。开发页四种原场景仍保留源配色，旧简化列保留浅色基线。
- `theme-transition.js` 定向改编固定上游 Overture 的 transition/focusPoint：760ms 缩为 180ms；快速连续切换可取消，减少动态/隐藏/不支持时即时切换；不清空搜索、选中、人工审阅或弹窗。
- 修复验收发现的问题：Qt 6.12 的 scripts.find 返回列表；PySide 自动发布未装饰绑定方法会扩大 bridge 表面，改为私有事件转接；VT 快照阶段暂停 rAF，改用同步 GPU 配色绘制；取消时清理 VT 类；浅色选中行辅助文字对比度不足已调整。
- 检查：原业务 32 + Web/来源/外观 23 + 适配器 8 + Lens 数学/PCM 7 + 转换原语 5 = **75 项通过**。真实 Qt/WebEngine 工作台、18 原版组件、阶段 5 通信、6.2 主题检查均通过；所有偏好检查使用临时 INI。11 类实际阅读文字抽样：浅色最低 4.72:1，深色最低 5.32:1，未据此宣称完整无障碍认证。
- 真实窗口截图 `outputs/stage62_workspace_dark_final.png` / `stage62_workspace_light_final.png`、外观弹窗、最小窗口、明暗材质对照及带原生标题栏的 `stage62_native_*.png`。本轮电脑控制工具调用 0 次，未新增运行依赖，未重打包。
- 真实主题转换录制 `outputs/stage62_theme.gif`：41 帧、约 3.57 秒，包含静置和三次 180ms 转换；采集/编码脚本随本次代码保存，PNG/GIF 为可再生成的忽略产物。
- 完整恢复点：提交消息 `feat: add persistent light and dark appearance` / 标签 `stage6-2-complete`。阶段 4/5 EXE 保持原哈希；历史恢复点保留。
- 待办：等待本轮验收；6.3 覆盖余下适用效果和整体视觉；7 真实文件接口整合；8 DPI/设备兼容及正式 EXE。
- 限制：系统变化用原生事件受控模拟，未切换用户 Windows 设置；DWM 设置接受且标题栏截图确认，本机不支持 caption 属性读取；尚未做多显卡、全部 DPI、干净 Windows 或人工试听认证。Web 页仍为明确标识的示例。

## 第六阶段补充（r3.2，6.1 完成记录；用户已选择增强）

- 原版源码检查点 `d445422`：Lens 19 个 ES module/CSS 原文件的 Git blob SHA 与固定提交逐个一致；ORIGIN、完整 MIT、来源与 LF 规则齐全。原 `stage6-complete` 保留。
- 新入口 `run_effects_preview.py`，比较旧简化 / 原版 Thick / 增强适配；18 类原版工厂全部可交互，另有 4 种原版背景、弹窗内玻璃、强度/关闭/减少动态和默认关闭的原版音效。工作台 `run_web_preview.py` 的目录栏、按钮和状态筛选已使用原版材质/手势。
- 原始 19 文件未改，Qt 生命周期、材质选项、绘制计数及业务回调集中在 `lens-runtime.js` / `upstream-effects.js`。目录控件共享一个画布；普通隐藏保留少量上下文，销毁时释放程序/纹理/缓冲并交给 WebEngine 清理画布，解决强制丢失时的原生 mailbox 警告。
- WebGL 丢失恢复须延后事件结束，适配层延迟 150ms 使用丢失前缓存的扩展；自动检查验证丢失后恢复、无 WebGL 时普通材质、最小化/空闲停帧及资源登记归零。
- 全量清单 82 项：Lens 18 控件 + 4 展示组合、Lattice 14、Overture 46；逐项来源、当前采用/待适配/可选展示/未采用具体理由，另列跨组件光学、声音与运动原语。尚未采用项没有冒充已接入。
- 最终检查：原业务 32 + Web/来源 14 + 前端适配器 8 + 原版材质/物理/PCM 7，共 61 项通过；原版目录/工作台/第五阶段通信的真实 WebEngine 检查通过。未新增运行依赖，未执行上游构建脚本，未改业务模块或原 EXE；本轮电脑控制工具调用 0 次。
- 实际截图 `outputs/stage61_comparison.png`、`stage61_workspace.png`、`stage61_drop_select.png`、`stage61_xy_lens.png`、`stage61_dialog.png`、`stage61_ocean.png`、宽窄/异常等；54 帧真实 Qt 输入/窗口录制 `outputs/stage61_motion.gif`，约 6.44 秒。截图/录制为可再生成的忽略产物。
- 10,000 行最后观测：8 个行 DOM，一次可见行渲染约 3.3ms，示例构造约 115.6ms，JS 堆粗采样约 23.1MB；搜索约 281ms 含防抖和检查等待，不代表真实扫描/全进程内存性能。
- 完整交付提交消息 `feat: integrate original Lens optics and comparison lab`，恢复标签 `stage6-1-complete`。本阶段不打包 EXE，核心与第四/五阶段 EXE 哈希保持相同。
- 下一步 6.2 待用户确认：完整浅色/深色/系统跟随、短主题转换、偏好保存/防白闪和系统标题栏；当前背景场景选择不是完整明暗主题。6.3 再补齐余下适用效果；7 接入真实文件；8 正式发布。
- 已知范围：声音仅验证原版 PCM 和默认静音，未人工试听；GPU 故障为程序模拟，本机结果不能替代多显卡/DPI/干净 Windows 认证；外观偏好尚未持久化，页面为显式示例且不注册文件操作 bridge。

- 核对结论：`ad1f299` 只采用上游 focus/modal，玻璃与粒子为本项目自写，尚未移植 GitHub Lens 玻璃源码。用户认为效果不明显，原视觉方向尚未验收。
- 6.1：全量审查 Lens/Lattice/Overture 的效果和组件，输出采用清单与未采用项的具体原因；优先复用原版渲染/材质/手势及成熟组件，制作原版/现有/增强效果对照。
- 6.2：浅色/深色/跟随系统，统一 CSS 与 GPU 配色、切换过渡、初始防白闪、本地偏好恢复和 Qt 适配；保持选中、搜索和审阅状态。
- 6.3：将清单适用项补齐到工作台，验证明暗/窗口/大列表/停帧/回退，提供截图及动效演示后等待验收。每步独立检查、更新文档、Git 提交并暂停。
- 复用范围扩大到玻璃/光学、弹性/吸附、流体选中/状态反光、进度/完成、通知/菜单/焦点、可选粒子与声音；具体可用性以源码和本地检查为准。声音如接入则默认关闭，缺少业务入口的效果只在开发验收页展示。
- 工作方式：优先源码、工具/API 和可重复自动化检查；电脑控制仅留必要 Windows 原生交互及最终少量视觉抽查，不重复手动遍历。
- 计划轮历史：只变更三份计划文档，未运行 GUI/业务回归；恢复提交 `d3ac91a` / `docs: expand upstream effects and theme plan`。6.1 的实现与检查结果以上述记录为准。

## 第六阶段骨架（已完成基线，视觉待补充验收）

- 新入口 `run_web_preview.py`；运行 `& .\.venv-web\Scripts\python.exe .\run_web_preview.py`。默认 `run_web.py` 仍是阶段 5 技术入口，原 `run_preview.py` 仍提供完整真实整理。
- `frontend/workspace.html`、三份 CSS、store/model、列表/详情/弹窗/效果组件形成独立工作台。视频主文字 15px、字幕 13px，文件类型与状态固定列，扩展名保留，完整名称/路径按需查看。
- 搜索/组合输入保护、状态与类型筛选、排序、稳定选中、上下/Home/End/Page 键、候选对比、人工指定/确认、移除关联、跳过/恢复、变更分页预览、复制名称、示例结果/记录均有实际行为。详情底部固定操作区；窄窗口切换为详情浮层。
- `frontend/js/preview/` 提供匹配/10,000 行/空目录/无字幕/读取失败等结构化场景；路径仅为显示文字。宿主不向该页面注册 QWebChannel，所有 `organize.*` / `file.*` 操作被拒绝；最终执行按钮始终禁用并解释原因。
- 局部 WebGL2 玻璃仅折射程序生成的装饰背景，文字保持 DOM；悬停按需绘制、按压约 180ms。16 个短粒子约 650ms；效果开关、系统/手动减少动画、空闲停止、最小化停帧和普通材质回退均设有检查。
- 小范围采用 MIT 参考代码：Lens 的 focus helper 原样复制，Overture modal helper 定向改写。上游固定提交、逐文件来源及完整许可见 `frontend/vendor/design-systems/`、`THIRD_PARTY_NOTICES.md`；未执行上游脚本、未引入远程资源/字体/大型框架。
- 原 32 项、Web 边界 11 项、适配器 8 项全部通过；实际工作台检查覆盖宽窄/最小/最大化、键盘、原生点击复制及剪贴板结果、候选确认、筛选、预览、空/错状态、10,000 行、效果开关/回退/停帧。阶段 5 真实通信/任务/刷新/关闭回归也通过。
- 使用 computer-use 实际点击待确认筛选、打开候选、Escape 返回并观察焦点、打开外观设置和 Ctrl+R 恢复初始预览。截图 `outputs/stage6_workspace.png`、`stage6_candidates.png`、`stage6_preview.png`、`stage6_narrow.png` 等来自实际 Qt/WebEngine 窗口。
- 恢复点以提交消息 `feat: introduce Web subtitle review workspace` / 标签 `stage6-complete` 定位。本阶段不重新打包，阶段 4/5 EXE 保留。
- 剩余：第七阶段用真实 Python 适配器替换示例，接入目录/扫描/多语言/冻结计划/一次性确认 token/执行/结果/导出，逐项比较原行为；第八阶段进行真实 DPI/跨屏/驱动/内存 CPU/干净机与正式 EXE 验收。
- 已知边界：外观偏好仅本次页面有效；刷新/切换示例会重置示例审阅。10,000 行测试是前端展示测试，不代表真实扫描性能。驱动丢失用事件模拟，不能代替不同 GPU 设备验收。生产发行必须排除示例入口/数据/只读调试统计。

## 第五阶段（已完成基线）

- 新入口 `run_web.py`；新增 `yingxu/web_ui/` 的资源/窗口、协议、桥接、任务服务与样本 worker，以及 `frontend/` 的本地 HTML/CSS/ES modules。
- 独立 `.venv-web` 使用官方 PySide6/Qt 6.12.0，WebEngine/Pdf 包为 6.12.0.140，Chromium 140.0.7339.225；完整锁定在 `requirements-web-lock.txt`，原 `.venv` 与依赖保留。
- 白名单仅含 app.hello / app.state / app.ping / diagnostics.runSample。只调用程序临时样本，不接入用户文件操作；同源资源、CSP、远程拦截、会话/重复请求校验、后台任务及刷新/关闭生命周期已实现。
- 原 32 项回归和新增 11 项边界检查通过；实际 WebEngine 流程检查通过中文回声、后台事件、3 份字幕目标、样本字节不变、宽窄窗口、外部导航阻止、普通/运行中刷新及延后关闭。
- 原 `.venv` 的 `work/check_preview.py` 通过；原 core/review/operations、Qt UI 与第四阶段 EXE 保留，哈希与既有记录相同。
- 使用 computer-use 检查源码和技术 EXE 的实际页面与按钮；技术 EXE 已显示本地页面并返回 Python 样本结果。截图为 `outputs/stage5_initial.png`、`stage5_sample.png`、`stage5_narrow.png`。
- 技术包：`outputs/stage5-tech/YingXuWebFoundation/YingXuWebFoundation.exe`；需保留整个目录，588,274,479 字节。主 EXE 哈希、辅助进程/资源及本机一次启动记录见验收文档。
- 打包首次发现宿主 PATH 引入 Poppler ICU，导致 QtCore 导入失败；构建脚本现在隔离子进程 DLL 搜索环境，重建后通过。可选 QML 插件的构建警告和包体优化留到正式发布。
- 恢复点通过提交消息 `feat: introduce local WebEngine foundation` / 标签 `stage5-complete` 定位。后续只在用户确认后进入第六阶段。

## 已确认的视觉补充（r3.1，历史约定）

- 第六阶段制作局部液态玻璃：顶部工具栏、浮层、选中控件加入轻折射、高光与按压反馈；文件列表保持清晰稳定。
- 粒子用于空状态或整理完成时的短暂反馈，低密度、可关闭；支持减少动画、普通材质回退和空闲停帧。
- 第六阶段实际运行验收效果及强度，第八阶段统一打磨。第五阶段架构范围不变。
- 本次只修改三份计划/进度文档；应用代码与依赖不变。提交消息：`docs: record approved glass and particle direction`。

## Web UI 架构与参考仓库审查（历史，仅文档轮）

- 核实当前核心 `core.py` / `review.py` / `operations.py` 独立于 GUI；保留前四阶段代码、入口、测试和 EXE，新增独立 Web 宿主与适配层。
- 推荐 PySide6 + QWebEngineView + 原生 HTML/CSS/ES modules + QWebChannel；参考仓库未使用 React/Vue，不需要为它引入大型前端框架。
- 参考仓库固定提交 `7a424c93b9be13cf835b91ea67495fec2ec0584e`，包含 Lens/Lattice/Overture。代码 MIT，需保留版权/许可；字体另有 OFL，图像等素材不能仅凭仓库 MIT 一概确认。优先系统字体与小范围 DOM/CSS 复用；具体证据见审查文档。
- 上游明确按原样提供且不积极维护；Lens flat 仍含玻璃，演示表格不是大数据组件。需要针对字幕工作台适配，不能直接整站嵌入。
- 新增方案要求 Python 持有审阅版本、稳定 ID、冻结计划、一次性执行 token 与任务互斥；页面刷新/重复点击不能直接再次调用 run_batch。当前 Qt 确认机制不能原封不动转成公开 bridge。
- 本地依赖探测确认 `.venv` 缺少可导入的 QtWebEngineWidgets / QtWebChannel；未来使用独立 `.venv-web`，保持旧环境可运行。本轮未安装包、未执行第三方脚本。
- 核对阶段四 EXE 大小和 SHA256 与原记录完全相符；本轮没有重新启动 GUI 或重跑 32 项回归，历史验证不冒充本轮测试。
- 本轮修改范围：`docs/DESIGN_PLAN.md`、新增 `docs/WEB_UI_MIGRATION.md`、`PROGRESS.md`；未修改业务代码、依赖、构建或测试。
- 文档差异检查、UTF-8 读取与本地 Markdown 链接检查通过；独立只读复核后补强 token 与唯一快照绑定及重复请求参数校验。以提交消息 `docs: plan staged WebEngine UI migration` 定位本轮计划恢复点。
- 审查时遗留：阶段 5–8 全部待实施；其后阶段 5 已按上文完成，正式许可清单和发布验收仍需后续实施。

## 方案 r3.1（阶段 5–6 已完成，阶段 7–8 待确认）

| 阶段 | 范围 | 验收边界 |
| --- | --- | --- |
| 5 | 新 Web 宿主、隔离依赖、本地资源、受限通信、最小页面与核心只读调用 | 双向通信、离线启动、旧版回归、技术试包；不做完整 UI 或文件执行 |
| 6 | 现代工作台、组件适配、结构化数据与前端交互 | 宽窄窗口、完整状态、键盘/大列表、真实截图；不最终打包 |
| 7 | 接入原 Python 全流程与安全状态管理 | 真目录操作、新旧一致、不覆盖、防重复、结果/记录/导出；撤销仍独立评估 |
| 8 | 视觉细修、DPI/跨屏、性能与正式 Windows 发行 | 实际系统缩放、干净机、WebEngine 资源、离线 EXE、许可/构建/截图 |

每阶段验证、更新文档、独立 Git 提交后汇报并等待确认。原 r2 阶段 5 的视觉/DPI/发布任务顺延到 r3 阶段 8，旧验收记录中的编号保留作历史。

## 第四阶段（已完成基线）

- `yingxu/operations.py` 在用户打开最终预览时冻结源、目标与文件标记；确认后对整批进行执行前复核，目标被占用、文件变化或消失则阻止执行并要求重新扫描。
- 文件执行模块只使用冻结目标名；Windows 同卷移动不覆盖已存在的目标，跨卷时以独占创建复制并在复核后删除源文件。权限失败逐项报告；停止请求在当前文件完成后生效。
- 最终预览按视频分组显示每份字幕的源文件、目标名称、目录变化和状态。存在低可信待确认项目时不能执行，确认按钮还要求用户勾选已核对。
- 结果弹窗汇总成功、无需变更、跳过/未匹配、异常及未执行，支持 JSON 导出；本地记录保存到 `%LOCALAPPDATA%/YingXu/history.jsonl`，工作台可查看最近 30 次。
- 32 项纯 Python 回归通过；真实 Qt 窗口完成扫描、确认、3 份字幕实际整理、结果与记录、导出，以及预览后目标被占用的阻止检查。原阶段二、三窗口流程重新通过。
- 截图：`outputs/stage4_workspace.png`、`stage4_preview.png`、`stage4_result.png`、`stage4_history.png`、`stage4_blocked.png`。
- 第四阶段 EXE 位于 `outputs/stage4/YingXuSubtitleOrganizer.exe`，39,547,039 字节；主窗口启动与关闭通过，SHA256 见 `docs/STAGE4_VERIFICATION.md`。
- 恢复点：执行安全模块独立提交 `48bb52d`，完整阶段标签为 `stage4-complete`。
- 安全撤销经评估暂不加入本阶段：可靠撤销需要记录执行后文件身份，并在恢复前逐项检查当前目标与原路径占用；当前优先完成已验证的整理闭环，不提供无安全检查的撤销按钮。
- 剩余：按 r3 完成 Web 架构/界面/整合，阶段八统一细修、DPI、性能与正式发布。异常退出时正在执行的批次可能来不及写完批次记录，应以重新扫描核对磁盘实际状态。

## 第三阶段（历史记录）

- 新增 `yingxu/review.py` 内存审阅计划：沿用原 `build_plan` 一对一匹配作为初始结果，再按显式语言标签自动关联不同语言字幕；同一字幕只分配一次，未知/重复语言保留候选。
- 候选人工指定、更换、添加语言、移除、确认、跳过/恢复只修改内存计划；目标名每次重算，沿用现有 `destination_for` 冲突编号规则。
- Qt 工作台接入搜索、状态筛选、表头排序、稳定选中、候选评分/集数冲突提示、文件夹拖拽扫描和扫描取消反馈。
- `review.py` 及 5 项独立回归先行提交 `988a7f0`；核心原有 15 项用例仍通过。
- 阶段三 Qt 窗口集成检查覆盖上述交互及媒体内容不变；截图 `outputs/stage3_review.png`。仍保留阶段二原图与 EXE。
- 阶段三运行：`& .\.venv\Scripts\python.exe .\run_preview.py`；检查：`& .\.venv\Scripts\python.exe -m unittest discover -s tests -v`、`& .\.venv\Scripts\python.exe .\work\check_review.py`；构建：`& .\.venv\Scripts\python.exe .\scripts\build.py --stage 3`。
- 当前阶段的 Git 提交与恢复标签为 `stage3-complete`；EXE 路径为 `outputs/stage3/YingXuSubtitleOrganizer.exe`。
- 阶段三 EXE 为 39,431,908 字节，实际主窗口启动及关闭通过；SHA256 见 `docs/STAGE3_VERIFICATION.md`。
- 此项为阶段三完成时的记录；阶段四现已提供最终预览、执行和结果记录。人工审阅仍随重新扫描清空，执行记录会独立保存。

## 第二阶段参考版（历史记录）

- 基于 Beautiful UI 的记录表、Component Gallery 的表格/折叠模式、Transitions.dev 的面板展开思路，以 Qt 原生实现；没有导入网站代码或新增网页运行时。
- 调整目录栏的名称/路径层级；列表视频文字增至 12pt；辅助字和按钮增至 10.5pt；状态增加色点并保留文字。
- 增加整行悬停、复制成功图标、160ms 文件位置展开动画；支持快速反向与 Windows 关闭动画设置。
- 真实 Qt 窗口集成检查通过，包括扫描、宽窄窗口、键盘、复制、空状态、路径错误及新增动画反向/禁用检查；测试样本媒体内容没有变化。
- 原阶段二截图和 EXE 保留，参考版截图为 `outputs/stage2_refs_*.png`，EXE 为 `outputs/stage2-refs/YingXuSubtitleOrganizer.exe`。
- 参考版 EXE 构建成功，39,415,543 字节；已独立启动主窗口并正常关闭。
- 构建增加 `--variant refs`；截图前设置 `$env:YINGXU_CAPTURE_PREFIX = 'stage2_refs'`，其他运行命令沿用下文。
- 恢复标签：`stage2-reference-preview`；完整参考来源、验证与产物校验见 `docs/STAGE2_REFS_VERIFICATION.md`。
- 此项为阶段二历史交付；用户随后授权进入阶段三。

## 方案 r2（历史约定，阶段 5 已被 r3 替代）

| 阶段 | 本阶段重点 | 确认点 |
| --- | --- | --- |
| 2 | PySide6 布局/设计系统、可运行列表与详情、真实扫描预览 | 验收字号、空间、窄窗口与流程；提供真实截图及试打包 |
| 3 | 搜索/排序/人工调整；优先新增拖拽目录、候选对比、多语言匹配 | 保持布局稳定，逐项验证匹配关系与目标名，媒体文件不变 |
| 4 | 变更预览/确认执行/结果、本地操作记录；可选安全撤销 | 文件安全与记录一致；撤销单独验证冲突与身份检查 |
| 5 | 功能完整后的统一视觉细修、缩放/DPI、性能和最终打包 | 完整状态与发布 EXE 验收 |

- 阶段 2 为搜索、候选、多字幕和结果/历史预留结构，不提前实现完整新增功能。
- 拖拽先支持文件夹，复用扫描入口；混合文件导入暂不列入基础范围。
- 多语言是一对多模型变更，阶段 3 独立提交并回归，不混入样式改动。
- 安全撤销为阶段 4 可选增强；先保障预览、执行、记录闭环。
- 方案修订记录：`c35c598`；第二阶段按 r2 实施。

## 第二阶段已完成

- 独立 `.venv`：PySide6 Essentials / shiboken6 6.8.3；构建环境完整锁定到 `requirements-stage2-lock.txt`。
- 新入口 `run_preview.py`；旧入口 `run.py` 和旧 EXE 保留。
- `yingxu/qt_ui/design.py`：统一字体、颜色、控件状态、SVG 图标；参数见 `docs/UI_SYSTEM.md`。
- `model.py`：只读 Qt 表模型与双行绘制；`VideoRecord.subtitles` 为后续多语言预留结构。
- `worker.py`：后台线程使用现有 core 读取文件和生成计划，不修改媒体文件。
- `window.py`：目录/扫描选项、列表、可伸缩详情、完整名称/路径、复制、打开目录、空状态、扫描状态和路径错误。
- 1240×840 和 1000×700 实际窗口已检查：窄窗口收起详情，可按需展开；列表无横向滚动。
- 核心 15 项回归通过；Qt 集成检查通过真实扫描、上下键选择、复制、选项失效重扫、空目录/无字幕/无效路径和扫描中关闭；临时样本内容不变。
- 在受限环境中遇到剪贴板间歇性为空，改在真实交互桌面复核通过；GUI 测试需在可访问系统剪贴板的环境运行。
- 试打包产物：`outputs/stage2/YingXuSubtitleOrganizer.exe`，39,318,071 字节；主窗口“映序 · 字幕匹配预览”启动并正常关闭。详见 `docs/STAGE2_VERIFICATION.md`。

## 第二阶段运行命令

```powershell
& .\.venv\Scripts\python.exe .\run_preview.py
& .\.venv\Scripts\python.exe -m unittest discover -s tests -v
& .\.venv\Scripts\python.exe .\work\check_preview.py
& .\.venv\Scripts\python.exe .\scripts\build.py --stage 2
& .\work\check_packaged.ps1 -Executable .\outputs\stage2\YingXuSubtitleOrganizer.exe
```

截图：`outputs/stage2_initial.png`、`stage2_scanning.png`、`stage2_wide.png`、`stage2_narrow.png`、`stage2_narrow_details.png`、`stage2_empty.png`。
这些是实际窗口截屏，扫描数据来自临时文件夹；截图中的临时路径在测试结束后已清理。

## 第一阶段已完成（历史基线）

- 初始化本地 Git，原始版本提交 `476d6ab`，标记 `pre-refactor-baseline`。
- 原 EXE 与截图保留，原 EXE 校验值见 `docs/BASELINE.md`。
- 原样分离扫描、匹配、集数解析、目标命名到 `yingxu/core.py`，不依赖 GUI。
- Tkinter 界面及确认/执行流程位于 `yingxu/legacy_ui.py`，当前阶段保留原界面。
- 建立 `run.py` 和原文件名兼容入口；建立可跨工作目录定位的构建脚本。
- 建立 15 项核心行为用例，提取前和提取后均通过。
- GUI 检查使用真实扫描/执行线程，覆盖筛选、跳过恢复、人工确认、取消确认、重命名、预览后冲突阻止覆盖。
- 补充 README、直接开发依赖版本、设计计划和已知限制。
- 对比基线源码的 AST：8 个核心函数体完全一致，UI 类仅调整资源图标的定位路径。
- 新 EXE 已构建并检测到主窗口，随后正常关闭。原 EXE 的 SHA256 保持不变。

## 第一阶段启动和验证（历史基线）

在根目录使用 PowerShell：

```powershell
$YingXuPython = (Get-Command python).Source
& $YingXuPython .\run.py
& $YingXuPython -m unittest discover -s tests -v
& $YingXuPython .\work\check_upgrade.py
& $YingXuPython .\scripts\build.py
& .\work\check_packaged.ps1
```

- 实际环境：Windows，Python 3.12.0，PyInstaller 6.17.0，Pillow 12.3.0。
- 旧版运行无需 pip 依赖。新版 Qt 需要 `requirements-qt.txt`；当前安装在独立 `.venv`。
- GUI 测试：通过，窗口 1240×840，列表高 180；截图 `outputs/stage1_ui.png`。此截图是基线运行证据，不是新版设计。
- EXE 构建/启动：通过，11,535,349 字节；独立检测主窗口并正常关闭。完整记录见 `docs/STAGE1_VERIFICATION.md`。

## 恢复与提交

- 阶段 2 提交消息：`feat: introduce Qt workspace`；使用 `git rev-parse stage2-complete` 获取实际哈希。
- 新版 EXE、截图与 `.venv` 不进入 Git，源码及完整依赖锁定进入 Git；可按 README 从干净源码目录重建。
- 阶段 1 提交消息：`chore: establish recoverable baseline`；使用 `git rev-parse stage1-complete` 获取实际提交哈希。
- 基线源码：`git show pre-refactor-baseline:outputs/映序_字幕整理器.py`。
- 当前源码需要完整项目结构；原文件名入口不再是单文件分发源码。
- 原 `work/*.spec` 仅历史记录；当前打包只使用 `scripts/build.py`。
- 最终阶段 1 EXE 路径：`outputs/stage1/YingXuSubtitleOrganizer.exe`。原 EXE 不替换。
- GUI 检查截图、EXE 和构建缓存不进入 Git；所有项目源码和交接文档进入 Git。

## 已知问题及剩余工作

新版已接入整理执行和本地记录；安全撤销尚未实现。各次人工审阅在重新扫描后重新开始，历史结果保存在本地记录中。
根目录无法读取会显示错误，但 legacy core 对子目录的权限异常仍可能忽略；阶段 3 的取消扫描是在计算结束后丢弃结果，并不立即终止后台计算。
关闭扫描中的窗口会等待当前任务完成；大量文件的匹配性能尚未专项优化。
多 DPI、跨显示器与干净 Windows 环境尚未验证；当前测试覆盖本机实际窗口和两种窗口尺寸。
旧版 UI 的限制仍存在于 legacy 入口，不应将新版布局验证理解为旧界面已修复。

## 第五阶段结束时的交接（历史记录）

1. 先读本文件、`docs/DESIGN_PLAN.md` 和 `docs/WEB_UI_MIGRATION.md`，核对 Git 状态；无需重新全量审查前四阶段或参考仓库。
2. 等待用户验收阶段 5 并明确确认阶段 6；随后完成现代 Web 工作台、局部玻璃/粒子及结构化数据交互，不提前接入用户文件执行。
3. 保留 `run_preview.py`、`yingxu/qt_ui/`、原 `.venv`、阶段四 EXE 与恢复标签；不在旧环境直接覆盖安装 WebEngine 依赖。
4. 首次移植代码时按审查文档固定上游提交/路径，登记许可与修改；第三方脚本先审查后决定是否使用。
5. 阶段 5 的实际 WebEngine、离线资源与技术试包已验证；正式发行、依赖裁剪和干净机验收仍在阶段 8。
6. 若未来实现安全撤销，先增加执行后文件身份记录，再验证目标被替换、原路径占用和部分失败，不直接倒序重命名。
7. 每阶段保存、验证、更新 PROGRESS 并提交，汇报后暂停。

上述交接对应第五阶段完成时点。当前进度以文件顶部的阶段 8d 发布记录为准。
