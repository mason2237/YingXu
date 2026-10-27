# 从业务原型开始

本教程先用独立原型讲规则，再说明已经接入 0.11 桌面的真实用例。当前源码只使用 Electron + Python，无需 Qt。
先在命令行跑通业务，再接桌面界面；完整结构见 [architecture.txt](../architecture.txt)。

## 运行一个最小系统

原型只使用 Python 3.12 标准库。以下命令中的 `-S` 会跳过第三方包，不需要 Qt、Electron 或网站账号：

```powershell
.venv-core/Scripts/python.exe -S scripts/run_workflow_prototype.py
.venv-core/Scripts/python.exe -S scripts/run_workflow_prototype.py --simulate-download
```

第一条运行到候选选中，停在下载确认前。第二条用模拟事件演示完整状态链，
不会联网、下载、校验真实字幕或修改媒体。`review_ready` 是演示状态，不是文件操作权限。
每次产生独立任务，不清空旧数据库；默认数据库在被 Git 忽略的 `work/test-results/workflow-prototype/`。

复制输出中的 `taskId`，在另一个进程读取同一任务：

```powershell
.venv-core/Scripts/python.exe -S scripts/run_workflow_prototype.py --show-task <taskId>
```

也可用 `--database <路径>` 指定专用演示数据库，不要指向其他软件的数据库。

## 六个可以分别替换的部分

| 部分 | 文件 | 负责什么 |
| --- | --- | --- |
| 数据模型 | `yingxu/domain/models.py` | 不可变任务、命令、阶段、错误；不认识窗口和网站 |
| 用例 | `yingxu/application/subtitles.py` | 决定哪些命令在当前状态可接受 |
| 接口 | `yingxu/ports/` | 约定存储和字幕供应服务应提供什么 |
| 实现 | `yingxu/adapters/sqlite_workflow_store.py` | 把任务与回执保存在 SQLite |
| 桌面边界 | `yingxu/desktop/protocol.py` | 验证有界 v2 JSON 消息，不执行系统命令 |
| 组合入口 | `scripts/run_workflow_prototype.py` | 装配对象，用 FakeSubtitleProvider 演示 |

`SubtitleWorkflow` 接收一个 `WorkflowStore` 接口，不指定 SQLite。
单元测试用内存替身测试规则，存储契约测试用真实临时 SQLite 测试事务；两者目的不同。
示例 provider 在脚本内，真实站点 provider 位于 adapters/subtitle_sites；用例通过 ports 调用，不导入浏览器。

## 选择数据类型

- 阶段用 Enum，避免到处拼字符串；非法阶段会在模型边界被拒绝。
- 快照用 frozen dataclass，减少共享可变状态；`.data` 返回新的 JSON 树。
- ID 是有界字符串，版本是有界整数，确认是严格布尔值，避免 `1` 被当成确认。
- 消息携带 ID 和必要参数，不携带文件字节、整个工作区或随意执行的代码。
- provider DTO 只是外部信息；得到候选不代表下载内容可信。

JSON 是序列化边界。`data_json` 是 R1 有界原型载荷；功能增多后应提取明确的类型与分页查询，
不要把所有未来业务数据都堆进一个字典。

## 理解几种标识

`command_id` 标识一次命令。相同命令重试返回已存回执，不再次推进状态；相同 ID 改内容则报错。
回执保留当时的结果，查询当前状态应调用 `get_task`。

`revision` 是这个任务的状态版本。`expected_revision` 不一致，说明调用者的状态过期。
`review_revision` 是工作区审阅上下文版本；与任务版本分别检查。
旧工作区审阅在宿主接入时仍需用例主动失效任务，R1 没有全局工作区管理器。

`active_effect_id` 标识这一轮搜索、传输或校验。取消/重试后旧回调不能推进新任务。
它不是密码或授权令牌；不可信页面被禁止调用内部完成事件，才是权限边界。

## 做一个局部修改

新增候选字段时，先决定类型和上限，再修改 provider DTO、应用的候选验证及对应契约。
不要先把网页对象原样穿过 IPC。候选大列表后续走分页接口，不放进每个命令回执。

新增规则时，修改应用的状态判断，并加一个能说明行为的 unit 测试。例如，
`confirm_download` 要求严格的 `acknowledged: true`；取消任务后，旧下载回调必须报错。
状态转换要产生新快照，不能在规则中打开文件、请求网站或显示弹窗。

更换存储时，实现 `create/get/apply/close`，其中 `apply` 必须原子完成去重、版本比较、
转换和回执保存。`tests/contract/test_workflow_store.py` 是 SQLite 参考契约；换存储时复用这些场景。
不能把示例内存替身直接当生产存储，它没有实现完整的持久去重与并发控制。

接入真实 provider 时，先声明搜索/下载能力，遇验证码返回人工介入，
再把结果规范化为候选。下载完成、内容验证通过、准备导入分别报告，不能互相替代。
文件系统提交和恢复是独立系统，不应藏进 provider 或 UI 回调。

## 验证与边界

```powershell
.venv-core/Scripts/python.exe -S -m unittest discover -s tests/unit -v
.venv-core/Scripts/python.exe -S -m unittest discover -s tests/contract -v
.venv-core/Scripts/python.exe -S -m unittest discover -s tests/integration -v
.venv-core/Scripts/python.exe -S -m unittest discover -s tests/recovery -v
```

recovery 测试实际强制退出子进程，验证已提交元数据保留、未提交事务回滚、旧回调被拒绝。
其中元数据检查不能代替文件恢复；文件恢复检查另见下文。HTTP 续传由本地服务验证 206/200/416、对象变化和中断等情况，不能保证每个真实网站都支持。真实断电未验证；当前边界见 [验证记录](RELEASE_VALIDATION.md)。
正确性测试保持可重复；计时和负载 benchmark 独立放 benchmarks，不混入通过/失败断言。


## 把原型接成真实工作台

先按 [开发指南](DEVELOPMENT.md) 运行默认 `run.py`。它组装 Electron 与无 Qt 的 Python 宿主；扫描、预览、确认执行、恢复、撤销和下载导入均已接通。

| 系统 | 规则或用例 | 可替换的外部实现 |
| --- | --- | --- |
| 扫描 | `application/scanning.py` | `ports/workspace.py` 的 Filesystem / MediaInspector |
| 匹配与命名 | `domain/matching.py`、`planning.py`、`review.py` | 目标占用检查由调用者提供，规则不导入适配器 |
| 审阅显示 | `application/reviewing.py` | 前端只消费 DTO；单行跳过/确认只更新该行 |
| 预览 | `application/workspace.py` 的预览用例 | `adapters/preview.py` 复用原检查，只冻结不执行 |
| 网站查找 | `application/discovery.py` 的任务编排 | `ports/browser_provider.py` 与 Electron 隔离网页 |
| 历史 | Workspace 读取用例 | `adapters/history_reader.py` 读取原有 JSONL |

试着只改一个接口：给 MediaInspector 写一个返回固定元数据的测试替身，扫描用例无需知道窗口或 DLL。
再换回 LocalMediaInspector，同一份扫描用例即可读取真实容器。内嵌语言符合的判断仍由 domain/media.py 决定，不能由 UI 自己标记通过。

修改新 IPC 时，先改 `desktop/workspace_protocol.py` 的用例参数，再修改客户端并补契约；8 KiB 超限需要分页，不能悄悄截断名称。
R1 任务 codec 与桌面外层都是 v2，但格式不同：前者是独立任务命令示例，后者有 type/requestId/sessionId/action，由宿主路由到用例。不要把两套消息直接混用。

换成其他图形栈时，应复用 Workspace/Discovery 和这些 ports；只替换 desktop/前端适配，不复制匹配和文件操作算法。
网站 DOM 结果始终是外部输入，必须经 provider 校验后才能成为候选；候选仍不等于可信字幕文件。

## 可恢复的文件整理系统

先运行一个只使用生成样本的闭环：

```powershell
.venv-core/Scripts/python.exe -S -m unittest tests.integration.test_file_execution.FileExecutionTests.test_same_volume_preserves_identity_time_hardlinks_and_undo -v
```

它依次生成视频/字幕 → 冻结预览 → 消费确认凭证 → 整理 → 冻结反向预览 → 确认撤销。
真实图形界面由用户勾选确认，测试只在自己创建的临时目录中代替确认，不读取你的媒体目录。
测试是业务原型的可运行例子；不是对任意现有文件直接调用执行器的使用建议。

| 可复用部分 | 入口 | 数据与职责 |
| --- | --- | --- |
| 文件版本 | `domain/operations.py` | `FileVersion` 是不可变值：身份、卷、大小、时间、SHA256 |
| 整理用例 | `application/executing.py` | 固定计划、授权、执行、恢复核对、反向撤销；不认识窗口 |
| 持久日志接口 | `ports/operation_journal.py` | 短事务保存意图/步骤/回执；事务内不能复制文件 |
| 文件接口 | `ports/transaction_files.py` | 打开受保护的文件会话、备份、提交和安全源删除 |
| Windows 实现 | `adapters/windows_files.py`、`transaction_files.py` | 通过实际文件句柄操作，避免检查路径后被替换 |
| SQLite 实现 | `adapters/sqlite_operation_journal.py` | 操作日志、完整性摘要、一次性凭证和数据目录独占 |
| 组合入口 | `desktop/operation_runtime.py` | `build_execution(profile)`；负责实例化和关闭适配器 |

应用层依赖两个接口，因此以后更换展示层或日志实现时，不必再写一套文件算法。
更换文件适配器必须保留“目标不覆盖、身份核对、目标保护到源删除完成”等语义；方法名称相同并不代表实现等价。
源与目标路径在预览时冻结，前端之后只传任务 ID、快照 ID 与严格的布尔确认，不能传新目标路径或系统命令。

把“意图”和“结果”分开思考：改名可能已经成功，但进程还没来得及记结果。
重启时应比较持久化的文件身份与内容，能证明完成就只补日志；有歧义时交还用户核对。
测试在多个 checkpoint 直接结束子进程，覆盖这个窗口，而不是用 UI 的进度数值推测成功。
Windows 句柄、SQLite 事务与文件系统仍没有共同的全局事务；这些测试不等于真实断电保证。

局部修改的顺序：先写清新的允许状态/不变量，再修改用例和 port，最后适配界面。
例如新增一种恢复策略，先说明哪些已知身份允许恢复，再覆盖“确认前文件变化”和“成功动作后强退”场景。
不要把来源不明、内容相同的文件当成本任务目标；也不要在 UI 关闭时自动清除仍用于恢复/撤销的缓存。

## 可恢复的字幕下载系统

运行 `tests.integration.test_subtitle_transfer` 可观察本地 HTTP 的 206、200、416 与对象变化；
运行 `tests.integration.test_subtitle_inbox` 可观察生成字幕包 → 重启 → 审阅 → 整理 → 导出 → 撤销。
这些样本不依赖公共网站，不读取真实媒体。

- `application/subtitles.py` 定义允许的状态转换；下载完成并不代表内容已经通过检查。
- `application/discovery.py` 管搜索与候选，`downloading.py` 编排下载、准备和待审阅导入。
- `ports/browser_provider.py` 与 `subtitle_artifacts.py` 分别描述网站交互和持久暂存能力。
- `adapters/http_transfer.py` 核对 HTTP 对象和区间；`subtitle_artifacts.py` 管落盘与资源清单；安全解压复用 `subtitle_imports.py`。
- 窗口只传任务 ID 和严格确认；外部结果还要匹配 generation/effectId。路径和 Cookie 不放进前端业务状态。

练习修改供应服务时，先声明能自动做什么、哪里必须人工验证，再实现 plan/results/url 适配器。
不要把某个站点的 URL、HTTP 逻辑或窗口对象放进领域模型。增加一种归档格式时，先定义条目、大小、
路径及取消语义，然后实现有界输出流；不要让第三方解压器直接写入视频目录。

状态与资源清单解决不同问题：工作流决定当前允许的操作，缓存收据说明已落盘的字节与字幕归属。
二者都由同一 Python 应用编排；页面重启不能替代用户确认，缓存存在也不等于可以整理媒体。
