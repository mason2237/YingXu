# 阶段 20C：Electron 独立运行包与 GitHub 更新

2026-10-26。用户验收 B 后明确授权继续并发布到现有公开仓库 `mason2237/YingXu`，要求详细功能与更新说明。`0.10.0-rc.1` 已完成本机验收并公开为预发布版；未进行干净 Windows 测试，rc.12 保留回退。实际上传与匿名核对结果见文末。

## 发布结构

- `YingXu.exe`：固定 Electron 45.0.0 普通窗口，带应用图标/版本；官方 Electron ZIP 校验通过后组装，不执行 npm 安装脚本。修改资源后移除失效的原上游签名，本应用明确为未签名。
- `resources/app/`：受限主进程/preload 及应用元数据。
- `python/YingXuBackend.exe` 与 `_internal/`：冻结 Python、可替换的 Qt/MediaInfo 动态库、原业务与独立在线窗口；同一受限辅助 EXE 分派后台/在线窗口/只读轨道助手三种内部入口。
- `python/_internal/frontend/`：离线 HTML/CSS/JS、原版 Lens 和字体，同一份资源由 Electron 与 Qt 辅助窗口使用。无需开发服务器、Python、Node 或浏览器安装。
- 配置、历史和字幕缓存默认 `%LOCALAPPDATA%/YingXu/Electron/`；不写安装目录，不自动覆盖/迁移 Qt 版数据。
- 整包保留 LICENSE、NOTICE、THIRD_PARTY_NOTICES、官方 Electron/Chromium 与 Qt/字体等许可、依赖源码和库替换说明。源码 ZIP 与二进制对应，发布 SHA256SUMS。

## 执行与验收

1. 完成三种冻结助手入口、资源定位与用户数据目录，打包完整 ZIP。
2. 在当前 Windows 中以裁剪的 PATH 启动最终 EXE，验证本地扫描/人工调整/预览/确认/记录、内嵌字幕助手和独立在线窗口；不把源码窗口结果代替成 EXE 通过。
3. 基础公开审查只检查当前分发内容的密钥/个人路径/临时文件和必要许可，不重复审计全部本地历史或已通过全套功能/性能。
4. 从 GitHub 现有 main 创建干净发布提交，导入已保存源码，不推送开发仓库历史或移动旧标签。核对 GitHub 提交、Release 资产大小/摘要、匿名可见性。
5. 更新 PROGRESS、README、详细 RELEASE_NOTES 和本记录并保存提交；不重复新建任务或修改系统 HDR/权限。

## 已保留的验证边界

阶段 A 的 PresentMon + Chromium + rAF、高光浮点输出、设置/生命周期验证，以及 B 的 13 项定向测试和真实窗口/异步 ZIP 链路结果继续有效。不因打包重跑整套性能或真实网站下载。字幕网站验证码、下载按钮和片源时间轴仍需用户核对；在线字幕 UI 仍是独立 Qt 进程，不宣传为全面纯 Electron。未签名、无撤销、未测试干净 Windows/所有驱动或物理峰值亮度。

## 本机最终运行包验证

- 构建恢复点 `4058f32`；实际主 EXE 的产品名、图标、版本为映序 / 0.10.0-rc.1。证书检查为 NotSigned，未保留无效的上游签名。运行包 646 文件、约 760 MiB，许可资料 204 文件；完整 Chromium 总声明另外保留在根目录。没有应用 QML 插件树，Qt 必要原生 DLL 见 BUILD_MANIFEST。
- `check_electron_full.mjs --executable=...` 启动实际发布 EXE，子进程环境去除开发 Python/Node/Qt 的 PATH 与相关变量，工作目录改为临时目录。扫描 3 视频/2 字幕、跳过恢复、候选移除/改配/确认、预览不修改媒体、重载后重新确认、连续点击仅执行一次，2 成功/1 未匹配/1 记录，视频不变。冻结后台与独立 Qt 在线窗口握手、正常关闭通过，无 JS/Python 错误。
- `check_embedded_release.py` 对实际冻结辅助 EXE 测试 MKV/MP4、中文/英文/未知语言/独立双轨，4 次回复全部通过；预算/语言判断沿用原模块，无提取、无新媒体文件，视频字节不变；stderr 为空。
- `check_electron_faults.mjs --executable=...` 不指定 profile，将 LOCALAPPDATA 临时指向测试目录，验证默认 YingXu/Electron 数据位置和主题落盘、真实 File 拖入、后台异常退出后的提示/禁用与正常关闭。只终止本探针自己的空闲后台，媒体不变，无自动重启。
- 13 项现有 Host/只读定向测试在冻结入口改造后通过。截图已检查：主工作台来自实际发布 EXE，样本路径在截图前临时隐去；在线窗口通过 HWND/PID 绑定的 PrintWindow 获取，只捕获自己的窗口。第一次桌面区域截图被其他前台内容遮挡，已弃用，不上传那张画面。旧失败记录保留，资源编辑工具初始化失败已修复后完成构建。
- 当前待公开 446 个源码文件的模式检查没有发现密钥、开发者绝对路径、敏感文件名、缓存/临时文件或非署名邮箱；最终干净公开副本还会再核对。许可沿用 Qt/MediaInfo/字体和上游效果原文，新增 Electron 官方 MIT/Chromium 总声明与源码/构建链接。检查限定于当前分发内容，未重查全部原本地历史。

有效原始结果在忽略的 `work/test-results/electron-b-1792987701649/`、`electron-b-faults-1792987522209/`、`stage20c-embedded-reader.json`；公开摘要 `evidence/stage20c-release.json`。其中 electron-b 前缀为复用检查器生成的名称，实际测试对象为 0.10.0 的最终 EXE。旧 rc.12 的 EXE/ZIP 与本地 Git 历史均保留。

## GitHub 发布结果

- [公开 Release](https://github.com/mason2237/YingXu/releases/tag/v0.10.0-rc.1)，2026-10-26 12:19:39 香港时间（`2026-10-26T04:19:39Z`），非草稿、预发布。README 和 Release 详细介绍功能、迁移、实测、用法、限制与非商业许可。
- 本地源码快照 `de3385b9d4065fd091b1df7752d67a2a0014ed51` 导出到现有公开 main，公开源码/标签提交 `01abf23911e80c142395617c073a44edda30df1e`，没有合并本地旧历史或强推旧标签。448 个导出文件；447 个在模式审查大小范围内，当前无密钥/个人路径/临时文件命中。103 个运行相关文件逐一对照，71 个只有 Git 的 LF/CRLF 转换，其余字节一致，无代码差异。
- 运行包 `YingXu-0.10.0-rc.1-windows-x64.zip`：334,158,346 字节，SHA256 `635714efe901f67e8287d34372115546fba18ef67809273c6b10049da2d313b2`。
- 源码 `YingXu-0.10.0-rc.1-source.zip`：13,457,411 字节，SHA256 `e7952a85e6c1cf0e361a752d678d1a89581f49dee51064a28db073fc06aaa396`。
- `SHA256SUMS.txt`：199 字节，SHA256 `8e8c0d017628a4011d9e939a4822a4954c0bfd8bf5fa088466f67376f64e305a`。三个资产均 uploaded，GitHub 服务端摘要与本地一致；先上传草稿再公开，没有替换不同摘要的既有资产。
- 无登录请求 Release/README/标签 LICENSE 及三个下载 URL 全部成功（200），下载大小正确；标签 LICENSE SHA256 为 `ffcca38841adb694b6f380647e15f17c446a4d1656fed51a1e2041d064c94cc8`，与官方原文一致。大 ZIP 未重复下载，以服务端摘要交叉核对。Git 远端确认标签解析到预期提交。
- 发布使用系统 Git Credential Manager 既有授权，凭据仅在进程内存使用，未写仓库/日志。GitHub 连接用于核对仓库权限，系统 Git/API 完成源码推送与二进制 Release 上传；电脑控制工具 0 次。原 rc.12/历史提交未删除。

下载包/源码包内的“待上传”记录是发布前冻结快照，上传完成记录随后只更新到仓库 main。已发布 ZIP、源快照和版本标签不再修改；GitHub 自动源码快照与手动源码 ZIP 可能只有换行格式差异。后续开发、重新打包或发布需要新的用户任务。
