# 阶段十七：统一源码入口与清理旧版本

日期：2026-10-25。版本：0.9.0-rc.10。按用户明确要求清理历史代码和本地旧版本，不修改远端 GitHub Releases 或 Git 提交历史。

## 当前结构

- `run.py`：唯一主入口，启动当前 PySide6/Qt Quick WebEngine 工作台。
- `run.py --widgets`：当前网页的 SDR 兼容容器，保留实际业务与安全检查。
- `scripts/build.py --zip`：唯一构建入口，始终构建当前程序，无 stage 选择或旧版默认值。
- `requirements.txt` / `requirements-lock.txt`：当前依赖及完整锁定；开发依赖只补充可选图标生成。
- `assets/subtitle_organizer.ico`：应用图标；`outputs/releases/<版本>/`：当前 EXE 与 ZIP；`work/build/`：构建缓存。
- `run_subtitle_browser.py` 保留为现行在线字幕窗口的独立调试入口。

## 清理范围

移除旧 Tkinter 界面、旧 Qt Widgets 工作台、阶段五诊断后端及示例页、阶段六效果/数据演示入口、仅服务这些界面的检查与录制脚本、旧依赖和复制的单文件代码。移除前逐项验证 57 个目标文件均存在于 `fa357cc`，随后通过 Git 记录可恢复删除；图标及当前依赖属于移位整合。

当前工作台直接使用受限 LocalAdapter 和真实 Python 通信，不再根据模式加载示例适配器。保留现行协议校验、资源白名单、原 Lens 文件和全部署名；通用协议仍由现行接口使用，没有误删。共用弹窗保留模态/外观生命周期，旧示例候选/预览/记录实现删除，实际功能继续使用 LocalWorkspaceDialogs。

`core.py`、`review.py`、`operations.py` 没有修改。原预览、明确确认、不覆盖、去重、历史记录及下载导入安全机制保持。不删除用户视频、字幕、下载缓存、个人设置或本地操作记录。

## 验证状态

- 49 个 Python 源文件语法检查与修改过的 JS 语法检查通过。
- 63 项核心/字幕来源/导入单元测试、56 项 Qt 协议/资源/外观/工作台测试通过。
- 初次沙箱运行受到临时目录身份查询和 QSettings 访问限制；未降低产品安全检查，使用项目内独立临时目录及本机正常权限后通过。初次日志保留，不冒称初次通过。
- 原生及 Widgets WebEngine 两种宿主各 5 组真实受控临时样本流程通过：ZIP/直接下载、导入、人工候选和确认、冻结预览、一次执行及记录，视频和原下载保持。
- rc.10 已构建并实际启动/关闭，真实 QWebChannel、离线字体和 15 个本地资源正常；DOM 中 36 个玻璃操作/4 个结构控件，1280×860 无横向溢出，无 JS/console error。仅启动检查不验证实际绘制或动画帧，不冒称新版 EXE 媒体整理复测。
- EXE 报告实际 D3D11 / HDRExtendedSrgbLinear、HDR 活跃、10-bit、SDR 白电平 240 nit；未修改系统设置或测量物理亮度。
- 检查 EXE 内嵌归档：入口为 run，包含现行原生及兼容 WebEngine 宿主，不含 tkinter、旧 Qt UI、旧诊断后端或旧前端页；三个业务模块逐文件保持原内容。
- 完整截图/动效复验本轮未通过：源码启动等待动画帧、动态材质等待、DevTools 截图和设置关闭恢复探针出现超时；保留的旧 rc.9 EXE 对照也在画面就绪处超时。只读输入桌面探针显示 Default，不能据此断言锁屏或唯一根因。不能把 DOM 就绪、二进制检查或仅启动模式冒称视觉已通过。
- 启动阶段补充初始按钮材质同步，并在字体/DOM/通信就绪后为绘制等待设置 200ms 上限，避免被遮挡时无限等待 rAF；两种宿主启动时请求自身焦点。未改写 shader 或图形架构，也不据此声称解决所有显示问题。

## 恢复与边界

源码历史保留在 Git。此前阶段文档和测试结果属于历史证据，文件路径/命令可能已退役；当前使用方式以根目录 README 和本文为准。没有新增第三方依赖、执行外部仓库脚本或重新授权第三方组件。

原批量永久递归删除命令被自动审批拒绝，理由是范围较广。随后完成逐项 Git 恢复性核对，并获准通过 Git 删除源码。旧运行包仅在新 EXE 验证后清理；最终清单记录在本地忽略的检查目录。

本轮不重跑实站下载、干净 Windows、多屏/全部显卡或长期稳定性检查，不承诺偶发闪烁永久消除，不自动上传 GitHub。

## 本地清理与交付结果

- 已删除 33 个经核对的旧运行包、源码导出、构建缓存及测试中的旧包副本，按文件逻辑大小合计约 10.06 GiB。当前输出仅保留 `outputs/releases/0.9.0-rc.10/` 与对应的 `outputs/github-release/0.9.0-rc.10/`。
- 247 个历史截图、录制帧目录、日志/旧 spec 目标移入 `work/test-results/history-images/` 和 `history-build-logs/`，没有覆盖或丢弃历史验证记录。原已提交的素材也可从 Git 恢复。
- 主 Git 历史不变；旧公开源码暂存目录中的独立 Git 历史已完整导出并通过 bundle verify，保存在忽略的 `work/test-results/public-release-history.bundle`，随后删除旧检出目录。远端仓库和 Releases 未变更。
- 清理路径逐项解析为工作区内绝对路径，排除当前发布/构建及主 .git，检查链接与旧版运行进程后才执行。未修改项目外路径、用户媒体、下载缓存、个人设置或操作记录。
- 当前公开文件有界检查无密钥、个人邮箱、开发机绝对路径或生成文件候选；没有重写 Git 历史，没有新增依赖或许可。

证据：`work/test-results/stage17-core-tests.log`、`stage17-web-tests.log`、`stage17-native-workflow.log`、`stage17-widgets-workflow.log`、`stage17_packaged.json`、`stage17-binary-cleanup.json`、`stage17-artifact-cleanup.json`。失败探针日志同样保留；公开去路径摘要见 `docs/evidence/stage17-source-cleanup.json`。

当前 EXE：`outputs/releases/0.9.0-rc.10/YingXu/YingXu.exe`。完整运行包、匹配提交的源码和校验：`outputs/github-release/0.9.0-rc.10/`。文档同步后通过构建脚本核对编译输入再更新包内说明，不用旧 EXE 改标签。阶段结束后汇报并停止；若用户要求继续视觉修复，应基于上述未通过项单独定位，不重复无关全量检查。
