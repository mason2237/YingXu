# 9e：真实网站下载实测与 blob 兼容

日期：2026-10-24。用户澄清需要测试真实网上字幕下载，并明确要求执行。本轮使用真实 Qt 应用、正常网站页面和临时视频；没有模拟网络响应。

## 实测结果

| 步骤 | 结果 |
| --- | --- |
| 首选字幕库 `zimuku.org` | 访问验证码页（HTTP 404），程序正确提示；没有破解/作答 |
| SubHD 搜索 `Interstellar 2014` | 正常填写/提交，读取当前页 20 条候选 |
| 候选详情 | 实际地址 `https://subhd.me/a/Cm0tsS`，网页标注双语 ASS |
| 正常页面下载 | 两次普通下载按钮点击：详情 → 下载准备页 → 文件 |
| 真实文件 | ASS，251,040 字节，SHA256 `bb03ec628c9b34917af2eea828481634014a762ed567f74a5bb52ec555bbe9f6` |
| 自动接收、暂存和原生登记 | 通过；不是下载网页/错误内容 |
| 导入与视频关联 | 1 份导入、1 个匹配“需确认”，保留实际文件名与目标名 |
| 确认前媒体安全 | 视频不变，没有把字幕放入视频目录；没有执行整理 |
| 远程隔离与异常 | 无 QWebChannel，Python/工作台 JS 错误为空 |

实测使用源码启动的真实应用及生产浏览器/导入模块，测试只配置临时目录、样本视频和独立设置。下载使用网站真实响应和 Qt 原生下载信号；没有调用未公开 API、替换响应、改变证书/网络策略或输入账号/Cookie/Token。

机器可读的公开摘要在 [evidence/stage9e_live_download.json](evidence/stage9e_live_download.json)。完整诊断、网页截图、原始下载和副本留在忽略的 `work/test-results/stage9e-*`，不随源码/EXE 分发。

## 找到并修复的问题

rc.1 接收器只允许公网 HTTPS URL。SubHD 将下载内容在网页中生成为 `blob:` 文件，实际请求的页面、任务和文件类型均正确，仍被误拒绝为“此下载不属于当前网站搜索”。诊断只记录协议、页面主机/路径、文件名及关联布尔值，不记录签名、Cookie 或隐藏表单值。

`yingxu/subtitle_sources/downloads.py` 增加 `same_origin_blob`，接收器将它作为 HTTPS 下载之外的窄范围入口：

- 当前页面必须是已登记字幕来源的 HTTPS 页面。
- blob 内来源必须与当前页面的协议、域名、有效端口完全一致，路径必须为 UUID，不允许 query/fragment。
- 不接受 data、null origin、其他来源、其他端口或本地地址。
- 原有请求页面身份、活动搜索任务、后缀/MIME、64 MiB/会话限额、内容初检、独占暂存仍执行。

没有修改 `core.py`、`review.py`、`operations.py` 或主工作台桥接白名单。没有增加新依赖。新版本为 0.9.0-rc.2 / Windows 0.9.0.2，rc.1 保留。

## 自动化边界

**本轮证明“真实下载后自动接收和导入关联”可行，尚未实现完全无人值守下载。** 实际页面的两个下载按钮由定向测试操作；产品目前仍让用户在网页完成这些点击，遇到验证码/登录由用户操作。

临时视频名为 1080p，而所选字幕页面标注 2160p。这里验证的是文件流和待确认关联，不是片源/时间轴匹配保证；导入后 `manual=true`、`confirmed=false`，没有强行确认。网页双语标注没有被冒充成软件对实际字幕语言的确定识别。

## 验证与工具

- 11 项网站/下载检查通过，包括新增同源 blob 正例及 data/null/其他域/端口/畸形 URL 拒绝。
- 11 项既有真实 Qt 受控下载回归通过，涵盖普通 HTTPS 接收、重复不覆盖、错误内容/后缀/超限拒绝、取消、切换任务与媒体不变。
- 本文的真实 SubHD 下载与导入关联通过；字幕库主站停于访问验证。没有把失败的首选来源记成成功。
- 新增 `scripts/check_live_subtitle_download.py`，启动实际应用、搜索并等待操作者依据真实控件逐步下达测试动作。只在忽略的测试目录读写命令文件，15 分钟停止；远程网页没有该入口。探针不是生产后门，也不进入 EXE。
- 一次诊断实例初始化停滞，仅重启该测试实例后正常。探针在等待操作者时不再输出误导性超时堆栈。旧源程序测试中的初始化记录保留，未宣称所有环境稳定性认证。

```powershell
.venv-web/Scripts/python.exe -m unittest discover -s tests -p test_subtitle_sources.py -v
.venv-web/Scripts/python.exe scripts/check_subtitle_browser.py --output work/test-results/stage9e-browser-regression.json
.venv-web/Scripts/python.exe scripts/check_live_subtitle_download.py --site subhd
```

## 交付与续接

本轮已构建 0.9.0-rc.2。新 EXE 实际启动、通信、本地资源、42/42 玻璃按钮和弹窗检查通过，JS/console error 为空；实际网站下载验证使用上文真实源码 Qt 应用，不冒称新 EXE 已重复实站下载。当前 400 个可公开文件检查通过；无新增依赖，沿用已有许可资料与构建校验。发布文件位于 `outputs/github-release/0.9.0-rc.2/`；不自动上传 GitHub。

后续如要减少网页点击，可在已核实的正常下载流程上设计“确认后下载”入口；遇到验证仍需用户操作。不要将“保留推荐”或下载完成当成已确认匹配，不泛化放开任意 blob/data URL，也不把下载内容加入公开资产。

恢复提交消息：`fix: accept trusted same-origin subtitle blobs after live download validation`。
