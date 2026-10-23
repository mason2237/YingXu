# 第六阶段：Web 工作台验收记录

日期：2026-10-21。范围：完整界面骨架、设计系统、可交互结构化示例、局部玻璃/粒子及真实窗口检查。本阶段不接入用户目录和文件执行，不重新打包 EXE。

## 交付与运行

```powershell
& .\.venv-web\Scripts\python.exe .\run_web_preview.py
```

入口明确显示“界面预览”“示例数据 · 不会修改文件”。右上角提供外观设置，目录栏提供切换示例；可检查正常、多语言、待确认、未匹配、冲突、无需变更、跳过、10,000 行、空目录、无字幕及读取错误。

现有 `run_web.py` 保持第五阶段双向通信技术验证；完整真实整理继续使用 `run_preview.py` / 第四阶段 EXE。原 core/review/operations、Qt UI、已有 32 项测试、依赖及构建脚本无差异；第四/五阶段 EXE 哈希再次核对相同。

### 文件与职责

| 文件 | 职责 |
| --- | --- |
| `run_web_preview.py` | 显式示例工作台入口 |
| `yingxu/web_ui/window.py` / `resources.py` | 增加 preview 页面选择及静态白名单；该页面不注册 QWebChannel |
| `frontend/workspace.html` | 顶部/目录/搜索/列表/详情/底部和五类弹窗语义结构 |
| `frontend/css/{tokens,components,workspace}.css` | 中性/品牌蓝、字体/尺寸、控件状态和自适应布局 |
| `frontend/js/workspace.js` / `store.js` / `model.js` | 工作台事件、选择/筛选状态、显示状态枚举 |
| `frontend/js/components/` | 虚拟列表、详情、候选/预览/记录弹窗、图标、受控效果 |
| `frontend/js/preview/` | 结构化测试场景与本地适配器；没有磁盘访问 |
| `frontend/vendor/design-systems/` | MIT focus/modal 片段、上游修改记录和完整许可 |
| `work/check_web_workspace.py` / `check_web_adapter.mjs` | 真实 Qt/WebEngine 流程检查 / 8 项适配器检查 |

所有示例中的 `D:\影库\…` 都是显示文字，不是程序读取或创建的文件夹。更换/确认/移除/跳过只更新内存计划，明确确认框不会启用执行；没有伪装的文件整理成功反馈。

## 实际设计与交互

- 品牌与三步流程、目录摘要、带数量的筛选、列表/详情、稳定的“预览变更”形成单工作台。常用操作无需切换页面。
- 主文件名 15px，字幕 13px，搜索/候选及预览名称 14px；长文件名保留扩展名，详情全文换行，路径折叠查看并可复制视频名称。完整视觉参数见 [UI_SYSTEM.md](UI_SYSTEM.md)。
- 双层 84px 列表使用虚拟滚动；搜索覆盖原名、字幕和目标名。状态文字区分已匹配/待确认/未匹配/冲突/跳过/无需变更。排序保持稳定 ID 选择。
- 候选同时展示三个评分、依据与集数冲突；人工指定保持原评分并要求确认。添加/替换、移除关联、确认、跳过恢复都真实更新示例状态和计数。
- 详情底部固定更换/确认/跳过；宽度不大于 1120px 改为可关闭浮层。内容与操作区分别布局，长内容不会隐藏主要操作。
- 变更预览展示原名/原路径、目标名/目标路径与阻止状态，每页 20 项。勾选核对仍不能触发真实整理，按钮解释第七阶段接入范围。操作记录显示明确的示例结果及错误，不记录到磁盘。
- Ctrl+F 搜索，Ctrl+Enter 预览，↑/↓/Home/End/PageUp/PageDown 选择，Enter 查看，Escape 关闭/返回。弹窗原生焦点约束、关闭后恢复触发点；触发元素被重绘时回到列表。组合输入期间不提前筛选或截获快捷键。

### 液态玻璃与粒子

玻璃为目录栏的本地 WebGL2 shader：对程序生成的浅色装饰背景做边缘折射和高光，鼠标按压有约 180ms 短反馈。它不采样 Windows 桌面、图片或文件文字；阅读区仍为普通 DOM。浮层背景的轻模糊是普通 CSS 效果，不称为真实背景折射。

粒子最多 16 个点、约 650ms，只在示例加载或手动“预览短反馈”时演示。开关、手动减少动画与 `prefers-reduced-motion` 均可控制；绘制结束/最小化/关闭/减少动态时停止。玻璃无持续时钟，指针绘制合并到按需帧；设备不可用/上下文丢失回退普通材质。实际文件整理完成后的触发点在第七阶段接入。

没有新增框架/包或远程资源，没有运行上游构建脚本。参考仓库固定提交 `7a424c93b9be13cf835b91ea67495fec2ec0584e`；Lens focus helper 原样复制，Overture modal helper去除示例业务、GPU/声音依赖并加短过渡/焦点恢复/关闭代际保护。完整 MIT 及逐文件来源见 vendor；Qt/Chromium 发行许可仍需第八阶段单独汇总。

## 本轮检查结果

| 检查 | 结果 |
| --- | --- |
| 原 Python 回归 | 32 项通过，涵盖匹配、审阅、冻结预览、冲突不覆盖、失败/停止/记录等 |
| Web 边界 | 11 项通过，静态白名单包含新资源且无磁盘逃逸，文件操作协议仍拒绝 |
| 前端适配器 | 8 项通过：DTO 路径/克隆、人工确认/旧版本、重复语言、跳过恢复、预览失效、执行拒绝、大列表查询、稳定选择及错误恢复 |
| 第六阶段真实 WebEngine | `work/check_web_workspace.py` 通过；没有页面 JS 或 Python 异常；预览页无注册 channel，Python 样本任务为空 |
| 原生输入与复制 | QTest 原生鼠标点击复制，读取剪贴板结果与完整视频名一致；检查后恢复原剪贴板内容；End 键实际输入滚动至第 10,000 行 |
| 审阅/弹窗 | 筛选待确认→候选三份→人工指定保留 82%→明确确认→跳过/恢复；搜索、无结果清除、稳定排序选择；预览警告与禁用执行、示例记录均检查 |
| 窗口与输入 | 1280×860 / 1000×700 / 900×620 / 最大化均无页面横向溢出；最小尺寸预览最终按钮可见；合成组合输入事件检查延后筛选，不等同于所有真实系统 IME 认证 |
| 效果边界 | WebGL2 当前机器可用；关闭玻璃/粒子、手动减少动画、空闲帧计数停止、实际最小化停止粒子、模拟上下文丢失回退及刷新重建均通过 |
| 第五阶段回归 | `check_web_foundation.py` 通过双向响应、后台事件、3 份字幕目标、样本字节不变、导航拒绝、普通/任务中刷新及等待任务结束关闭 |
| 实际桌面检查 | computer-use 在可见窗口点击待确认筛选/打开候选，Escape 关闭后观察焦点返回，打开外观设置，Ctrl+R 回到初始示例 |

环境沿用阶段 5：Windows 11，Python 3.12.0 / PySide6 与 Qt 6.12.0 / Chromium 140.0.7339.225。本阶段没有安装新依赖。

### 10,000 行观测

最后一次工作台检查：示例构造约 **114.5ms**，当前 **8 个行 DOM**，一次可见行渲染约 **4.1ms**；Chromium `performance.memory.usedJSHeapSize` 返回约 **17.1MB** 的粗粒度 JS 堆采样。搜索第 9999 行从触发到检查约 **265ms**，包含 100ms 防抖和检查等待，不是纯查询基准。

这只衡量结构化示例与前端浏览，不代表真实磁盘扫描/匹配性能或整个 Qt/Chromium 进程组内存。粒子指标采样发生在一次短反馈期间，之后另有结束/空闲及最小化停帧断言；没有据此宣称整体空闲 CPU 已验收。

### 可复现命令

```powershell
& .\.venv\Scripts\python.exe -m unittest discover -s tests -v
& .\.venv-web\Scripts\python.exe -m unittest discover -s tests/web -v
node .\work\check_web_adapter.mjs
& .\.venv-web\Scripts\python.exe .\work\check_web_workspace.py
& .\.venv-web\Scripts\python.exe .\work\check_web_foundation.py
```

Node 22+ 只用于开发检查；应用直接由 Python/Qt 运行，不依赖 Node 或开发服务器。GUI 检查需交互式 Windows 桌面。

## 截图、恢复与剩余范围

- [工作台](../outputs/stage6_workspace.png)、[候选对比](../outputs/stage6_candidates.png)、[变更预览](../outputs/stage6_preview.png)。
- [窄窗口](../outputs/stage6_narrow.png)、[最小窗口](../outputs/stage6_minimum.png)、[最小窗口预览](../outputs/stage6_preview_minimum.png)、[最大化](../outputs/stage6_maximized.png)。
- [10,000 行](../outputs/stage6_large.png)、[空目录](../outputs/stage6_empty.png)、[无字幕](../outputs/stage6_no_subtitles.png)、[读取失败](../outputs/stage6_error.png)、[外观](../outputs/stage6_appearance.png)、[回退](../outputs/stage6_fallback.png)。

截图来自实际 Qt/WebEngine 窗口，未作设计图替换；与既有阶段相同，图片为本地忽略产物，可运行检查脚本重新生成。恢复提交消息 `feat: introduce Web subtitle review workspace`，标签 `stage6-complete`。

本阶段没有新 EXE；既有第四/五阶段 EXE 的 SHA256 与历史记录相同。本阶段运行时外观偏好仅本次页面有效，刷新/切换示例重置示例审阅。生产发行必须排除 fixture 入口/资源和 `yingxuPreview` 只读开发统计。

阶段 7 待确认：真实选择/拖拽目录、后台扫描、原匹配/多语言及人工调整、Python 持有 ID/revision/冻结快照/一次性 token、文件执行/停止、结果/记录/导出；不能直接将本地 fixture 计算当作真实处理逻辑。

阶段 8 待确认：最终视觉、真实 100/125/150/200% 系统 DPI/跨屏、不同驱动、冷/热启动与整体 CPU/内存、真实大规模任务、许可清单、发行资源裁剪及无开发环境 Windows EXE 验收。当前仅在本机验证，模拟上下文丢失不等同于多设备兼容认证。安全撤销/崩溃续跑仍未实现。
