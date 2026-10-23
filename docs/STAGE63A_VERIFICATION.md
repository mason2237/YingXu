# 6.3a 气态列表与液态操作按钮验收

日期：2026-10-22。用户指定列表截图及详情/预览按钮，要求气态列表和液态玻璃按钮。本轮为定向 6.3a，不将其表述为整个 6.3 或真实业务整合已完成。

本文保留原始交付和 80 项检查记录；随后按用户反馈修订的细雾、光丝、薄玻璃和帧率情况见 [STAGE63A_REFINEMENT.md](STAGE63A_REFINEMENT.md)，不能把下述历史结果当成本次修订重新运行的结果。

## 实现与来源

- `frontend/js/components/list-mist.js`：项目自写的 WebGL2 fBm/域扭曲雾气。全列表一个低分辨率画布，位于文字/虚拟行下方；行内轻雾、悬停聚拢、选中增强，限制 alpha 并提高辅助文字对比度。它是程序化视觉，不是物理气体模拟或 Lattice 点场源码。
- `frontend/js/components/liquid-actions.js`：复用原版 Lens 渲染器和 Jelly 手势。详情“更换/确认、跳过/恢复”共用画布，底部“预览变更”另用一个；画布按真实按钮轮廓裁切，文本、键盘和点击仍在原按钮上。
- `frontend/js/components/inspector.js`：底部真实按钮保持节点身份，标签/主次状态/回调随当前行更新。避免每次选择都替换节点、积累手势 body 或新建上下文。
- `frontend/css/materials.css`：双主题雾气层、材质按钮、普通/禁用/GPU 回退；`workspace.html` 加载资源并新增独立气态开关。
- `upstream-effects.js`、`dialogs.js`、`appearance.js` 与 Python `appearance.py`：配置、统计和严格布尔 `mistEnabled`，默认 true；原五字段设置兼容加载。固定键 appearance/v1 现为六项，仍只允许外观方法，没有增加文件或命令能力。
- `workspace.js`：新载入开始时清理前一次示例通知，避免“0 条载入”覆盖新数据状态。

原版 Lens 19 文件及 Git blob SHA 未改变；未引入新依赖、外部资源或运行第三方构建脚本。工作台现在有四个 Lens 画布、一个雾气画布，共十个玻璃表面；粒子仍为已有独立短反馈。

### 运行约束

- 雾气约 30 次/秒按需绘制，使用时间戳限制高刷新率屏幕的 GPU 工作；停止操作后 0.45–1.8 秒结束动态，保留静态背景。
- 系统/手动减少动态时没有时间流动或指针漩涡；选中与主题变化即时更新静态材质。最小化、隐藏、空列表和关闭效果时停止。
- 无 WebGL 使用普通列表/按钮；上下文丢失时回退并延后恢复。页面退出释放监听、定时器、GL 对象及画布，不强行 loseContext 触发 Qt mailbox 问题。
- 原来搜索、候选、确认、跳过、预览、安全限制和旧 Qt 入口保持。此 Web 入口仍是显式示例，执行真实文件整理按钮不因材质更新而获准。

## 检查

环境仍为 Python 3.12.0、Qt/PySide6 6.12.0、Chromium 140；原业务在隔离的旧环境运行。

| 检查 | 结果 |
| --- | --- |
| 原业务 unittest | 32/32 |
| Web/来源/外观 unittest | 24/24，新增旧设置补全雾气默认值；非法类型仍整条拒绝 |
| 前端适配器 | 8/8 |
| Lens 数学/物理/PCM | 7/7 |
| 主题转换原语 | 5/5 |
| 雾气调度 | 4/4：60/120/144/240Hz 时间戳、空闲队列清空、停止条件、长帧限幅 |
| **单项合计** | **80/80** |
| 新材质实际窗口 | GPU 初始化、原生预览按钮按压/打开、雾气/按钮像素对照、25 次选择节点稳定、独立开关、静态模式、停帧、最小化、上下文恢复、空列表、10,000 行、无 WebGL、销毁检查通过 |
| 原工作台实际窗口回归 | 搜索/输入法、排序/筛选、候选/确认、跳过恢复、原生复制、预览/记录、空错/无字幕、窗口及 GPU 回归通过 |
| 明暗/偏好实际窗口回归 | 浅/深/系统、180ms 转换、状态与焦点保持、刷新/新窗口恢复、连续切换、最小窗口及原生标题栏通过 |

实际截图逐张检查了雾气强弱、文字、主次按钮、按压与窄窗口；降低普通行纹理频率与强度、降低主按钮亮部、移除操作组继承的外层大圆角，只保留真实按钮玻璃边缘。

一次冻结画面并仅隐藏材质画布的对照：雾气区域约 71,102 个四分之一采样像素变化，按钮约 18,350；证明有实际 GPU 图像参与，不能据此推导显示帧率或完整可读性认证。最终数据可由脚本重新采集。

原工作台 10,000 行最后观测：8 个行 DOM，一次可见行渲染约 3.5ms、示例构造约 112.7ms、JS 堆粗采样约 26MB；搜索观测约 281ms 含防抖和等待。定向材质检查在顶部区域渲染 12 行，雾气仍只一个画布。不是磁盘扫描、GPU 内存或全进程性能基准。

原主题检查的 DOM 色彩采样继续通过；它不包含 GL 纹理的全部像素、禁用文字和所有控件，未据此声称完整无障碍认证。实际文字不经过雾化或折射。

## 命令和证据

```powershell
& .\.venv-web\Scripts\python.exe .\run_web_preview.py
& .\.venv-web\Scripts\python.exe .\work\check_materials_preview.py
& .\.venv-web\Scripts\python.exe .\work\check_web_workspace.py
& .\.venv-web\Scripts\python.exe .\work\check_theme_preview.py
& .\.venv-web\Scripts\python.exe -m unittest discover -s tests/web -q
& .\.venv\Scripts\python.exe -m unittest discover -s tests -q
node .\work\check_web_adapter.mjs
node .\work\check_lens_math.mjs
node .\work\check_theme_transition.mjs
node .\work\check_mist_scheduler.mjs
```

本次受限环境中 QSettings 默认临时位置写入失败、WebEngine GUI 直接退出；设置测试改用 `work/test-results/stage63-temp`（只给测试进程设置 TEMP/TMP），GUI 经工具审批在正常桌面运行。没有关闭 Qt/WebEngine 安全选项。`YINGXU_CAPTURE_PREFIX` 可为旧检查指定新文件名，避免覆盖原阶段证据。

- `outputs/stage63a_final_light.png` / `stage63a_final_dark.png`：最终双主题。
- `stage63a_liquid_press_light.png`：真实 QTest 按压；`stage63a_minimum_dark.png`、`stage63a_no_webgl_dark.png`、`stage63a_plain_buttons_dark.png`：最小窗口与回退。
- `stage63a_regression_*.png`、`stage63a_theme_*.png`：已有流程/主题重验。
- `outputs/stage63a_materials.gif`：48 帧、约 3.34 秒、5,244,619 字节的真实 Qt 抓取与 QTest 指针输入，展示雾气流动、原生按钮按压、预览打开/关闭后的明暗转换。源帧目录 `outputs/stage63a_motion_frames/`；采集脚本 `work/record_materials_preview.py`，编码器为原工具新增可选参数，未合成 UI 帧。

截图与录制是可再生成的忽略产物，代码/采集脚本随本轮提交。电脑控制工具调用 0 次。

## 剩余范围与恢复

- 这次只处理用户圈出的列表和主操作按钮；其余菜单、弹窗、通知、加载等材质/效果继续按 6.3b 清单评估。Lattice 点场未冒充已采用。
- 真实 OS 设置切换、多显卡与全部 DPI/干净 Windows 验证、真实文件接口、正式打包仍为后续阶段。未新增可执行成品。
- `core.py`、`review.py`、`operations.py` 和旧 Qt UI 无修改。阶段 4 / 5 EXE 的 SHA256 与前阶段相同，仍分别为 `3860B7359D386A7CAB1DD34C20C3E33ECDB939EC191C3769768BE94D8F58AA55` / `3B9EF7E6CAC7C1FAFA625E3EECEF0A50B9F61F7013848EEB1E2A338BFC5B9EE3`。
- 提交消息 `feat: add vapor list and liquid glass actions`，恢复标签 `stage6-3a-complete`；6.2 恢复点 `a78ce6d` / `stage6-2-complete` 保留。

阶段结束等待用户视觉验收，不自动进入 6.3b、7 或 8。
