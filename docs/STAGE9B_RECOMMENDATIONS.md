# 9b：工作台入口与批量候选推荐

日期：2026-10-23。9a 通过后按用户授权继续下一步；本阶段短暂停止后用户要求继续。当前保存 9b，等待确认后进入 9c。

## 已实现

- 工作台“在线字幕”、详情中当前视频入口和 Ctrl+K 操作，默认载入未匹配且未跳过的视频，打开窗口不联网。
- 勾选/跳过、顺序批量查找、停止/续查；后续任务间隔 1.5 秒，不并发抓取、不自动翻页。验证码/失败/结构不明时暂停，可切换来源，旧来源结果保留。
- 中英双语/简体/繁体/英语优先，保存到独立 `YingXu/SubtitleDiscovery` 设置。
- SubHD 搜索结果真实 DOM 读取，每页最多 60 条，限制字段长度，剔除重复及站外详情地址。仅保存公开片名、片源名、语言/格式标注、详情链接，不保存 Cookie/验证码/下载签名。
- 按片名关键词、年份、季集及明确语言标注排序，显示依据、缺项和冲突，不显示虚假概率。双语须同时有明确双语与中英文标注，排序不证明剪辑版本或时间轴一致。
- 人工保留/更换推荐，需核对项目必须勾选后才能保留。下载收据附带扫描/行/版本与候选线索，但 `matchConfirmed` 仍为 false。
- 自写 miuix 风格 Qt 面板、明暗同步、工作台局部字体/圆角/中性色调整，保留既有玻璃。未复制 Compose Miuix 代码或素材，无新增依赖。

## 文件与接口

| 范围 | 文件 |
| --- | --- |
| 有界读取和排序 | `yingxu/subtitle_sources/candidates.py` |
| 队列与候选面板 | `yingxu/web_ui/subtitle_browser.py`、`subtitle_recommendations.py` |
| 版本校验和原生入口 | `window.py`、`workspace_bridge.py`、`workspace_protocol.py`、`workspace_service.py`（均在 `yingxu/web_ui/`） |
| 工作台入口与局部风格 | `frontend/js/components/local-workspace.js`、`inspector.js`、`frontend/js/workspace.js`、`frontend/css/local-workspace.css` |
| 新检查 | `tests/test_subtitle_recommendations.py`、`tests/web/test_discovery.py`、`scripts/check_subtitle_recommendations.py` |

新增 `subtitle.open` 必填 `scanId: string, revision: int`，可选 `rowId: string`。不传行 ID 时取整个扫描的未匹配队列，不受前端搜索筛选限制；响应 `opened, taskCount, added`。视频路径由 Python 解析，不接受任意路径/URL；旧版本、未知 ID、忙状态和重复请求均受控。

远程窗口使用独立 profile，无 QWebChannel；主工作台离线资源/CSP 约束保留。`core.py`、`review.py`、`operations.py` 未改。

## 验证结果

- 新增 7 项候选检查：URL/字段边界、坏数据、显式双语、语言排序、集数/年份冲突、别名提示和脚本编码通过。
- 新增 5 项接口检查：默认队列、任意路径/URL/旧版拒绝、请求去重、忙/无扫描拒绝、原预览与媒体不变通过。
- 14 项原后端检查通过。首次受限环境的 `Path.resolve(strict=True)` 拒绝，在普通 Windows 环境重跑通过，未修改安全校验。
- 11 项既有下载流程通过：隔离启动、搜索、接收/收据、不覆盖、错误内容/超限拒绝、取消、任务及来源切换、验证码、媒体不变。
- 7 组真实 Qt 集成通过：工作台真实扫描/入口且首次不联网、批量停止/续查和跳过、偏好保存/排序/低可信确认/更换、详情下载上下文、验证码暂停/备用恢复、940×700 深色/无 JS 错误、主窗口关闭子浏览器。
- 真实 SubHD 示例 `Interstellar 2014` 当前页读取 20 条候选，双语元数据可用。此前总数 55 条包含其他页；本阶段不自动翻页，真实网站下载 0 份。
- 3 个修改 JS 语法及 7 个 Python 模块编译通过。Qt 检查 Python 异常和工作台 JS 错误均为 0。

受控下载使用临时回环站点和合成字幕，策略替换仅在测试进程中生效。真实站点只进行正常搜索与有界 DOM 读取，没有验证码识别/绕过。修复了 Qt JS 普通对象返回导致的队列误暂停，使用 JSON 字符串解码；截图检查后隐藏推荐页无关导航、详情独立滚动、收起空下载列表并增大字号。

```powershell
.venv-web/Scripts/python.exe -m unittest discover -s tests -p test_subtitle_recommendations.py -v
.venv-web/Scripts/python.exe -m unittest discover -s tests/web -p test_discovery.py -v
.venv-web/Scripts/python.exe -m unittest discover -s tests/web -p test_workspace.py -v
.venv-web/Scripts/python.exe scripts/check_subtitle_browser.py --output work/test-results/stage9b-browser-regression.json
.venv-web/Scripts/python.exe scripts/check_subtitle_recommendations.py
.venv-web/Scripts/python.exe scripts/check_subtitle_recommendations.py --live --site subhd
```

证据保存在被忽略的 `work/test-results/stage9b-*`：fixture、browser-regression、live-subhd 的 JSON；真实站点截图、浅色/深色候选截图及深色工作台截图。真实站点前后两次读取分别用于初验及布局修正后的截图，均为 20 条。没有电脑控制调用，未重复未受影响的业务/DPI/干净系统测试。

## 续接边界

当前不解压、不登记字幕库存、不将文件放入视频目录；保留推荐不自动点击网站下载。真实网站下载认证尚未完整验收。候选和选择只保存在窗口内，语言偏好、已下载文件和收据保留在本机。

9c：安全处理压缩包、限定大小/内容/路径、登记库存并更新审阅版本、失效旧预览、单独规划缓存字幕目的地，再接最终预览/确认/不覆盖/结果记录。不能直接套用旧 `move=False`，否则字幕会留在缓存目录。

9d：增量细修、当前 Windows 完整闭环、新 EXE 和发布准备。当前没有构建或推送；公开库按 `PUBLISHING.md` 的干净历史流程同步，不能推送本地旧开发历史。

提交消息：`feat: connect batch subtitle discovery and language-aware recommendations`。从根 `PROGRESS.md` 和本文续接，不重复 9a/9b。
