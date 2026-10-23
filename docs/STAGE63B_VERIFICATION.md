# 6.3b 工作台反馈与快捷操作

日期：2026-10-22。基线 `492e10a` / `stage6-3a-refined`。授权：“开始下一步”；继续遵循少检查、少用电脑控制、每阶段提交并等待确认。

## 本阶段成果

| 内容 | 实现与真实行为 |
| --- | --- |
| 快捷操作 | 顶部入口 / Ctrl+K；12 个固定动作，直接复用当前搜索、筛选、候选、跳过、预览、记录、外观、示例功能。中文 IME、方向/Home/End、Enter、禁用项、一次运行及关闭焦点处理。没有任意命令解释器。 |
| 通知 | 160ms 出现 / 100ms 退出、计时线、指针/焦点/隐藏暂停、状态图标；原生 popover 放到当前 dialog 内，关闭 dialog 后迁回活动层。删除原来的独立简单计时器，不提供虚构文件撤销。 |
| 加载 | 原版 Lens 进度工厂，仅 DOM/CSS，实际 done/total 驱动；没有总量时用不定状态。纠正空目录和错误场景的初始总量，不增加人为等待或假成功。 |
| 详情抽屉 | 窄屏将同一个 aside 移入原生 dialog；按钮/画布节点保持，Tab 留在模态内、Escape 关闭并还原，断点变宽会直接收回。宽屏仍并列。 |
| 状态与结果 | 准备/审阅/预览步骤同步；空目录/无结果/读取失败分开呈现。记录的成功/跳过/异常数量、分布及具体原因来自现有记录数据，仍明确标识为示例。 |
| 性能边界 | 不增加 WebGL 画布；浮层打开后暂停背景烟雾和粒子，关闭后按需恢复。新的临时动画有退出/销毁处理，减少动态时静态显示。 |

## 来源

- 固定仓库/提交仍为 `ruiqichenbiec/design-systems@7a424c93b9be13cf835b91ea67495fec2ec0584e`，MIT © 2026 DayDreamInAReverie。
- 本轮只下载和阅读 `overture/src/overlays.js`、`controls.js`、`dynamics.js`，没有安装依赖、执行上游脚本或加载在线素材。参考文件保存在忽略的 work/test-results 中。
- `workspace-overlays.js` 定向改编 overlays.js 的 Toast、CommandPalette、Tooltip 生命周期；已有 modal.js 加入 Drawer 横向运动。审查文件 SHA256、修改说明和许可见 vendor/UPSTREAM.md 与 THIRD_PARTY_NOTICES.md。
- 原 19 个 Lens 文件没有修改；加载使用现有 `createOpticalProgress` 工厂，未新增 GL renderer。空/错布局、未知总量指示、记录分布和应用状态适配为项目实现。
- Lattice 点场需要 three.js/GPU 计算；结合 6.3a 已记录的 37–50 次/秒短采样，本阶段不向主工作台增加这套依赖和绘制。进度选择 Lens、通知/快捷操作选择 Overture；重叠项及无业务入口项已在采用清单逐项说明。

## 文件

- 新增 `frontend/vendor/design-systems/workspace-overlays.js`、`frontend/js/components/workspace-feedback.js`、`frontend/css/feedback.css`。
- 修改 `workspace.html`、`workspace.js`、`components/dialogs.js`、`components/upstream-effects.js`、`components/list-mist.js`、`preview/adapter.js`、vendor/modal.js；Python 仅在 `web_ui/resources.py` 增加三个明确静态资源路径。
- 定向脚本 `work/check_workspace_feedback.py`；原调度脚本增加浮层暂停状态覆盖。计划、进度、设计系统、来源和采用清单同步更新。
- 核心 Python 文件操作、原 Qt 入口和原发布包没有改动。Web 仍只注册 appearance，实际 execute 仍禁用；没有扩大文件或系统命令能力。

## 必要验证

沿用用户“少检查”的要求，没有运行全部 80 项回归、旧全流程 GPU 故障注入、全 DPI 或打包检查。

- 8 个修改 JS 模块通过 Node `--check`；资源模块/定向脚本通过 Python 编译，实际页面模块加载无错误。
- `work/check_mist_scheduler.mjs`：4/4，通过 60/120/144/240Hz 预算、空闲结束、隐藏/关闭/减少动态/浮层暂停、长帧限幅。这是调度检查，不是实际 60 FPS 保证。
- `work/check_workspace_feedback.py`：一个临时设置的实际窗口集中验证 Ctrl+K、中文组合输入保护、命令打开预览、真实执行禁用、候选指定通知及顶层迁移、暂停、结果三类计数、10,000 条示例加载、筛选空状态、900×620 深色抽屉及 Tab/Escape/节点还原、键盘提示、减少动态。
- 实际加载收到 **21 次**进度更新，数值在 0–100 且含实际完成的 100；控制台错误为空，原生注册对象只有 `appearance`。
- 初次通知鼠标断言未通过：QtTest 坐标没有命中原生 popover，不能据此推导真实鼠标行为。控制器采用明确进入/离开标志，定向脚本改为指针事件验证，加上 DOM 焦点暂停；没有声称已完成原生鼠标悬停体感认证。
- 截图最初早于 170ms 入场和原生合成，增加 250ms 采集等待后重新保存清晰证据。只重跑同一短脚本以完成这些修正；没有展开全套回归。电脑控制工具调用 0 次。

最终脚本输出：`PASS`、`progressUpdates: 21`、`consoleErrors: []`、`nativeInterfaces: ["appearance"]`。

## 实际截图

- `outputs/stage63b_commands_light.png`：快捷操作。
- `outputs/stage63b_candidates_light.png`：候选对比。
- `outputs/stage63b_notice_light.png`：示例审阅通知。
- `outputs/stage63b_results_light.png`：结果数量、分布和异常原因。
- `outputs/stage63b_drawer_dark.png`：900×620 深色详情抽屉。

图片为可再生成的忽略产物，没有合成虚假界面或重录 GIF。

## 恢复与剩余

提交消息 `feat: unify workspace feedback and quick actions`；标签 `stage6-3b-complete`。旧阶段恢复点均保留。

等待用户验收后进入阶段 7：真实目录/扫描/元数据、匹配与人工审阅、冻结变更预览、一次性确认执行、结果与本地记录。阶段 8 再做全面性能、DPI/多设备、干净 Windows 和正式 EXE。当前仍是显式示例；6.3a 深色帧率未稳定 60 的限制未因本轮而被宣告解决。
