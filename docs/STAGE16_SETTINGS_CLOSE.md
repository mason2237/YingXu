# 阶段十六：移除快捷操作与设置关闭过渡

日期：2026-10-25。版本：0.9.0-rc.9，本地修复候选，不自动上传。

## 实现

- 完整移除顶部快捷操作入口、Ctrl+K、命令弹窗、动作控制器及专用 CSS；保留 Ctrl+F、Ctrl+Enter、列表选择和其他真实功能。候选/记录仍使用共用空状态样式，文件扫描中的同名变量不属于该功能。
- 仅设置启用 140ms opacity 关闭动画，遮罩同步淡出，不加缩放、位移或整页模糊。淡出后等待至多两个绘制帧再移除顶层；动画和帧等待均有有界超时，隐藏页面不会卡住关闭。
- 关闭后继续保持背景特效暂停 120ms，避免恢复背景与移除弹窗在同一帧发生。随后恢复原动效并让原生帧泵按旧策略停止。重开会取消延后恢复，销毁时清理定时器。
- 按钮、Esc、外部点击共用关闭生命周期。退出时重开由代次保护，旧关闭不能关掉新弹窗；减少动态/隐藏/显式即时关闭直接完成。焦点返回设置按钮使用 preventScroll，不使工作台滚动。
- 保留原生 HDR、明暗、玻璃按钮和既有遮挡防护，不修改 Windows 设置；没有修改核心业务、文件权限、QWebChannel 接口、依赖或原 Lens 19 个源文件。上游改编说明同步保留 MIT 署名。

## 修改范围

前端：`workspace.html`、`js/workspace.js`、`js/components/dialogs.js`、`glass-controls.js`、`upstream-effects.js`、`css/feedback.css`、`lighting.css`，以及改编的 `vendor/design-systems/modal.js`、`workspace-overlays.js`、`UPSTREAM.md`。

验证：新增 `scripts/check_settings_close.py`，更新 `work/check_packaged_release.mjs`。旧 `check_modal_compositor.py`、`check_wheel_compositor.py` 对不含命令面板的当前版明确提示改用新检查，历史报告保留。`yingxu/version.py` 升为 rc.9。进度、主计划、README、发布说明及实际工作台截图同步。

## 已完成验证

| 范围 | 结果 |
| --- | --- |
| 源码 SDR / HDR | 各 8 次设置关闭通过，按钮/Esc、滚动后关闭、重开及减少动态均覆盖 |
| 动画及恢复 | rAF 采样存在中间透明度和 140ms 动画；关闭后背景回到 20.17 的归一化诊断基线，焦点正确，闲置帧泵停止 |
| 定向单元/来源 | 18 项通过；JS 语法通过 |
| 源码文件安全闭环 | 5 组通过，实际受控 Qt ZIP/直接下载、导入、候选、人工确认、冻结预览、一次执行及记录；视频及原下载保持 |
| 当前 EXE | 实际启动及 6 次设置关闭通过，每次 11 个淡出采样帧；快捷操作不存在，Ctrl+K 不打开弹窗 |
| EXE 界面/输出 | 1280×860 无横向溢出；15 个本地资源、离线字体、36 个玻璃操作和 4 个结构控件；无 JS/console error |
| HDR 保留 | 实际 D3D11 / HDRExtendedSrgbLinear，Windows HDR 开启、10-bit、SDR 白电平 240 nit；关闭 HDR 偏好时实际 SDR |

正常源码检查无 Python/场景图错误；EXE stderr 仅临时本地测试调试入口。单次缓存启动 1.842 秒只作记录，不作为性能基准。全部测试使用独立设置、空工作台或可丢弃样本，不处理个人媒体。

证据保留在忽略目录：`work/test-results/stage16-hdr-settings.json`、`stage16-sdr-settings.json`、`stage16_packaged.json`；本次文件闭环沿用工具输出名 `stage13-native-workflow.json`。公开去路径摘要见 `docs/evidence/stage16-settings-close.json`。

```powershell
.venv-web/Scripts/python.exe scripts/check_settings_close.py --sdr
.venv-web/Scripts/python.exe scripts/check_settings_close.py
.venv-web/Scripts/python.exe -m unittest tests.web.test_lens_sources tests.web.test_render_flags tests.web.test_appearance
.venv-web/Scripts/python.exe scripts/check_subtitle_imports.py --native
.venv-web/Scripts/python.exe scripts/build_web.py --release --zip
$env:YINGXU_CHECK_PREFIX='stage16'
node work/check_packaged_release.mjs outputs/stage8-release/0.9.0-rc.9/YingXu/YingXu.exe
```

## 验证边界与交付

额外用每 20ms 的 QQuickWindow.grabWindow 强制读回去观察退出时，探针触发 D3D 读访问/SkSurface/上下文丢失诊断，说明该采样会干扰渲染，已从测试移除。不能将此侵入式压力探针写成通过，或仅凭它推断日常关闭的唯一根因。正常源码与 EXE 检查随后通过。本轮只在动画期间采浏览器帧，原生背景在关闭前后取样，没有可靠的完整 HDR 连续帧序列。

实际 EXE 截图已查看，保存为 `outputs/stage16_packaged_workspace.png` 和 `outputs/stage16_settings.png`；它们是原生 HDR shader 之前的网页画面，不证明物理 HDR 峰值。短测不能保证所有驱动的偶发闪烁永久消除。未重复实站字幕下载、干净 Windows、多屏/全驱动或长期验收；新 EXE 的媒体执行没有重跑，源码完整闭环与历史 EXE 结果独立记录。

EXE：`outputs/stage8-release/0.9.0-rc.9/YingXu/YingXu.exe`。完整运行包、匹配提交的源码和校验材料：`outputs/github-release/0.9.0-rc.9/`。不新增 pip/Qt/QML 依赖或素材，沿用既有白名单、197 份许可附件及 PolyForm/第三方许可边界。保留 rc.8、全部 Git 历史和旧测试；本阶段完成后汇报暂停，不自动上传或跨入新阶段。
