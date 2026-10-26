# 9a：独立字幕库原型开发记录

日期：2026-10-23。

## 追加验收与备用来源

用户随后明确要求“测试，成功后继续下一步”，并指定 miuix 风格及多个备用网址。原先“不测试”约定已由此更新。

- 10 项离线单元检查通过：搜索词、URL/来源边界、文件名、独占暂存和收据、编码/格式、错误内容和大小限制。
- 11 项真实 Qt 临时站流程通过：启动/无桥接、视频选择/表单提交、真实下载信号、重复文件不覆盖、伪装 HTML/程序拒绝、取消、超限、任务关联、来源切换、验证码页识别及媒体不变。Python 异常为 0。
- 实际 `zimuku.org` 与 `srtku.com`：均显示网站访问验证码，HTTP 状态为 404。已修正原“页面未加载”的误导提示，保持待提交的搜索词；没有自动解答验证码。
- 实际 `subhd.me` 与 `subhd.one`：使用站点真实 `input#sn` / `button#searchbutton` 自动搜索公开片名 `Interstellar 2014`，两条线路都加载结果页，显示 55 条结果。没有猜测搜索 URL。
- 普通 HTTP 库读取 SubHD 结果曾返回 403；没有继续重试该方式。正常 Qt 网页访问成功，后续候选只从实际可访问页面获取。
- 未从真实站点下载字幕，未验证真实下载认证；下载接收链路通过的是受控测试站。以上不等同于全站无验证下载可用。
- 默认仍为字幕库；可切换其官方备用域名和 SubHD 的两条线路，来源/搜索词与原记录分别保留。
- 视觉采用 Miuix / HyperOS 设计原则的原生适配，未复制组件源码，未新增第三方运行依赖。原网站本身的内容与验证页面保留。

来源依据：[字幕库页脚的备用域名公告](https://zimuku.org/detail/221247.html)、[SubHD 官网可用域名列表](https://subhd.me/)、[Miuix 官方说明](https://compose-miuix-ui.github.io/miuix/)。Miuix 是 Compose Multiplatform 库，官方许可为 Apache-2.0；本阶段仅参考设计原则。

可重复命令：`python -m unittest discover -s tests -p test_subtitle_sources.py -v`；`python scripts/check_subtitle_browser.py`；显式联网用 `--live --site zimuku|srtku|subhd|subhd-one`。使用 `.venv-web` 环境。原始 JSON 和截图在被忽略的 `work/test-results/stage9a-*.json/png`，不随公开包携带网页/媒体内容。

以下保留初始开发记录；以本节更新后的验证结果为准。

## 授权与状态

用户确认采用独立内置窗口接入 zimuku.org，随后曾要求额度不足先保存，写进度时自动审批因额度耗尽失败、没有执行该次修改。用户随后要求继续，并明确额度已恢复、直接开发。本次已继续实现原型并保存，**按最新指示未运行测试、没有启动窗口验收**。

这是开发检查点，不能描述为字幕库搜索/下载已通过真实验证。前八阶段的结果和公开 Release 保留。

## 已写入代码

- 独立 Qt 窗口，复用现有 WebEngine 依赖，不引入前端框架或新依赖。
- 一次选择多个本地视频，生成去除分辨率/编码等技术标记的搜索词，保留片名、年份和集数；可编辑、复制、逐项查找。
- 使用真实页面 DOM 识别搜索表单；找到唯一明确表单后自动填写并提交，没有写死未验证的搜索 URL。
- 独立页面、请求范围和权限限制，无 QWebChannel、无本地资源处理器、拒绝网页上传文件请求。
- 真实下载信号接收、进度、取消、数量/大小限额、文件名净化、独立暂存、初步格式识别与收据。
- 每次开始新搜索更换页面；下载事件只接受当前页面，收据保存当时搜索任务；旧页面的加载结果不能覆盖新任务。
- 网络失败、30 秒等待、渲染进程中止、站外跳转、下载中断/错误内容等反馈；提供系统浏览器回退并复制搜索词。

## 运行入口

在项目根目录使用已有 Web 环境：

```powershell
.venv-web/Scripts/python.exe run_subtitle_browser.py
```

启动不会自动搜索；点击“选择视频并查找”或输入片名后点击“查找字幕”才访问网站。暂存位置为应用本地数据目录下 `subtitle-inbox/<会话>/<下载>/`；通过窗口“打开暂存目录”访问。收到文件后显示“待匹配”或“待检查解压”，不修改视频目录。

## 修改文件

- `run_subtitle_browser.py`
- `yingxu/web_ui/subtitle_browser.py`
- `yingxu/subtitle_sources/__init__.py`
- `yingxu/subtitle_sources/zimuku.py`
- `yingxu/subtitle_sources/downloads.py`
- `README.md`、`PROGRESS.md`、`docs/DESIGN_PLAN.md` 与本阶段两份文档

## 验证与遗留

- 本轮：未运行测试、未启动 GUI、未重复网站请求、未做打包。
- 先前已知：本机普通 HTTP 请求为 404；这不证明浏览器一定打不开。表单、验证、弹窗和真实下载兼容性仍待实际确认。
- 尚未接入主工作台入口、默认未匹配选择、语言偏好保存、候选抓取/排序、压缩包处理、字幕导入/自动关联和最终整理。
- 支持一次选择多视频和按项查找；没有将这一点宣称为自动批量推荐完成。
- 下载原型与既有主工作台分离；原业务模块、原 UI、已发布 EXE 未修改。没有上传或推送本次代码。
- 完整后续范围见 `SUBTITLE_DISCOVERY_PLAN.md`。下一阶段从现有原型继续，不重写原业务。

## 保存点

Git 提交消息：`feat: add isolated subtitle website browser and download staging`。精确提交 ID 随阶段汇报提供，可由本消息在本地历史中查到。原本地开发历史不能推送到公开仓库。
