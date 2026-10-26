# 映序 0.10.0-rc.1 使用说明

完整解压后双击 `YingXu.exe`，保留所有相邻 DLL、`resources` 和 `python`。Windows 11 x64，无需另装 Python、Node、浏览器或开发服务器。

1. 选择/拖入含视频与字幕的文件夹，设置递归和字幕移动选项。
2. 搜索/筛选并核对匹配，人工选择、更换、确认或跳过字幕。
3. 缺字幕时，打开“在线字幕”，确认片名、选择并下载；默认自动解压并加入待确认。
4. 预览原名称、最终名称和冲突，勾选确认后才整理。
5. 查看结果与本地操作记录，可导出 JSON。目前无撤销。

媒体本地处理，不上传；扫描/预览不修改文件、不覆盖已有目标。视频内已有符合语言要求的独立字幕轨时直接通过，不导出或改写视频；扫描选项可调整语言要求，详情可手动改判。语言依赖片源元数据，硬字幕不做 OCR。

主工作台采用 Electron，保留明暗/跟随系统、液态玻璃、果冻按钮、真实进度和减少动态。系统 HDR 已开启且设备支持时有局部浮点高光，不修改 Windows 开关。可在设置关闭 HDR/动效；`--effects=moderate` 关闭次要雾气/粒子，`--preview` 为禁用改配、执行和在线窗口的只读模式。

在线窗口为独立 Qt 辅助进程：字幕库优先，SubHD/备用来源，无 API Token，默认中英双语优先、语言偏好可保存。搜索只发送确认后的片名，验证码/下载按钮需用户操作。缓存保留原包，有来源/格式/大小/路径检查，默认自动解压；支持 ZIP 及系统 tar 支持的 RAR/7z。最终仍需回到工作台确认整理；缓存不自动清空或跨会话恢复候选。

数据默认 `%LOCALAPPDATA%/YingXu/Electron/`：外观 `appearance.json`、记录 `python/history.jsonl`、下载 `python/subtitle-inbox/`。与旧 Qt 版隔离，不自动迁移；有待确认下载时勿删缓存。更新建议解压至新目录，保留旧 rc.12 回退。

快捷键：Ctrl+F 搜索、Ctrl+Enter 预览；方向键、Home/End/PageUp/PageDown 选择，Enter 详情。详细功能、更新、性能方法与验证边界见 RELEASE_NOTES.md 和 docs/STAGE20C_RELEASE.md。

本版为未签名预发布版，未进行干净 Windows 测试或所有设备认证。原创代码采用官方 PolyForm Noncommercial 1.0.0，依许可可个人免费使用、学习、修改、非商业性再分发，商业用途须单独授权；第三方许可独立。见 LICENSE、NOTICE、THIRD_PARTY_NOTICES.md、LICENSE_STATUS.md、licenses/ 与 docs/DEPENDENCIES.md。包内摘要供核对下载，不阻止 LGPL 库替换。
