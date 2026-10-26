# 9d：0.9.0-rc.1 Windows 发布候选

日期：2026-10-24。用户在 9c 提交 `ef355d6` 后再次要求继续。本轮准备本地发布物，不上传或推送 GitHub；已有公开版本保持。

## 当前结果

- 已构建 Windows x64 onedir：`outputs/stage8-release/0.9.0-rc.1/YingXu/YingXu.exe`，版本 0.9.0.1。必须保留同目录 `_internal`。
- 当前 Windows EXE 启动、真实通信、本地资源及基本界面检查通过。
- 当前源码公开内容检查、增量依赖/许可核对通过；已准备完整 ZIP 和从保存 Git 提交导出的干净源码发布材料。
- **EXE 内扫描到整理的本机复测已通过**：用户再次要求测试后成功完成原生目录选择，验证实际扫描、审阅确认、冻结预览、明确勾选、字幕整理、去重与本地记录。在线窗口入口真实返回成功；真实网站下载认证仍未完整验收。

## 版本与打包

沿用 `scripts/build_web.py --release --zip`，原版 EXE/ZIP 保留。没有安装新依赖、执行第三方仓库脚本或更改生产桥接白名单。新在线字幕/候选、下载与导入模块和 `zipfile` 均在 EXE 的 PYZ 中检查到。

实际 Qt DLL 清单和依赖版本与 0.8.0-rc.2 相同；既有 hook 继续排除不用的 QML/GPL 可选模块。构建自动检查 WebEngine helper、资源、locales、前端白名单与源摘要。196 个许可附件随包提供，官方 PolyForm 原文与根 LICENSE 相同；Qt/LGPL、上游 MIT 等独立权利保持。自写 miuix 风格未复制新第三方组件。

测试入口 `work/check_packaged_release.mjs` 保留原冒烟检查，新增可选核心流程；仅测试进程开启回环 CDP，生产启动无该端口。无需为测试给生产程序加入任意路径参数或远程执行接口。

## 验证结果与限制

| 项目 | 结果 |
| --- | --- |
| PyInstaller 构建、完整 ZIP、依赖/资源校验 | 通过 |
| 新增 6 个关键模块的 EXE 归档检查 | 通过，无缺失 |
| EXE 在独立目录与不含 Python/Node 的子进程 PATH 启动 | 通过 |
| 主窗口响应、真实 QWebChannel、离线资源与弹窗 | 通过 |
| 42/42 按钮玻璃、1280×860 无横向溢出 | 通过，实际截图已查看 |
| JS 异常、console error | 均为空 |
| 实际 EXE 内扫描/确认/整理/在线窗口复测 | 通过：扫描 2 视频，整理 1 字幕，保留 1 未匹配，1 条执行记录；在线入口返回 1 个任务 |
| 下载 → ZIP 导入 → 候选 → 确认 → 整理 | 复用 9c 的 5 组当前 Windows 真实 Qt 源码窗口结果 |
| 实际网站搜索 | 复用 9a/9b 真实结果；未重复网络调查 |
| 实际网站下载认证 | 仍未完整验收，验证码/登录由用户完成 |
| 干净 Windows / 真实多屏 / 万级性能 | 未执行；不新增这些门槛 |

本次 EXE 从启动到页面就绪约 1.402 秒，属于本机当前缓存状态的一次测量，不是冷启动或性能保证。指标/日志在忽略的 `work/test-results/stage9d_packaged.json`；截图 `outputs/stage9d_packaged_workspace.png`。增量依赖记录在 `work/test-results/stage9d-bundle-audit.json`。

电脑控制只进行应用/窗口定位，`get_window`/状态访问返回 `Computer Use app approval timed out`，没有完成输入或目录选择；恢复查询时测试已超时结束。没有随后使用其他 Windows 自动化绕过授权。普通 EXE 启动检查独立通过。

### 本轮补测（2026-10-24，已通过）

上段为初次候选交付时的历史限制。本轮用户要求“来你测试一下”，系统目录选择已经成功。使用临时合成文件，目录名含中文、空格、`&` 和单引号；全部操作均由真实 EXE 执行：

- 扫描 2 个视频和 1 份本地字幕，未匹配视频保持未匹配。
- 核对匹配和最终名称，未勾选时执行按钮禁用，原字幕字节保持。
- 勾选后连续点击两次执行，只整理 1 份并生成 1 条本地记录。
- 目标字幕名称、内容正确，目录内字幕总数仍为 1；两个视频的内容保持。
- 在线入口成功构造/显示窗口并返回 1 个任务；未搜索时没有外站页面。
- 主窗口响应正常，JS 异常和 console error 均为空，进程正常退出。

首次补测停止在一个错误的测试条件：隐藏且尚未加载网页的 WebEngineView 不一定出现在调试目标中。测试已改为监听真实 WebChannel 原生打开响应，该响应由 Python 完成窗口构造、队列绑定和显示后发出，再检查调试目标没有外站地址。没有改产品代码或虚构响应，修正后的流程通过。

证据：`work/test-results/stage9d-workflow_packaged.json`，结果截图 `outputs/stage9d-workflow_packaged_result.png`，后者已实际查看。该次页面就绪约 1.250 秒，仅为缓存状态的一次测量。在线下载/ZIP 导入仍引用 9c 的真实 Qt 源码窗口测试，本轮没有执行真实网站下载，也没有重跑无关测试。

公开检查报告 `work/test-results/stage9d-public-audit.json`：当前 397 个文件未发现所检查模式的密钥/开发路径；生成文件、敏感文件名、未解释邮箱均为空。修正 URL 安全测试里的假凭据为明确 example 占位值，测试覆盖含凭据 URL 的原意保持，相关 10 项下载/站点检查通过。检查是有界模式匹配，不承诺识别任意敏感信息；历史开发路径结论保持，旧 Git 历史不导出。

## 发布目录

保存本阶段提交后运行：

```powershell
.venv-web/Scripts/python.exe scripts/prepare_github_release.py
```

`outputs/github-release/0.9.0-rc.1/`：

- `YingXu-0.9.0-rc.1-windows-x64.zip`
- `YingXu-0.9.0-rc.1-source.zip`
- `SHA256SUMS.txt`
- `RELEASE_NOTES.md`
- `RELEASE_MANIFEST.json`（精确字节数、摘要、源码提交，`uploaded=false`）

导出脚本要求工作区已保存、当前公开检查通过，并逐项比对二进制构建记录与实际 Python/前端摘要；源码 ZIP 从 Git 提交导出，排除历史、缓存、媒体和个人配置。源码包与 EXE 不能分离版本公开。

## 续接步骤

1. 本机 EXE 核心复测已完成。以后仅在相关改动后需要复验时运行以下命令，无需重做 9a–9c：

```powershell
$env:YINGXU_CHECK_PREFIX = 'stage9d-workflow'
$env:YINGXU_CHECK_WORKFLOW = '1'
node work/check_packaged_release.mjs outputs/stage8-release/0.9.0-rc.1/YingXu/YingXu.exe
```

2. 脚本输出临时媒体路径后，在应用文件夹对话框选择该路径。后续自动验证实际扫描、确认前字节不变、一次性确认、整理/记录、视频内容保留、在线窗口离线打开；不会连接真实站点。测试进程只使用打印出的临时目录。
3. 本轮同步结果与 Release Notes，使用 `build_web.py --finalize-existing --zip` 仅更新文档/校验及压缩包，EXE 本体不重编译；保存新提交再导出源码包。
4. 上传新版需明确发布指令；沿 `PUBLISHING.md` 的独立干净历史同步，不能推送本地旧历史。

本轮恢复提交消息：`release: prepare 0.9.0 candidate with verified startup and documented limits`。

补测恢复提交消息：`test: verify packaged scan and organization workflow`。已完成本机核心验收，公开上传仍等明确指令。
