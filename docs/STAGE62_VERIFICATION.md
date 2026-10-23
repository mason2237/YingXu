# 6.2 增强玻璃、明暗主题与偏好验收

日期：2026-10-22。授权：“就使用增强效果，开始”。仅实施 6.2；6.3 / 7 / 8 继续等待确认。默认增强玻璃，原业务模块、原 Qt 入口和既有 EXE 保留。

## 本次交付

1. 浅色 / 深色 / 跟随系统，顶部快捷选择与外观面板共享状态。
2. 语义化阅读、列表、详情、状态、弹窗、通知、输入、焦点、禁用、滚动条和兼容材质；深浅背景及原版 GPU 染色同步。
3. 180ms 主题虹膜转换，减少动态时立即应用；连续切换可取消，筛选、搜索、选中、人工审阅和打开的弹窗保持。
4. 固定 QSettings 外观存储、损坏数据回退及写入失败提示。DocumentCreation 引导、WebEngine 背景、Qt palette 和 Windows 标题栏在显示前适配，刷新/重新打开恢复。
5. 工作台 / 原版对照页注册独立外观对象；无文件整理或任意系统接口。实际整理继续使用第四阶段工作台。

### 来源与适配

- 固定参考仓库 [design-systems](https://github.com/ruiqichenbiec/design-systems/tree/7a424c93b9be13cf835b91ea67495fec2ec0584e)，MIT。6.1 采用的 19 个 Lens 文件在本阶段未改，Git blob 核验继续通过。
- 新 `theme-transition.js` 定向改编 [Overture dynamics.js](https://github.com/ruiqichenbiec/design-systems/blob/7a424c93b9be13cf835b91ea67495fec2ec0584e/overture/src/dynamics.js) 的 transition/focusPoint。原版 760ms 缩为 180ms，ES module、可取消、减少动态/隐藏/不支持回退和错误清理；属于改编，未标为原样复制。
- 光学算法及工厂保持原文件；适配器更换自绘背景，工作台深色使用原 shader 的 ocean 暗色染色，浅色使用 grid。对照页四种内置场景保留原始配色，旧简化列保留浅色基线。
- 粒子仍为映序既有短反馈，改用当前语义色；未冒充 Lattice 点场。音效继续默认关闭。没有执行参考仓库脚本、引入前端框架或新运行依赖。

## 修改文件与责任

| 文件组 | 内容 |
| --- | --- |
| `yingxu/web_ui/appearance.py` | 五项偏好白名单、QSettings、原生系统观察、启动脚本和 palette/DWM |
| `yingxu/web_ui/window.py` / `resources.py` | 页面隔离、外观 channel、首次显示/刷新背景及显式资源清单 |
| `frontend/js/appearance.js` | 外观状态、QWebChannel 客户端、主题控件联动、错误反馈 |
| `frontend/vendor/design-systems/theme-transition.js` | Overture 虹膜定向改编 |
| `frontend/css/{tokens,appearance,components,workspace,lens-adapter,effects-lab}.css` | 两套语义色、阅读与状态、原版控件覆盖层、主题选择与过渡 |
| `frontend/workspace.html` / `effects.html` 及相关 JS 适配器 | 快捷选择/面板、GPU/粒子同步、偏好联动及预览边界说明 |
| `tests/web/test_appearance.py` | 默认/持久化/拒绝/损坏/写入失败/系统变化/桥接表面/启动脚本 |
| `work/check_theme_preview.py` / `check_theme_transition.mjs` | 实际窗口主题检查与转换原语检查 |
| `work/check_web_workspace.py` / `check_lens_preview.py` | 原有回归调整为临时 INI 与外观唯一对象，避免污染用户设置 |
| `work/record_theme_preview.py` / `encode_theme_recording.py` | 实际窗口录制、按采集时间编码，不合成虚假 UI 帧 |
| README / PROGRESS / 设计、接口、来源与清单文档 | 当前状态、恢复和阶段边界 |

外观对象的专有元方法仅 `getState()`、`update(QString)`、`changed(QString)`。未知键整条拒绝，布尔值不接受 0/1，theme/strength 只接受固定枚举；不接受 path、command、action 或文件处理参数。QSettings 使用 `YingXu/SubtitleOrganizer` 和固定 `appearance/v1`；测试均注入临时 INI，不写用户注册表。

## 检查结果

环境：Windows、本机 Qt/PySide6 6.12.0、Chromium 140.0.7339.225、Python 3.12.0。旧环境和 Web 环境隔离保持。

| 检查 | 结果 |
| --- | --- |
| 原业务 unittest（`.venv`） | 32 / 32 |
| Web 边界、原版来源、外观 unittest（`.venv-web`） | 23 / 23 |
| 前端测试适配器 | 8 / 8 |
| 原版材质 / 物理 / PCM | 7 / 7 |
| 主题转换原语 | 5 / 5 |
| **单项合计** | **75 / 75** |
| 6.2 实际 Qt/WebEngine | 通过：深色启动/首次注入、两处选择同步、180ms 虹膜、减少动态、刷新/新窗口、连续切换、筛选/选中/人工审阅与焦点保持 |
| 原工作台实际窗口回归 | 通过：搜索/输入法、键盘、原生点击复制、候选/确认/跳过、预览/记录、空/错/无字幕、窗口、大列表、效果/停帧、GPU 丢失恢复 |
| 18 类原版工厂回归 | 通过：交互、键盘、拖动、弹窗、停帧/销毁、无 WebGL 回退；去除光学几何后像素对照仍有明显差异 |
| 第五阶段基础通信回归 | 通过：本地资源、双向通信、后台样本、3 份目标、样本未变、刷新、外部导航拒绝、任务中刷新与延后关闭 |

6.2 还检查了深色原版/增强对照及弹窗自身画布。900×620、1000×700、1280×860 均未见页面横向溢出；最小窗口外观面板可以滚动。连续主题切换后空闲帧不再增加。

实际 DOM 文字/不透明背景合成抽样：11 类正文及辅助信息，浅色最低 **4.72:1**、深色最低 **5.32:1**。未覆盖所有控件、GPU 纹理下的文字、禁用状态或所有字号；这是局部可读性检查，不是完整无障碍认证。

原工作台最后大列表观测：10,000 行 / 8 个行 DOM，可见行一次渲染约 3.6ms、示例构造约 110.2ms，JS 堆粗采样 23.1MB；搜索观测 250ms 含防抖与等待。这些不是磁盘扫描或全进程内存基准。

### 验收中修复

- Qt 6.12 scripts.find 返回列表，逐项替换引导脚本。
- PySide 对直接连接的未装饰绑定方法可能动态发布 slot；原生系统事件使用私有转接，并核对专有元方法白名单。
- Chromium 在 View Transition 快照更新时暂停 requestAnimationFrame，等待它会超时；改为适配器同步重绘/flush GPU 配色。
- 取消主题转换时立即移除过渡类；主题更新与设置回复重复到达不重复应用。
- 提高浅色辅助/选中行文字及警告状态对比度；保存失败恢复控件显示到实际状态。

## 运行与复核命令

```powershell
& .\.venv-web\Scripts\python.exe .\run_web_preview.py
& .\.venv-web\Scripts\python.exe .\run_effects_preview.py
& .\.venv\Scripts\python.exe -m unittest discover -s tests -v
& .\.venv-web\Scripts\python.exe -m unittest discover -s tests/web -v
node .\work\check_web_adapter.mjs
node .\work\check_lens_math.mjs
node .\work\check_theme_transition.mjs
& .\.venv-web\Scripts\python.exe .\work\check_theme_preview.py
& .\.venv-web\Scripts\python.exe .\work\check_web_workspace.py
& .\.venv-web\Scripts\python.exe .\work\check_lens_preview.py
& .\.venv-web\Scripts\python.exe .\work\check_web_foundation.py
```

应用运行不需要 Node 或 Pillow；后者只用于录制编码开发步骤。

## 真实界面证据

- `outputs/stage62_workspace_dark_final.png`、`stage62_workspace_light_final.png`：1280×860 真实 WebEngine 工作台。
- `stage62_native_workspace_dark.png`、`stage62_native_workspace_light_final.png`：通过 Qt 屏幕 API 截取本应用实际窗口，包含 Windows 标题栏；已目视核对两种配色。
- `stage62_appearance_dark.png`、`stage62_appearance_minimum_dark.png`、`stage62_minimum_dark.png`：设置及最小窗口。
- `stage62_fallback_dark.png`：关闭玻璃时普通深色材质；`stage62_comparison_dark.png`、`stage62_lens_dialog_dark.png`：原版对照与弹窗。
- `stage62_regression_*.png`、`stage62_lab_*.png`：既有流程重验，保留 6.1 证据文件。
- `outputs/stage62_theme.gif`：41 帧实际 Qt 抓取，约 3.57 秒、2,228,679 字节；按真实采集间隔编码，包含静置和三次切换，不表示应用的帧率基准。源帧 `outputs/stage62_motion_frames/`。

截图、GIF/源帧为可再生成的忽略产物。本轮电脑控制工具调用 **0**；没有外部桌面点击遍历或改变 Windows 设置。

## 边界、问题与恢复

- 系统跟随使用 QStyleHints 的实际初始值；变化通过受控调用原生事件处理验证，未切换用户 OS 主题。真正 OS 切换、不同缩放/显卡/干净设备还需阶段 8。
- DWM setter 在本机成功，标题栏截图已核对；caption 属性的 getter 本机不支持，未将 setter 返回值写成读回验证成功。
- 未人工试听音效。Lattice 点场及余下适用效果留 6.3；文件操作及安全整合留 7；正式 EXE 留 8。
- 未修改 `core.py`、`review.py`、`operations.py` 或旧 Qt UI。旧 EXE SHA256：阶段 4 `3860B7359D386A7CAB1DD34C20C3E33ECDB939EC191C3769768BE94D8F58AA55`；阶段 5 技术版 `3B9EF7E6CAC7C1FAFA625E3EECEF0A50B9F61F7013848EEB1E2A338BFC5B9EE3`，与原记录相同。
- 恢复提交消息 `feat: add persistent light and dark appearance`，标签 `stage6-2-complete`；以前的 stage6-1 / stage6 / stage5 / stage4 标签保留。完成提交后以 `git show stage6-2-complete` 查唯一提交。

下一步：用户验收本阶段后再实施 6.3。未将对照页示例值或动效表示为真实文件处理结果。
