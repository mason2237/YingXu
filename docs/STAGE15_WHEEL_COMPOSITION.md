# 阶段十五：完整列表滚轮合成修复

日期：2026-10-24–25。版本：0.9.0-rc.8，本地修复候选，不自动上传。

## 依据与实现

用户提供了鼠标滚轮期间的坏帧：快捷操作弹窗保留顶部几项，其余区域大片空白。阶段十四主要检查了过滤后单项结果及脚本设置 scrollTop，不能覆盖完整列表的真实滚轮路径，本轮补齐该缺口。

- 完整快捷列表保留液态玻璃颜色、亮边、悬停/选中反馈与原生 HDR；取消列表项逐个 backdrop-filter 与弹簧 transform。其他工作台操作按钮的拖动反馈保持，滚动项仍可点击和使用键盘。
- 本地桌面弹窗使用非被动 wheel 监听，把滚动偏移与文字绘制放在同一主线程提交中，避免独立快速滚动层先于 HDR 源纹理前进。仅接管实际可滚动的弹窗容器，支持像素/行/页单位；Ctrl/Meta/Alt 滚轮保持原行为。主文件列表和普通浏览器预览不采用该处理。
- 新宿主在本进程请求关闭 Chromium `CalculateNativeWinOcclusion` 窗口遮挡推断，降低嵌入窗口/纹理被误判为无需绘制时出现旧帧的风险。参数在 WebEngine 初始化前设置，保留其他开关；识别到已有 disable-features 时合并，不认识的格式保持原值。未更改 Windows、浏览器安装设置、GPU 安全设置或用户文件。
- 遮挡优化关闭可能使被其他窗口覆盖的页面继续绘制；现有最小化/隐藏和弹窗关闭后停帧机制保持。该处理是兼容防护，不将其冒称为本机已严格证明的唯一根因。
- 没有修改文件扫描、匹配、整理、预览/确认或不覆盖规则，也没有新增通信能力、依赖或第三方素材。原 Lens 文件保持。

背景参考：[Chromium Windows 遮挡 feature 定义](https://chromium.googlesource.com/chromium/src/+/refs/tags/141.0.7348.0/ui/base/ui_base_features.cc)、[CEF 嵌入窗口空白问题记录](https://github.com/chromiumembedded/cef/issues/3638)。这些资料只用于确定防护方向，不等同于对本机坏帧的根因证明。

## 测试与证据

新增 `scripts/check_wheel_compositor.py`，通过 Qt `QTest.wheelEvent` 注入原生输入；浏览器确认 `isTrusted=true`，并核对同步滚动的 defaultPrevented 标记。使用真实未过滤的 14 项快捷操作，覆盖上下往返、边界和快速连续滚动，设置页同样使用滚轮。

- 最终 HDR 与 SDR 各通过 90 次完整快捷列表滚轮、8 次设置页滚轮。初始列表实际呈现后才开始输入；检查全部可见行的绘制覆盖，不能仅看 DOM 数量或 JS 无报错。
- SDR 检查完整原生合成帧。当前 Qt 的 HDR grabWindow 使用 8-bit 描述符包装浮点读回字节，本轮先验证 half-float alpha/范围，再只读取字节确实覆盖的上半帧行；不会读取缓冲区之外，也不把结果当作完整 HDR 截图或亮度测量。
- 较早的检测仅采文字小矩形，会把 DOM/画面一帧的位置差误判为丢字，已改为完整行区域；启动尚未呈现的帧也独立处理。最终检查仍保留每行覆盖阈值，没有为了通过而忽略失败行。
- 中途快速收尾检查捕捉到旧帧，增加遮挡防护后才完成上述最终连续检查。旧版短测也曾通过，因此不能声称已在本机稳定复现用户那张完全相同的坏帧、或证明所有驱动永久无问题。
- 4 项 Chromium 参数保留/合并契约与 3 项 Lens 原文件来源检查通过，JS 语法检查通过。
- 最终 EXE 通过 12 次完整列表 Chromium 滚轮，最大滚动 202px；14 项保持、逐项模糊/变换关闭、事件可信并被同步处理。D3D11/scRGB/HDR 活跃、10-bit/240 nit 系统白电平、15 个本地资源及 38 玻璃操作/4 结构控件保持，无横向溢出，无 JS/console error。
- 实际 QtWebEngineProcess 命令行已核对包含遮挡防护 feature，检查只输出布尔结果，不导出完整命令行。最终 EXE 网页截图已查看；位于 HDR shader 之前，不能证明物理 HDR 亮度。

最终证据：`work/test-results/stage15-hdr-wheel.json`、`stage15-sdr-wheel.json`、`stage15_packaged.json`，公开摘要见 `docs/evidence/stage15-wheel-composition.json`。旧短测基线与中途日志保留在忽略目录，不进入公开源码。测试使用独立设置和空工作台，不处理个人媒体。

```powershell
.venv-web/Scripts/python.exe scripts/check_wheel_compositor.py --sdr --stress
.venv-web/Scripts/python.exe scripts/check_wheel_compositor.py --stress
```

## 交付与边界

EXE：`outputs/stage8-release/0.9.0-rc.8/YingXu/YingXu.exe`。完整运行包、匹配源码与校验材料：`outputs/github-release/0.9.0-rc.8/`。rc.7 和全部 Git 历史保留；进度和计划同步。

无新增 pip/Qt/QML 模块，沿用现有白名单、197 份许可证附件及 PolyForm/第三方许可边界。本轮未重复文件整理、实站下载、干净 Windows、多屏/全驱动或长期稳定性验收。HDR 合成效果保持；最终结果是经过扩大滚轮检查的修复候选，仍须以用户实际环境的滚轮表现核对，不能仅凭这次短测保证全部偶发帧已经消除。
