# 上游效果与组件覆盖清单

审查及采用更新：2026-10-21 至 2026-10-23。固定仓库 `ruiqichenbiec/design-systems`，提交 `7a424c93b9be13cf835b91ea67495fec2ec0584e`。

本清单包含 **18 类 Lens 控件 + 4 个 Lens 展示组合 + 14 类 Lattice 组件 + 46 类 Overture 组件，共 82 项**，另列跨组件效果。Lattice 的 Cover 是封面，未计为第 15 个组件。状态描述当前交付，待适配/可选展示不表示已经接入。

已采用的 Lens 19 个运行文件均与上游 Git blob 逐字节一致，见 `frontend/vendor/design-systems/lens/ORIGIN.json`。外部生命周期/业务映射是项目适配代码。6.2 定向改编 Overture transition/focusPoint；6.3b 继续定向改编通知/命令/提示和 Drawer 运动。其余项目按下表明确为现有实现、未来真实功能或可选/不采用；不冒充已经移植。未执行上游构建脚本或加载摄影素材。

6.3a 按用户截图将 Lens 光学/手势扩展到三个主操作按钮。列表雾气为独立项目扩展，非 Lattice 点场，不计入下方 82 项上游采用数量；其余未采用项状态不变。

6.3b 已接入 Overture 通知/命令/提示与 Drawer 运动的定向改编，以及原版 Lens 进度 DOM 工厂。其他重叠控件明确选择现有实现，真实目录/拖入留阶段 7；可选展示表示未移植，不是遗漏的已完成承诺。新反馈不增加 WebGL 上下文，具体来源和定向检查见 STAGE63B_VERIFICATION.md。

## Lens

2026-10-23 补充 8a：页面所有按钮统一 CSS 玻璃外壳及原版 JellyController；GPU 折射继续由主操作/筛选承载，并新增一个复用的弹窗 footer。原版光学进度现启用 GPU 和波纹，绑定真实任务计数。具体 CSS/GPU 区分、覆盖计数与实窗检查见 STAGE8A_VERIFICATION.md；原 19 文件仍未修改。

| 组件 / 效果 | 当前状态 | 去向与具体原因 | 上游实现 |
| --- | --- | --- | --- |
| 玻璃按钮 · button | 已接入工作台及验收页 | 8a 全按钮统一 CSS 材质和原版 Jelly；主操作/筛选及复用弹窗 footer 使用原版 GPU。第七阶段的真实回调保留。 | [源码](https://github.com/ruiqichenbiec/design-systems/blob/7a424c93b9be13cf835b91ea67495fec2ec0584e/lens/lab/design-system/components.js) |
| 图标按钮 · icon-button | 已接入工作台及开发验收页 | 8a 图标/关闭/翻页按钮同样使用统一 CSS 玻璃和原版 Jelly，共用 Tooltip/焦点，不为每个图标分配独立画布。 | [源码](https://github.com/ruiqichenbiec/design-systems/blob/7a424c93b9be13cf835b91ea67495fec2ec0584e/lens/lab/design-system/component-patterns.js) |
| 滑动开关 · switch | 已接入开发验收页 | 原版工厂保留开发验收页；应用外观保留与持久偏好绑定的原生 switch，维护单一状态源。 | [源码](https://github.com/ruiqichenbiec/design-systems/blob/7a424c93b9be13cf835b91ea67495fec2ec0584e/lens/lab/design-system/components.js) |
| 连接开关 · toggle-tile | 已接入开发验收页 | 保留原版可交互示例；按字幕业务需要定向接入，避免增加无意义的参数/页面。 | [源码](https://github.com/ruiqichenbiec/design-systems/blob/7a424c93b9be13cf835b91ea67495fec2ec0584e/lens/lab/design-system/component-patterns.js) |
| 选项胶囊 · choices | 已接入工作台及验收页 | 在 6.3 / 7 接入对应真实设置、审阅、搜索、通知或任务状态。 | [源码](https://github.com/ruiqichenbiec/design-systems/blob/7a424c93b9be13cf835b91ea67495fec2ec0584e/lens/lab/design-system/components.js) |
| 分段标签 · tabs | 已接入开发验收页 | 原版工厂保留开发验收页；工作台没有多页面标签需求，状态筛选继续使用已接入的 Lens choices。 | [源码](https://github.com/ruiqichenbiec/design-systems/blob/7a424c93b9be13cf835b91ea67495fec2ec0584e/lens/lab/design-system/component-patterns.js) |
| 浮动导航 · dock | 已接入开发验收页 | 保留原版可交互示例；按字幕业务需要定向接入，避免增加无意义的参数/页面。 | [源码](https://github.com/ruiqichenbiec/design-systems/blob/7a424c93b9be13cf835b91ea67495fec2ec0584e/lens/lab/design-system/component-patterns.js) |
| 光学滑杆 · slider | 已接入开发验收页 | 在 6.3 / 7 接入对应真实设置、审阅、搜索、通知或任务状态。 | [源码](https://github.com/ruiqichenbiec/design-systems/blob/7a424c93b9be13cf835b91ea67495fec2ec0584e/lens/lab/design-system/components.js) |
| 数值步进器 · stepper | 已接入开发验收页 | 保留原版可交互示例；按字幕业务需要定向接入，避免增加无意义的参数/页面。 | [源码](https://github.com/ruiqichenbiec/design-systems/blob/7a424c93b9be13cf835b91ea67495fec2ec0584e/lens/lab/design-system/components.js) |
| 玻璃通知 · notification | 已接入开发验收页 | 在 6.3 / 7 接入对应真实设置、审阅、搜索、通知或任务状态。 | [源码](https://github.com/ruiqichenbiec/design-systems/blob/7a424c93b9be13cf835b91ea67495fec2ec0584e/lens/lab/design-system/components.js) |
| 操作菜单 · menu | 已接入开发验收页 | 在 6.3 / 7 接入对应真实设置、审阅、搜索、通知或任务状态。 | [源码](https://github.com/ruiqichenbiec/design-systems/blob/7a424c93b9be13cf835b91ea67495fec2ec0584e/lens/lab/design-system/component-patterns.js) |
| 折射搜索框 · search | 已接入开发验收页 | 原版工厂保留开发验收页；文件/命令搜索保留原生输入和中文 IME，不为文字输入额外添加 GL 画布。 | [源码](https://github.com/ruiqichenbiec/design-systems/blob/7a424c93b9be13cf835b91ea67495fec2ec0584e/lens/lab/design-system/components.js) |
| 弹性面板 · panel | 已接入工作台及验收页 | 顶部保留原版 Lens，并在 6.3a 修订为薄材质；其他浮层采用原生 dialog 和已改编运动，不增加整片弹性形变。 | [源码](https://github.com/ruiqichenbiec/design-systems/blob/7a424c93b9be13cf835b91ea67495fec2ec0584e/lens/lab/design-system/components.js) |
| 自由透镜 · lens | 已接入开发验收页 | 保留原版可交互示例；按字幕业务需要定向接入，避免增加无意义的参数/页面。 | [源码](https://github.com/ruiqichenbiec/design-systems/blob/7a424c93b9be13cf835b91ea67495fec2ec0584e/lens/lab/design-system/components.js) |
| 透镜卡片列表 · card-list | 已接入开发验收页 | 保留原版可交互示例；按字幕业务需要定向接入，避免增加无意义的参数/页面。 | [源码](https://github.com/ruiqichenbiec/design-systems/blob/7a424c93b9be13cf835b91ea67495fec2ec0584e/lens/lab/design-system/card-list.js) |
| 光导进度条 · progress | 已接入工作台及验收页 | 8a 将原版 createOpticalProgress 接原版 Lens renderer，按真实 done/total 显示波纹/光导；未知总量仍为不定状态，减少动态关闭波纹，隐藏/完成停帧。 | [源码](https://github.com/ruiqichenbiec/design-systems/blob/7a424c93b9be13cf835b91ea67495fec2ec0584e/lens/lab/design-system/optical-components.js) |
| 凹槽吸附选择 · drop-select | 已接入开发验收页 | 原版工厂保留开发验收页；类型/主题/材质沿用原生 select 和系统键盘语义，不叠加另一套手势控制器。 | [源码](https://github.com/ruiqichenbiec/design-systems/blob/7a424c93b9be13cf835b91ea67495fec2ec0584e/lens/lab/design-system/optical-components.js) |
| 二维滤镜滑块 · xy-slider | 已接入开发验收页 | 保留原版可交互示例；按字幕业务需要定向接入，避免增加无意义的参数/页面。 | [源码](https://github.com/ruiqichenbiec/design-systems/blob/7a424c93b9be13cf835b91ea67495fec2ec0584e/lens/lab/design-system/optical-components.js) |
| 玻璃光导折线 · line-chart | 待评估展示组合 | 操作记录目前没有时间序列指标；保留为可选统计展示，不用虚构数据充当扫描结果。 | [源码](https://github.com/ruiqichenbiec/design-systems/blob/7a424c93b9be13cf835b91ea67495fec2ec0584e/lens/lab/design-system/showcase-charts.js) |
| 液体柱状图 · bar-chart | 待评估展示组合 | 可评估结果数量/类型分布；真实统计由第七阶段 Python 提供。 | [源码](https://github.com/ruiqichenbiec/design-systems/blob/7a424c93b9be13cf835b91ea67495fec2ec0584e/lens/lab/design-system/showcase-charts.js) |
| 彩色玻璃环图 · ring-chart | 待评估展示组合 | 可评估完成数量分布；不能用动画伪装未知进度。 | [源码](https://github.com/ruiqichenbiec/design-systems/blob/7a424c93b9be13cf835b91ea67495fec2ec0584e/lens/lab/design-system/showcase-charts.js) |
| 光学记录表 · records-table | 待评估展示组合 | 候选小表/历史可适配；原版分页展示不替代 10,000 行虚拟列表。 | [源码](https://github.com/ruiqichenbiec/design-systems/blob/7a424c93b9be13cf835b91ea67495fec2ec0584e/lens/lab/design-system/showcase-charts.js) |

## Lattice

| 组件 / 效果 | 当前状态 | 去向与具体原因 | 上游实现 |
| --- | --- | --- | --- |
| 点阵按钮 · Button | 可选展示 | 单一控件材质以 Lens 为主；该体系的点群响应保留独立对照。 | [源码](https://github.com/ruiqichenbiec/design-systems/blob/7a424c93b9be13cf835b91ea67495fec2ec0584e/lattice/src/components.css) |
| 点阵输入 · TextField | 可选展示 | 名称/错误提示可适配点列反馈；点阵字不用于中文文件名正文。 | [源码](https://github.com/ruiqichenbiec/design-systems/blob/7a424c93b9be13cf835b91ea67495fec2ec0584e/lattice/src/components.css) |
| 点群标签 · Tabs | 本轮不采用 | 主筛选已采用 Lens 原版选中/手势；不在同一状态叠加另一套点群控制器。 | [源码](https://github.com/ruiqichenbiec/design-systems/blob/7a424c93b9be13cf835b91ea67495fec2ec0584e/lattice/src/dom/controls.js) |
| 气态/晶态开关 · Switch | 可选展示 | 与 Lens 设置开关作材质对照，不叠加两套手势控制器。 | [源码](https://github.com/ruiqichenbiec/design-systems/blob/7a424c93b9be13cf835b91ea67495fec2ec0584e/lattice/src/dom/controls.js) |
| 点列滑杆 · Slider | 可选展示 | 作为强度调节的替代反馈，原生 range 保留键盘语义。 | [源码](https://github.com/ruiqichenbiec/design-systems/blob/7a424c93b9be13cf835b91ea67495fec2ec0584e/lattice/src/dom/controls.js) |
| 结晶进度 · Progress | 本轮不采用 | 6.3b 统一选择现有 Lens 实际数值进度；不为同一任务加载第二套点场运行依赖。 | [源码](https://github.com/ruiqichenbiec/design-systems/blob/7a424c93b9be13cf835b91ea67495fec2ec0584e/lattice/src/dom/controls.js) |
| 点阵消息 · Toast | 本轮不采用 | 6.3b 统一采用 Overture 的计时/暂停通知，避免同一反馈出现两套状态与语义。 | [源码](https://github.com/ruiqichenbiec/design-systems/blob/7a424c93b9be13cf835b91ea67495fec2ec0584e/lattice/src/dom/command.js) |
| 轨迹加载器 · Loader | 本轮不采用 | 6.3b 已提供未知总量读取状态和减少动态；点场 loader 的额外渲染依赖不进入主工作台。 | [源码](https://github.com/ruiqichenbiec/design-systems/blob/7a424c93b9be13cf835b91ea67495fec2ec0584e/lattice/src/dom/dottext.js) |
| 逐点重排字 · DotText | 可选展示 | 仅品牌/短状态可用，5×7 字库不能承担中文长文件名。 | [源码](https://github.com/ruiqichenbiec/design-systems/blob/7a424c93b9be13cf835b91ea67495fec2ec0584e/lattice/src/dom/dottext.js) |
| 光标点集重组 · CursorHalo | 可选展示 | 尊重系统光标与键盘焦点，默认不覆盖用户指针；独立验收页评估。 | [源码](https://github.com/ruiqichenbiec/design-systems/blob/7a424c93b9be13cf835b91ea67495fec2ec0584e/lattice/src/dom/cursor.js) |
| 命令面板 · CommandPalette | 本轮不采用 | 6.3b 选择 Overture 命令列表，复用当前动作和原生 dialog，不引入第二个快捷入口。 | [源码](https://github.com/ruiqichenbiec/design-systems/blob/7a424c93b9be13cf835b91ea67495fec2ec0584e/lattice/src/dom/command.js) |
| 粒子点场/熔化/冲击波/旋转 · Field | 可选展示 | 依赖 three.js 与 GPU 计算；完整场景放开发验收页，工作台评估低密度短反馈。 | [源码](https://github.com/ruiqichenbiec/design-systems/blob/7a424c93b9be13cf835b91ea67495fec2ec0584e/lattice/src/gl/field.js) |
| 依赖瀑布 · Cascade | 暂不采用 | 现有审阅对象不是依赖 DAG；该演示的滚轮巡游与文件列表滚动用途冲突。 | [源码](https://github.com/ruiqichenbiec/design-systems/blob/7a424c93b9be13cf835b91ea67495fec2ec0584e/lattice/src/gl/cascade.js) |
| 证明树生长/旋转 · ProofTree | 暂不采用 | 视频字幕匹配没有公理/结论树结构；不引入数学示例与假业务图。 | [源码](https://github.com/ruiqichenbiec/design-systems/blob/7a424c93b9be13cf835b91ea67495fec2ec0584e/lattice/src/gl/prooftree.js) |

## Overture

| 组件 / 效果 | 当前状态 | 去向与具体原因 | 上游实现 |
| --- | --- | --- | --- |
| 进入按钮 · CueButton | 保留现有实现 | 主要动作使用原版 Lens，禁用/错误/成功绑定现有回调；实际任务忙碌和结果在阶段 7 接入。 | [源码](https://github.com/ruiqichenbiec/design-systems/blob/7a424c93b9be13cf835b91ea67495fec2ec0584e/overture/src/controls.js) |
| 图标按钮 · IconButton | 保留现有实现 | 继续使用已有语义 button/项目图标和焦点样式；6.3b 提供共用 Tooltip，不复制摄影控件。 | [源码](https://github.com/ruiqichenbiec/design-systems/blob/7a424c93b9be13cf835b91ea67495fec2ec0584e/overture/src/controls.js) |
| 文字链接 · TextLink | 保留现有实现 | 完整名称/路径披露和复制已有实际行为；打开系统位置须在阶段 7 使用已登记 ID。 | [源码](https://github.com/ruiqichenbiec/design-systems/blob/7a424c93b9be13cf835b91ea67495fec2ec0584e/overture/src/controls.js) |
| 幕次标签页 · StageTabs | 可选展示 | 对照其保留速度的取景框与 Lens 流体指示层，统一最终控件。 | [源码](https://github.com/ruiqichenbiec/design-systems/blob/7a424c93b9be13cf835b91ea67495fec2ec0584e/overture/src/controls.js) |
| 章节导航 · ChapterNav | 保留现有实现 | 6.3b 已将准备/审阅/预览步骤绑定实际前端状态；未复制演示章节及全屏切换。 | [源码](https://github.com/ruiqichenbiec/design-systems/blob/7a424c93b9be13cf835b91ea67495fec2ec0584e/overture/src/controls.js) |
| 路径导航 · Breadcrumb | 留待阶段 7 | 真实目录选择/层级导航依赖后端目录 ID，本阶段仍为显式示例路径，不能虚构可导航目录。 | [源码](https://github.com/ruiqichenbiec/design-systems/blob/7a424c93b9be13cf835b91ea67495fec2ec0584e/overture/src/controls.js) |
| 翻页 · Pagination | 保留现有实现 | 现有预览真实分页、禁用、页码已可用；统一浮层样式，不重复实现同一分页控制器。 | [源码](https://github.com/ruiqichenbiec/design-systems/blob/7a424c93b9be13cf835b91ea67495fec2ec0584e/overture/src/controls.js) |
| 动作搜索 · CommandPalette | 已定向改编并接入 | 6.3b workspace-overlays.js 改编过滤/键盘选择；12 个固定实际动作、中文 IME、禁用与异步保护。 | [源码](https://github.com/ruiqichenbiec/design-systems/blob/7a424c93b9be13cf835b91ea67495fec2ec0584e/overture/src/overlays.js) |
| 文字输入 · TextField | 保留现有实现 | 现有原生输入与中文组合输入保护保留，命令搜索也有 IME 防误执行；不复制演示校验业务。 | [源码](https://github.com/ruiqichenbiec/design-systems/blob/7a424c93b9be13cf835b91ea67495fec2ec0584e/overture/src/controls.js) |
| 创作笔记 · TextArea | 暂不采用 | 当前没有创作笔记或多行文字编辑需求。 | [源码](https://github.com/ruiqichenbiec/design-systems/blob/7a424c93b9be13cf835b91ea67495fec2ec0584e/overture/src/controls.js) |
| 下拉选择 · Select | 保留现有实现 | 原生 select 承担类型/主题/材质选择和系统键盘语义；未复制自定义下拉控制器。 | [源码](https://github.com/ruiqichenbiec/design-systems/blob/7a424c93b9be13cf835b91ea67495fec2ec0584e/overture/src/controls.js) |
| 单选组 · ChoiceGroup | 可选展示 | 其选中压印适合对照；主筛选已有 Lens 真实手势。 | [源码](https://github.com/ruiqichenbiec/design-systems/blob/7a424c93b9be13cf835b91ea67495fec2ec0584e/overture/src/controls.js) |
| 复选框 · Check | 保留现有实现 | 已有核对复选框保留原生语义；示例执行仍禁用，真实确认权限在阶段 7。 | [源码](https://github.com/ruiqichenbiec/design-systems/blob/7a424c93b9be13cf835b91ea67495fec2ec0584e/overture/src/controls.js) |
| 状态开关 · Switch | 可选展示 | 开关弹簧与 Lens 对照，最终同一设置只绑定一个状态源。 | [源码](https://github.com/ruiqichenbiec/design-systems/blob/7a424c93b9be13cf835b91ea67495fec2ec0584e/overture/src/controls.js) |
| 曝光滑杆 · Range | 可选展示 | 曝光游标效果可用于强度示例；没有图片曝光功能。 | [源码](https://github.com/ruiqichenbiec/design-systems/blob/7a424c93b9be13cf835b91ea67495fec2ec0584e/overture/src/controls.js) |
| 数量步进 · Stepper | 可选展示 | 数量翻片反馈可用于分页设置；不新增无用数值。 | [源码](https://github.com/ruiqichenbiec/design-systems/blob/7a424c93b9be13cf835b91ea67495fec2ec0584e/overture/src/controls.js) |
| 关键词输入 · TagInput | 可选展示 | 可展示添加/去重/移除动画，现有流程没有可写标签字段。 | [源码](https://github.com/ruiqichenbiec/design-systems/blob/7a424c93b9be13cf835b91ea67495fec2ec0584e/overture/src/controls.js) |
| 本地图片选择 · Dropzone | 留待阶段 7 | 拖入目录必须与 Python 目录 ID/路径校验一并接入；本阶段不引入图片解码或上传示例。 | [源码](https://github.com/ruiqichenbiec/design-systems/blob/7a424c93b9be13cf835b91ea67495fec2ec0584e/overture/src/controls.js) |
| 折叠说明 · Accordion | 保留现有实现 | 完整路径已有原生 details/summary；保持原生键盘和稳定行为，不额外复制演示内容。 | [源码](https://github.com/ruiqichenbiec/design-systems/blob/7a424c93b9be13cf835b91ea67495fec2ec0584e/overture/src/overlays.js) |
| 确认对话框 · Dialog | 已定向采用 | 阶段 6 modal helper 已适配；光圈进入/退出与其他关闭路径在 6.3 补齐。 | [源码](https://github.com/ruiqichenbiec/design-systems/blob/7a424c93b9be13cf835b91ea67495fec2ec0584e/overture/src/overlays.js) |
| 侧边编辑 · Drawer | 已定向改编并接入 | 6.3b 改编原 modal 的横向运动，用原生 dialog 承载同一详情；焦点/关闭/宽屏还原。 | [源码](https://github.com/ruiqichenbiec/design-systems/blob/7a424c93b9be13cf835b91ea67495fec2ec0584e/overture/src/overlays.js) |
| 辅助提示 · Tooltip | 已定向改编并接入 | 6.3b 定向改编焦点/Escape 生命周期，扩展为共用定位 popover；不生成每行控制器。 | [源码](https://github.com/ruiqichenbiec/design-systems/blob/7a424c93b9be13cf835b91ea67495fec2ec0584e/overture/src/overlays.js) |
| 就地选项 · Popover | 保留原生实现 | 6.3b 通知/Tooltip 使用 HTML 原生 top layer；外观仍采用已有 dialog，未移植 Overture 的就地设置示例。 | [源码](https://github.com/ruiqichenbiec/design-systems/blob/7a424c93b9be13cf835b91ea67495fec2ec0584e/overture/src/overlays.js) |
| 可撤销反馈 · Toast | 已定向改编并接入 | 6.3b 采用计时线/暂停/出现退出，补齐取消、隐藏和 dialog 迁移；删除示例撤销。 | [源码](https://github.com/ruiqichenbiec/design-systems/blob/7a424c93b9be13cf835b91ea67495fec2ec0584e/overture/src/overlays.js) |
| 状态提示 · Notice | 保留现有实现 | 6.3b 统一现有冲突/错误语义与布局；真实权限/占用错误来自阶段 7，未执行原示例处理。 | [源码](https://github.com/ruiqichenbiec/design-systems/blob/7a424c93b9be13cf835b91ea67495fec2ec0584e/overture/src/overlays.js) |
| 显影进度 · Progress | 可选展示 | 其弹簧推进与 Lens 光导进度作对照，真实数值不得由定时器虚构。 | [源码](https://github.com/ruiqichenbiec/design-systems/blob/7a424c93b9be13cf835b91ea67495fec2ec0584e/overture/src/overlays.js) |
| 准备状态 · Loading | 保留现有实现 | 6.3b 以实际适配器事件驱动，未知总量用静态或短读取线；未复制摄影光圈/假等待。 | [源码](https://github.com/ruiqichenbiec/design-systems/blob/7a424c93b9be13cf835b91ea67495fec2ec0584e/overture/src/overlays.js) |
| 空白起点 · EmptyState | 保留现有实现 | 6.3b 区分空目录/筛选空结果/读取错误，入口可清除或重载；不复制原照片导入示例。 | [源码](https://github.com/ruiqichenbiec/design-systems/blob/7a424c93b9be13cf835b91ea67495fec2ec0584e/overture/src/overlays.js) |
| 档案表格 · EditorialTable | 本轮不采用 | 主列表保留已验证虚拟列表，结果使用现有明细；无排序重排需求时不添加 FLIP 动画。 | [源码](https://github.com/ruiqichenbiec/design-systems/blob/7a424c93b9be13cf835b91ea67495fec2ec0584e/overture/src/overlays.js) |
| 幕次时间线 · Timeline | 保留现有记录 | 6.3b 展示记录提供的时间/数量/明细；真实日志在阶段 7 接入，不复制剧场时间线。 | [源码](https://github.com/ruiqichenbiec/design-systems/blob/7a424c93b9be13cf835b91ea67495fec2ec0584e/overture/src/overlays.js) |
| 光圈舞台 · ApertureStage | 可选展示 | 原 GPU 光圈要求摄影底图；先审查独立演示，主题转换优先复用运动原语。 | [源码](https://github.com/ruiqichenbiec/design-systems/blob/7a424c93b9be13cf835b91ea67495fec2ec0584e/overture/src/media.js) |
| 底片档案 · ContactSheet | 可选展示 | 照片底片/拖动惯性只在开发页评估；字幕候选没有图片素材。 | [源码](https://github.com/ruiqichenbiec/design-systems/blob/7a424c93b9be13cf835b91ea67495fec2ec0584e/overture/src/contact.js) |
| 追光取景 · FlashlightFocus | 暂不采用 | 固定照片灯位与三格滚轮切图会接管主文件列表滚动；没有照片浏览业务。 | [源码](https://github.com/ruiqichenbiec/design-systems/blob/7a424c93b9be13cf835b91ea67495fec2ec0584e/overture/src/light.js) |
| 红线照片墙 · PinnedPhotoWall | 暂不采用 | 空间照片墙/摄影机巡游与文件行审阅无对应任务。 | [源码](https://github.com/ruiqichenbiec/design-systems/blob/7a424c93b9be13cf835b91ea67495fec2ec0584e/overture/src/light.js) |
| 胶卷暗盒 · FilmCanister | 可选展示 | 胶片拖出/放回/橡皮筋回弹可独立审查，暂不加载摄影/视频素材。 | [源码](https://github.com/ruiqichenbiec/design-systems/blob/7a424c93b9be13cf835b91ea67495fec2ec0584e/overture/src/film.js) |
| 局部显影 · DevelopImage | 可选展示 | 局部显影可用于独立视觉对照；本工具没有图像显影功能。 | [源码](https://github.com/ruiqichenbiec/design-systems/blob/7a424c93b9be13cf835b91ea67495fec2ec0584e/overture/src/media.js) |
| 取景画廊 · FocusGallery | 可选展示 | 灯箱焦点/退出行为有参考价值，暂不新增图片浏览模块。 | [源码](https://github.com/ruiqichenbiec/design-systems/blob/7a424c93b9be13cf835b91ea67495fec2ec0584e/overture/src/media.js) |
| 显影比较 · CompareLens | 本轮不采用 | 已有原版/旧版/增强三列开发对照；本工具不需要摄影图片的可拖动显影比较。 | [源码](https://github.com/ruiqichenbiec/design-systems/blob/7a424c93b9be13cf835b91ea67495fec2ec0584e/overture/src/media.js) |
| 共振褶皱 · SilkResonance | 可选展示 | GPU 织物/持续回荡只在独立按需演示评估，不进入长期文件阅读区。 | [源码](https://github.com/ruiqichenbiec/design-systems/blob/7a424c93b9be13cf835b91ea67495fec2ec0584e/overture/src/media.js) |
| 共振播放器 · CuePlayer | 暂不采用 | 当前没有音视频播放/解码流程；素材与播放器依赖不为装饰引入。 | [源码](https://github.com/ruiqichenbiec/design-systems/blob/7a424c93b9be13cf835b91ea67495fec2ec0584e/overture/src/media.js) |
| 品牌字标 · Wordmark | 保留项目品牌 | 继续使用映序中文标识和系统字体；不替换成 Overture 拉丁品牌或引入外部字体。 | [源码](https://github.com/ruiqichenbiec/design-systems/blob/7a424c93b9be13cf835b91ea67495fec2ec0584e/overture/src/brand.js) |
| 字体编排 · TypeSpecimen | 可选展示 | 用于字级与长中文换行验收，不分发参考项目字体。 | [源码](https://github.com/ruiqichenbiec/design-systems/blob/7a424c93b9be13cf835b91ea67495fec2ec0584e/overture/src/brand.js) |
| 编辑引言 · PullQuote | 暂不采用 | 没有编辑引言/署名内容，不能增加无关内容区。 | [源码](https://github.com/ruiqichenbiec/design-systems/blob/7a424c93b9be13cf835b91ea67495fec2ec0584e/overture/src/brand.js) |
| 宣传海报 · Poster | 暂不采用 | 没有摄影海报制作/宣传图输出功能。 | [源码](https://github.com/ruiqichenbiec/design-systems/blob/7a424c93b9be13cf835b91ea67495fec2ec0584e/overture/src/brand.js) |
| 品牌工坊 · BrandComposer | 暂不采用 | 品牌图/PNG/WebM 工坊属于独立创作产品；会引入无关编辑与媒体导出流程。 | [源码](https://github.com/ruiqichenbiec/design-systems/blob/7a424c93b9be13cf835b91ea67495fec2ec0584e/overture/src/brand.js) |
| 幕布转场 · CurtainTransition | 本轮不采用 | 工作台状态局部更新并保持选中；6.2 已有主题 iris，不叠加整幕遮挡过渡。 | [源码](https://github.com/ruiqichenbiec/design-systems/blob/7a424c93b9be13cf835b91ea67495fec2ec0584e/overture/src/brand.js) |

## 跨组件效果

| 体系 | 效果范围 | 当前采用情况 | 来源 |
| --- | --- | --- | --- |
| Lens | 真实纹理采样/多层合成/折射/雾化/色散/Fresnel/指针高光 | 原版渲染器已采用 | [源码](https://github.com/ruiqichenbiec/design-systems/blob/7a424c93b9be13cf835b91ea67495fec2ec0584e/lens/lab/design-system/internal/renderer.js) |
| Lens | 弹簧/压感/形变/吸附/手势取消 | 原版控制器已采用 | [源码](https://github.com/ruiqichenbiec/design-systems/blob/7a424c93b9be13cf835b91ea67495fec2ec0584e/lens/lab/design-system/internal/jelly.js) |
| Lens | 4 个内置场景与自定义背景 | 已接入验收页选择 | [源码](https://github.com/ruiqichenbiec/design-systems/blob/7a424c93b9be13cf835b91ea67495fec2ec0584e/lens/lab/design-system/internal/renderer.js) |
| Lens | 13 种合成短音与拖动摩擦音 | 源码已采用；开发页可选，默认关闭，未做人工听感认证 | [源码](https://github.com/ruiqichenbiec/design-systems/blob/7a424c93b9be13cf835b91ea67495fec2ec0584e/lens/lab/design-system/sound.js) |
| Lattice | 粒子点集转换/冲击波/按住熔化 | 可选展示，依赖和缩减方案待 6.3 | [源码](https://github.com/ruiqichenbiec/design-systems/blob/7a424c93b9be13cf835b91ea67495fec2ec0584e/lattice/src/gl/field.js) |
| Lattice | 夜间世界/点阵字体/声音 | 应用明暗主题已统一；Lattice 夜间世界自身仍只作审查 | [源码](https://github.com/ruiqichenbiec/design-systems/blob/7a424c93b9be13cf835b91ea67495fec2ec0584e/lattice/src/core/theme.js) |
| Overture | iris/develop/flip/count/spring 与可打断运动 | 6.2 采用 transition/focusPoint，6.3b 采用短浮层/通知生命周期；其他原语保留为未采用，不自动扩大动画范围。 | [源码](https://github.com/ruiqichenbiec/design-systems/blob/7a424c93b9be13cf835b91ea67495fec2ec0584e/overture/src/dynamics.js) |
| Overture | 三主题/两种光温/八种合成声音 | 应用语义主题已实现；原三主题、光温和声音尚未移植 | [源码](https://github.com/ruiqichenbiec/design-systems/blob/7a424c93b9be13cf835b91ea67495fec2ec0584e/overture/src/core.js) |

## 优先级与后续验收

1. 6.1：原版玻璃/手势/18 类控件、真实材质对照、工作台目录/状态筛选、资源边界与生命周期。
2. 6.2（已完成）：完整浅色/深色/系统跟随、原版虹膜转换的定向改编、偏好保存与初始防闪。场景选择与应用主题分别控制；证据见 STAGE62_VERIFICATION。
3. 6.3b（已完成）：适用反馈已接入，统一通知/加载/结果/快捷操作/浮层；点场依赖和已有帧率限制下不向工作台新增点场渲染。可选展示不作为已实现功能，重叠方案和未采用项保留具体理由。
4. 7：将所有业务值、进度和最终文件操作接入 Python，保留预览、确认与不覆盖；任何演示动画都不能表示实际文件操作成功。

同类控件在开发验收页可并列比较；主工作台共享一个业务状态源和明确的视觉规则。强效果提供开关与减少动态，默认不开启声音，不持续播放无用动画。未采用项的理由可随真实业务需求重新评估。
