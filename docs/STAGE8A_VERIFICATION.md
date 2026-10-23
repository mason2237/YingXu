# 8a：全按钮玻璃、果冻拖动与真实光学进度

日期：2026-10-23。基线 `85eca86` / `stage7-complete`。
本轮恢复标签：`stage8a-controls-complete`。此为用户追加的控件效果子阶段；正式 EXE、完整 DPI/性能/设备验收仍待后续阶段。

## 覆盖与来源

- `glass-controls.js` 自动覆盖页面内所有语义 button，包括顶部、排序/详情、图标、空状态、通知、快捷操作、候选、确认、记录与翻页；MutationObserver 处理动态生成/替换的按钮，不改原有文字和点击回调。
- 所有按钮统一应用项目 CSS 玻璃外壳：透色、折面反光、指针高光、轻描边，以及明暗/禁用/焦点/停止语义。小型/文字/图标按钮使用该轻量材质；不冒充每一个按钮都使用 GPU 折射。
- 顶部、筛选、详情主操作、主任务操作继续使用未修改的 Lens GPU 渲染器；一个可复用的真实弹窗 footer 容器补齐确认、返回、导出、分页等主要弹窗按钮。只移动并还原原有 footer 节点，保留事件和焦点。
- 果冻直接复用 `lens/internal/jelly.js` 的 JellyController / 原弹簧物理。按钮弹性提高，小范围拖动上限每轴 12px，松手回弹。移出/重挂节点使用弱缓存与控制器身份检查，避免重复绑定或增长的强引用。
- 真正拖动超过 5px 后阻止点击；减少动态或关闭玻璃时停止拖动形变，独立的防拖动误触仍生效。键盘与正常轻点保持原行为。
- 任务条使用原版 createOpticalProgress 和原版 Lens renderer/optics：真实波纹、光导、折射和完成状态。恢复 30px 可见轨道，去掉原先针对 DOM 精简版的 8px/隐藏波纹覆盖。
- 进度继续来自实际 done/total；总数未知时只显示不定光带，不编造百分比。轨道使用中性底纹，避免装饰色块让填充位置显得超过真实进度。
- 处理任务时暂停被加载层遮住的列表雾气/短粒子；进度结束/隐藏时停止波纹。设置和结束状态不重复重启相同动画。停止按钮使用独立红色底纹，修复相邻蓝色按钮背景越界染色。
- 原 19 个 Lens 文件字节未改；新增 CSS 与生命周期/业务映射属于项目适配代码。未联网、未安装依赖、未执行第三方脚本，未改 Python 文件整理核心或扩大 QWebChannel 文件权限。

## 定向检查

`work/check_glass_controls.py` 运行真实 WebEngine；媒体、历史和外观设置只在 `work/test-results/glass-controls-*`。

1. 实窗初始 40 个 button、动态候选/记录生成后 59 个 button 全部带统一玻璃外壳。主操作有原版 GPU，其他为 CSS 材质；这些是测试场景计数，不是产品固定上限。
2. QtTest 真实鼠标拖动顶部快捷操作：按住可移动/形变，松手回弹；没有误开面板。随后普通原生鼠标点击仍能打开快捷操作。
3. 候选弹窗连续打开/关闭 3 次，动态按钮仍被覆盖，复用同一个光学 footer 容器；Lens canvas 在该场景初始 5、弹窗打开最多 6。列表雾气另有一个独立 canvas，没有每按钮新增 GL。
4. 勾选真实预览确认后，拖动“确认整理”没有执行任何任务，临时媒体的路径和字节完全不变。
5. 正常原生点击确认，仅执行一批 3 份字幕。测试在第二份文件处理前受控等待，实窗进度显示实际完成的 **1 / 3、33%**，原版波纹和 WebGL 轨道已启用；不是产品用定时器推进。
6. 在任务中开启“减少动态”，波纹关闭、按钮不再移动；拖动仍不激活按钮。释放测试等待后，实际整理结束，真实历史仅 1 批、成功 3 项，JavaScript 控制台无错误。
7. 浅色/深色截图和按住形变截图已实际查看；导出 11 帧原生拖动/回弹录制。最初鼠标按下发生在主题过渡期间，增加短等待后重复检查通过。

另完成 7 个修改 JS 文件语法、2 个 Python 文件编译、3 项上游来源/完整性检查；保留的诊断与示例两入口启动/通道检查通过。按用户“少检查”，本轮未重复完整 32/14 项业务回归，也未声称完成性能/DPI认证。电脑控制工具调用 0 次。

## 主要文件

- `frontend/js/components/glass-controls.js`、`frontend/css/glass-controls.css`
- `liquid-actions.js`、`lens-runtime.js`、`upstream-effects.js`
- `workspace-feedback.js`、`dialogs.js`、`workspace.js`
- `frontend/workspace.html`、`yingxu/web_ui/resources.py`
- `work/check_glass_controls.py`、本记录、设计/进度/来源文档

## 产物与接续

- `outputs/stage8a_workspace_light.png` / `stage8a_workspace_dark.png`
- `outputs/stage8a_candidate_glass.png` / `stage8a_confirm_drag.png`
- `outputs/stage8a_real_progress.png`
- `outputs/stage8a_jelly_motion.gif`（11 帧 Qt 原生输入录制，非生成设计稿；用于演示，不代表测得的显示帧率）

当前已打开的旧源码窗口需要关闭后用 `run_web.py` 重新启动，才能加载新增的 Python 资源白名单；仅刷新旧进程不足以新增资源。未擅自关闭可能正在使用的旧窗口。

下一子阶段按用户确认继续：真实 DPI/跨屏、长期 CPU/内存/GPU 兼容、冷启动/真实规模性能与最终 Windows EXE。本轮不承诺所有显卡稳定 60 FPS，不改变系统文件对话框的系统控件样式。
