# 阶段 8d：GitHub 公开发布

日期：2026-10-23。用户明确要求上传，确认公开目标 `mason2237/YingXu` 并完成 GitHub 设备授权。此前 8c 仅准备材料的范围由本次授权扩展为实际发布。

## 发布结果

- 仓库：[mason2237/YingXu](https://github.com/mason2237/YingXu)，公开。
- Release：[v0.8.0-rc.2](https://github.com/mason2237/YingXu/releases/tag/v0.8.0-rc.2)，预发布版，非草稿。
- 发布时间：2026-10-23 13:08:10（Asia/Hong_Kong，GitHub 记录为 `2026-10-23T05:08:10Z`）。
- 原创许可：PolyForm Noncommercial License 1.0.0 官方原文；第三方原署名和独立许可保持。

| 发布资产 | 字节数 | SHA256 |
| --- | ---: | --- |
| YingXu-0.8.0-rc.2-windows-x64.zip | 163642594 | `889a141fa8cd0ed08c1d4a10cdef1503ae93098c207efa10a0911fd2b58079d0` |
| YingXu-0.8.0-rc.2-source.zip | 1316564 | `c5ec0e954ed72ab8c9666c49e64cee0c718de044bbc1adf36a07ae56b217fa4b` |
| SHA256SUMS.txt | 197 | `a41065c1f1b9bcb3c9bb99ca468bbfe5d20a14c041cbe90974130174aa242e7a` |

完整解压 Windows ZIP，运行 `YingXu/YingXu.exe` 并保留 `_internal`；不能仅下载/复制单个 EXE。下载、许可与现有验证边界在 Release 说明和 README 均有记录。

## 源码与历史对应

- 本地发布快照：`c3ea9a73eb569fd30eb87b5651fa14b6c4251767`，标签 `stage8c-public-ready`。
- 公开源码初始提交及 Release 标签目标：`71005b2245b3eb5d3ae1c6e50ef947d9db8e6b98`，来自上述干净源码 ZIP 的 372 个文件。
- 原 Git 历史完整留在本地；没有上传旧开发路径历史、测试媒体、虚拟环境、缓存或操作记录。公开初始提交使用账号的 GitHub noreply 邮箱。
- 公开 `main` 后续追加下载链接/发布记录的文档提交；不移动 `v0.8.0-rc.2`，不重新打包或替换本次 ZIP。源码 ZIP 中的 8c“尚未上传”描述保留为当时记录。
- 本地恢复提交消息 `docs: record public GitHub release`，恢复标签 `stage8d-published`。后续维护公开历史应从公开仓库继续，不合并原开发仓库历史。

## 本次核对与边界

- GitHub 确认三个资产均为 uploaded，返回大小和 SHA256 与本地材料一致。
- 无登录凭据访问仓库和版本 Release 成功；公开/预发布/非草稿状态正确，版本标签解析到预期提交。
- 公开版本根 LICENSE 与本地官方原文字节一致，SHA256 为 `ffcca38841adb694b6f380647e15f17c446a4d1656fed51a1e2041d064c94cc8`。
- 结构化结果：[stage8d_github_publication.json](evidence/stage8d_github_publication.json)。既有测试与 EXE 验证见 [8c 记录](STAGE8C_PUBLICATION.md)。
- 本次只发布既有产物并修改文档，应用代码及 ZIP 未变；未重复执行应用测试，未重新下载整个大包，资产核对采用 GitHub 的服务端摘要。
- **未进行干净 Windows 系统测试**。EXE 未签名，无撤销功能；不将本机已有结果表述为所有设备兼容认证。
- 电脑控制工具调用 0 次；凭据由系统 Git Credential Manager 管理，没有把 token 或设备授权码写入仓库/发布记录。

## 发布过程中的中断

首次建仓调用因自动审批系统额度不足未执行；用户要求继续后通过相同审批流程重试成功。没有绕过审批，也没有将中断时的本地材料描述为已上线。

当前发布已完成；新增功能、额外兼容性验证与后续版本均按用户下一次需求实施。
