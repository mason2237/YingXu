# 映序 · Windows 预发布版

解压完整压缩包，打开 `YingXu/YingXu.exe`。请保留同目录的 `_internal` 文件夹，不能单独复制 EXE。

- 无需手动运行 Python、Node、浏览器或开发服务器；应用页面和效果均随包提供，不上传文件。
- 选择目录 → 扫描 → 审阅匹配 → 预览变更 → 勾选确认 → 整理。低可信匹配请先确认或手动更换。
- 文件名冲突不会覆盖已有文件。关闭正在工作的窗口会等待当前文件安全结束。
- 右上角切换明暗主题；外观设置可关闭玻璃、雾气和粒子，或开启减少动态。玻璃按钮支持轻拖回弹，拖动不触发点击。
- 操作记录保存在 `%LOCALAPPDATA%/YingXu/history.jsonl`；外观偏好保存在当前 Windows 用户的 `YingXu/SubtitleOrganizer` 设置中。该包没有撤销功能。

当前 Windows 11 x64 环境已验证启动；核心业务和真实整理闭环结果沿用同一业务代码的已完成测试。未进行干净 Windows 系统测试，也未认证所有设备/跨屏组合。EXE 未签名。

原创部分采用 PolyForm Noncommercial License 1.0.0（完整原文在 LICENSE）。允许按许可证个人免费使用、学习、修改和非商业性再分发；商业使用需要提前取得版权所有者的单独授权。第三方部分依各自许可证，见 NOTICE、THIRD_PARTY_NOTICES.md、LICENSE_STATUS.md 和 licenses/。源码 ZIP 与运行包在同一 Release 提供；重新构建/替换 LGPL 库见 docs/DEPENDENCIES.md。

`BUILD_MANIFEST.json` 记录版本、依赖和源文件摘要，`SHA256SUMS.txt` 可校验包内文件。修改或替换 DLL 后摘要会改变；运行时不强制校验或限制库替换。
