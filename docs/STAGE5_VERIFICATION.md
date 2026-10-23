# 第五阶段：本地 Web 桌面基础验收

日期：2026-10-21。范围：独立 Web 宿主、资源边界、双向通信和既有核心只读样本调用。
完整工作台及局部液态玻璃/粒子效果留到第六阶段；实际用户文件整理接入留到第七阶段。

## 实现与文件

- `run_web.py`：独立桌面入口，保留原 `run_preview.py` 和全部 `yingxu/qt_ui/`。
- `yingxu/web_ui/resources.py`：同源 `yingxu://app/`，仅提供明确登记的 HTML/CSS/JS 与 Qt 自带 qwebchannel.js；拒绝未知资源、路径穿越与远程请求。
- `window.py`：QWebEngineView、独立非持久 profile、受限导航/新窗口/下载/权限、加载失败提示、Ctrl+R，以及任务未结束时延后关闭。
- `protocol.py` / `bridge.py`：v1 请求/响应/事件、白名单、严格字段与长度检查、页面会话、有限缓存内的请求去重与参数冲突拒绝。业务对象不注册到 QWebChannel；自定义 bridge 元对象仅含 request slot、reply/event signals。
- `service.py` / `workers.py`：Python 持有样本任务和结果，QThread 调用原 `collect_media`、`ReviewPlan`；`operations` 可导入但不调用执行函数。刷新页面重新握手，取回既有任务状态，不自动再发任务。
- `frontend/`：本地 HTML、CSS、ES modules；通信回声、真实后台状态、由 Python 返回的样本名称/目标名称。无开发服务器、CDN、远程字体或第三方仓库运行时。
- `requirements-web*.txt`：独立环境和精确依赖锁。`scripts/build_web.py`：独立技术 onedir 构建；`.gitignore` 排除新环境、截图和构建产物。
- `tests/web/test_boundary.py`、`work/check_web_foundation.py`：边界与实际 WebEngine 检查；原 32 项测试保持独立，不要求旧 `.venv` 安装 WebEngine。

## 本次验证

| 项目 | 结果与证据 |
| --- | --- |
| 既有核心回归 | 原 `.venv` 中 32 项全部通过；core/review/operations、旧 Qt UI 和原依赖锁无源码差异 |
| 新接口边界 | 11 项通过：畸形/过长消息、未知/文件修改动作、非法参数、Unicode、元对象接口、会话失效、重复请求/参数冲突、忙碌/关闭、静态资源边界及真实核心样本 |
| 实际 WebEngine 窗口 | `work/check_web_foundation.py` 通过：本地 HTML/CSS/ESM、握手、中文/符号/emoji 回声、后台事件和 3 份字幕目标预览 |
| 样本安全 | 程序自行创建 2 个视频和 3 份字幕的临时样本；扫描/匹配前后逐文件名称与字节一致；结束后清理临时样本，不读取用户目录 |
| 刷新与生命周期 | 普通刷新和任务运行期间刷新均建立新页面会话、保留同一 Python job；运行中关闭会等待 worker 结束，没有销毁运行线程 |
| 资源限制 | 实际外部顶层导航被拒绝；资源白名单和拦截器单测拒绝远程/任意磁盘路径、错误主机、端口、查询参数及编码路径逃逸 |
| 窗口布局 | 源码实际 1120×760、860×650 逻辑尺寸检查，无横向页面溢出；较长结果可垂直滚动；这不是多 DPI 认证 |
| 原 Qt 工作台 | 原 `.venv` 运行 `work/check_preview.py` 通过真实扫描、10 行结果、宽窄窗口、键盘、复制、选项失效、空目录/无字幕/错误路径及等待任务关闭；样本未改动 |
| 实际输入检查 | 使用 computer-use 技能在源码窗口和技术 EXE 中点击通信验证、只读样本按钮，核对 Python 回声与后台真实结果 |
| 技术试包 | PyInstaller onedir 构建成功；独立 EXE 显示本地网页并完成握手/样本调用，关闭后主进程结束 |

环境：Windows 11（10.0.26200），Python 3.12.0；PySide6/Qt 6.12.0；Qt WebEngine/Pdf 官方包 6.12.0.140，Chromium 140.0.7339.225；PyInstaller 6.17.0 / hooks-contrib 2026.8。
依赖只安装官方预编译 wheel；未执行参考仓库脚本，也未移植其代码或素材。

## 构建问题与修复

首次试包的 QtCore 导入报“找不到指定的程序”。实际分析发现宿主 PATH 中 Poppler 的 `icuuc.dll` 被误收集；该 DLL 缺少 Qt 所需的不带版本后缀的 ucnv 接口。不是匹配算法问题。
构建脚本现为子进程设置仅含独立 Python、Qt 与 Windows 目录的 PATH，并移除外部 Qt/Python 路径变量；重建产物不再收集 Poppler ICU，真实 EXE 已重新验证。没有修改系统 PATH 或旧环境。
构建工具仍会报告未使用的可选 QML assetdownloader 插件缺失及其日志格式警告；此应用使用 Widgets WebEngine，当前页面/通信/样本流程不受影响。正式发布前再处理依赖裁剪与构建警告。

## 运行与恢复

```powershell
& .\.venv-web\Scripts\python.exe .\run_web.py
& .\.venv-web\Scripts\python.exe -m unittest discover -s tests/web -v
& .\.venv-web\Scripts\python.exe .\work\check_web_foundation.py
& .\.venv-web\Scripts\python.exe .\scripts\build_web.py
```

截图：`outputs/stage5_initial.png`、`outputs/stage5_sample.png`、`outputs/stage5_narrow.png`，来自真实 Qt/WebEngine 窗口。截图为技术验证界面，不是第六阶段的最终设计。

- EXE：`outputs/stage5-tech/YingXuWebFoundation/YingXuWebFoundation.exe`。
- 需保留整个目录及 `_internal`；主 EXE 1,725,036 字节，完整目录 588,274,479 字节，3,068 个文件。
- 主 EXE SHA256：`3B9EF7E6CAC7C1FAFA625E3EECEF0A50B9F61F7013848EEB1E2A338BFC5B9EE3`。
- 包内已核对 QtWebEngineProcess.exe、qtwebengine_resources.pak、icudtl.dat、v8_context_snapshot.bin 及 en-US/zh-CN locales；HTML/CSS/JS 从打包目录加载。
- 本机一次可见启动观测：主窗口约 0.84 秒出现。此时间不代表页面完全就绪，不是冷启动/干净机基准。
- 第四阶段 EXE SHA256 仍为 `3860B7359D386A7CAB1DD34C20C3E33ECDB939EC191C3769768BE94D8F58AA55`。
- Git 恢复点：提交消息 `feat: introduce local WebEngine foundation`，标签 `stage5-complete`。

## 尚未验收的范围

完整文件工作台、真实用户目录接入、确认计划的一次性执行 token、文件整理和历史迁移属于第六/七阶段。当前请求缓存只服务技术接口，不能代替第七阶段的快照消费保护。
真实 100/125/150/200% 缩放、跨屏、大规模扫描、内存/CPU、干净 Windows、正式许可清单与包体裁剪留在第八阶段。当前技术包在本机运行通过，不等同于发布认证；此入口不会提供撤销或崩溃后自动续跑。
