# 阶段十三：Windows 原生 HDR 与稳定合成

日期：2026-10-24。版本：0.9.0-rc.6，本地候选；不上传 GitHub。

## 实现范围

- `native_window.py` / `frontend/native/desktop.qml`：独立 Qt Quick + WebEngine 宿主，Windows 使用 D3D11/basic 渲染循环，复用原 HTML、WorkspaceBridge 和文件服务。默认 `run_web.py` 进入该宿主；`--widgets` 保留原 Widgets Web 容器，旧 rc.5 包保持。
- Qt 6.12 的 `_qt_sg_hdr_format=scrgb` 只作为请求；实际 `swapChain().format()` 和 `rhi().backend()` 才用于状态报告。该 Qt 接口为内部属性，后续升级 Qt 必须重验，不把请求成功当作输出成功。
- `display_status.py` 仅查询 Windows 显示配置，通过窗口所在 HMONITOR 的 GDI 名称对应活动路径，区分 HDR/WCG/SDR；不读取另一块 HDR 显示器作为当前屏幕状态。混合克隆目标保守处理，旧接口不能证明 HDR 时保持未知。没有调用改变显示配置的 API。
- `hdr.frag`：网页 sRGB 转线性 scRGB，按 Windows SDR 白电平/80 校正普通内容。文字保持该白电平；明亮蓝色强调按光影档位获得 0/15%/45% 高光余量。网页仍为 sRGB 内容，不宣称创造了 HDR 影像的原始细节、色域或测量了显示器峰值。实际 SDR 交换链直接输出原色。
- 外观新增“使用系统 HDR 输出”，默认开，下次启动生效；只控制应用输出，不修改 Windows HDR 开关。设置页显示真实格式/系统状态。在线字幕窗口继续使用原 SDR Widgets 容器。
- `native_actions.py` 从旧窗口提取原生动作供两个宿主复用，保留文件夹选择、打开位置、导出、下载登记、自动解压和安全关闭。核心 `core.py`、`operations.py` 未改写。

## 闪烁处理

- 桌面 WebChannel 环境取消整页 View Transition 快照，明暗切换直接更新；保留网页普通组件的轻量反馈。
- 单一 Qt Quick 场景合成窗口，最小化时保留图形/场景资源；文档加载/刷新期间冻结上一帧纹理，并显示原生遮罩，待主题、字体和前端就绪后恢复实时输出。
- 相同主题/玻璃材质/减少动态设置不重复触发 renderer 更新。原 19 份 Lens 上游文件未修改，MIT 来源记录保持。
- 最初 HDR 刷新检查出现两条 Chromium shared-image mailbox 诊断；冻结加载期纹理后，HDR 和 SDR 的最终相同检查均未再出现，EXE 最终 stderr 也无该诊断。短时观察不能证明所有驱动的偶发问题永久消失。

## 验证结果

| 检查 | 结果与边界 |
| --- | --- |
| 本机实际显示与输出 | Windows HDR 开启、10-bit，D3D11，`HDRExtendedSrgbLinear`，SDR 白电平 240 nit；真实窗口已查看，未改系统设置 |
| 外观、通信边界、导入安全 | 30 项通过；沙箱首次阻止临时路径身份/设置访问，改在本机正常权限重跑通过，未放宽产品检查 |
| 跨屏对应规则 | 4 项通过；实际仅单屏，未认证真实多显示器移动 |
| 上游 Lens 来源 | 3 项通过，保留原 19 文件；修改的是项目适配层 |
| 新 HDR 宿主核心闭环 | 5 组真实 Qt 临时样本检查通过：扫描、受控 ZIP/直接字幕下载、批量自动解压导入、候选/确认、预览、实际整理和记录；重复点击只执行一次，视频与原下载保持 |
| 保留 Widgets 容器 | 提取共享操作后同一 5 组闭环通过 |
| HDR/SDR 稳定性 | 各自通过主题切换、三种尺寸、最小化恢复、两次刷新、设置弹窗；最终 HDR 91 帧、SDR 101 帧，无 Python/JS/场景图异常；不是长期帧率基准 |
| 新 EXE | 独立工作目录及受限 PATH 启动/关闭通过；真实 QWebChannel、15 个本地资源、字体、38 玻璃操作和 4 平整结构控件、设置/快捷弹窗正常；1280×860 无横向溢出；实际 D3D11/scRGB/HDR 状态核对通过 |
| EXE 完整整理 | 本次系统文件夹选择框电脑控制失败（set-value 不支持、点击目标不匹配、刷新后激活失败），未完成；测试进程已结束。不能将源码闭环或以前 EXE 结果写成本次新 EXE 全流程通过 |
| 截图 | 实际前台 HDR 窗口已查看；Qt HDR 读回与 GDI 截图失真，不用其证明画面。EXE 的 CDP PNG 是原生 shader 之前的 SDR 网页预览，不代表物理 HDR 亮度 |

证据在忽略目录 `work/test-results/stage13-native-workflow.json`、`stage13-hdr-stability.json`、`stage13-sdr-stability.json`、`stage13-smoke_packaged.json`。首次核心闭环输出状态因屏幕名称对应问题为未知，后续 HMONITOR 修正及独立 HDR/SDR/EXE 检查已验证真实状态，不重写早期原始证据。公开摘要见 `docs/evidence/stage13-native-hdr.json`。

定向复核入口：

```powershell
.venv-web/Scripts/python.exe scripts/check_native_window.py
.venv-web/Scripts/python.exe scripts/check_native_window.py --sdr
.venv-web/Scripts/python.exe scripts/check_subtitle_imports.py --native
```

## 打包与许可

`scripts/qml_payload.py` 明确收集 18 个 QML 运行模块，当前 202 个文件/18 个插件，使用 Basic 样式；排除 designer、其他 Controls 样式及 Charts/3D/Timeline。不收集整个安装目录。构建逐文件验证 QML/前端摘要和必需 WebEngine 资源，保留 shader 源码/qsb、LGPL 动态库替换方式及既有完整许可附件。新增模块的 LGPL 路径/原署名已核对，说明见 DEPENDENCIES 和 LICENSE_STATUS；没有新增 pip 依赖或外部脚本。

EXE：`outputs/stage8-release/0.9.0-rc.6/YingXu/YingXu.exe`。完整运行 ZIP、对应干净源码与校验材料放在 `outputs/github-release/0.9.0-rc.6/`，不包含本地 Git 历史或测试媒体。不自动上传。

## 后续边界

本阶段不重复实站下载、干净 Windows、全部 DPI/驱动或万级数据验收。没有做物理亮度/色彩仪器测量，也未证明所有显卡永久无闪烁。若特定机器仍闪烁，可使用 `YingXu.exe --widgets` 或关闭原生 HDR 后重启；后续定位需要按实际触发时点收集证据。正式发布前可由操作人员补做新 EXE 的一次目录选择与整理闭环；本轮不将干净系统测试作为交付阻塞。
