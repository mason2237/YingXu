# GitHub 公开发布步骤

## 已确定的范围

- 不进行干净 Windows 系统测试，也不将其作为本轮阻塞条件；README/Release 必须写明未验证。
- 保留以前的业务测试、真实窗口验证记录和原 Git 提交，不重写历史。
- 发布采用 PolyForm Noncommercial 1.0.0 的官方完整原文，仅限制原创部分；第三方许可证、署名和库替换权利独立保留。
- 8c 只准备文件和本机发布包；随后用户明确要求上传并确认 `mason2237/YingXu`，8d 已完成公开发布。历史阶段的“未上传”记录指当时状态。
- 以前阶段的试包保留作恢复用途，不作为本次公开资产；旧默认打包可能包含本轮已剔除的额外 Qt 模块。

## 当前发布结果

- 公开源码：[mason2237/YingXu](https://github.com/mason2237/YingXu)。
- 预发布版：[v0.8.0-rc.2](https://github.com/mason2237/YingXu/releases/tag/v0.8.0-rc.2)，含 Windows x64 ZIP、对应源码 ZIP 和 SHA256SUMS。
- 资产上传后核对 GitHub SHA256，并以匿名请求验证公开可见、标签提交与 LICENSE；详见 [发布记录](STAGE8D_GITHUB_RELEASE.md)。
- 发布采用独立干净历史，原开发仓库未配置公开远程。后续从公开仓库 `main` 维护或同步选定源文件；不要推送原开发仓库的旧分支/标签。发布标签保持对应应用源码提交，后续文档提交不改已发布 ZIP。

## 公开内容与历史

运行 `python scripts/audit_public.py --history` 检查当前可发布文件和可达历史对象。报告只输出位置和类别，不输出疑似密钥值；报告本身放在被忽略的 `work/test-results/`。

本轮未发现所检查格式的 API 密钥/私钥。旧提交仍包含开发机路径，不能通过新的清理提交从 Git 历史消除。原 Git 记录保留在本地；若不希望公开旧路径，应使用本轮生成的 **干净源码 ZIP** 建立新的公开仓库，不要将旧 `.git` 目录一同上传。源码 ZIP 不包含 `.git`、虚拟环境、缓存、日志、测试媒体和发布二进制。

若选择直接推送现有 Git 历史，旧开发路径仍会可见。密钥模式检查不能保证发现所有任意格式敏感信息；实际提交个人配置、媒体或服务凭据前仍应检查差异。不要把 `.env`、证书、真实操作记录或临时目录加入版本控制。

## 生成发布材料

```powershell
.venv-web/Scripts/python.exe scripts/build_web.py --release --zip
# 先保存代码/文档并创建本阶段提交，再从该提交导出源码：
.venv-web/Scripts/python.exe scripts/prepare_github_release.py
```

输出 `outputs/github-release/<版本>/`：

- `YingXu-<版本>-windows-x64.zip`：完整 EXE 运行目录，含运行时资源与许可文件。
- `YingXu-<版本>-source.zip`：本阶段 Git 提交的干净源文件，不含 Git 数据库或旧提交。
- `SHA256SUMS.txt`：两个 ZIP 的 SHA256。
- `RELEASE_NOTES.md`：可粘贴到 GitHub Releases 的说明。
- `RELEASE_MANIFEST.json`：版本、源码提交和文件摘要，供发布前核对。

发布目录不纳入 Git，避免重复提交大体积二进制。GitHub 的自动源码快照也不包含 Qt/Python 运行环境，使用者应按 README 安装依赖。

## 后续版本在 GitHub 操作

1. 本次已从干净源码包建立独立公开仓库；后续继续该仓库历史，避免将原开发历史带入。新发布目标和发布动作由维护者确定。
2. 上传/推送源码，确认根目录 LICENSE、NOTICE、README、THIRD_PARTY_NOTICES 和 licenses/ 都存在。
3. 新建对应版本的预发布 Release，使用本轮说明，上传两个 ZIP 和 SHA256SUMS。保持源码版本与 EXE 对应，不将 rc 标成已做全环境认证的稳定版。
4. 在二进制下载说明旁保留许可证和对应第三方源码/构建链接。未完成实际版本源码提供要求时，不公开该二进制。

## 验证记录

32 项业务、14 项后端、11 项边界、真实临时目录整理闭环以及 100/125/150/200% Qt 缩放模拟见原阶段 8b 记录。本轮不重复执行这些未受影响的流程；收窄 Qt 打包范围后只补当前 Windows 下最终 EXE 的启动/通信/界面检查。干净 Windows 测试未执行，不作已通过陈述。
