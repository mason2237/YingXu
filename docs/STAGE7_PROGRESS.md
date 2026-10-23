# 阶段 7 开发检查点

当前状态（2026-10-23）：**阶段 7 已完成定向验收，等待用户确认。** 默认 `run_web.py` 已切换真实工作台；检查证据、截图、限制和阶段 8 入口见 [STAGE7_VERIFICATION.md](STAGE7_VERIFICATION.md)。下文保留 2026-10-22 两次中途保存的历史，不能将其未完成状态当成当前状态。恢复标签 `stage7-complete`。

日期：2026-10-22。基线：`6740ab7` / `stage6-3b-complete`。

用户已授权阶段 7，并要求 token 余量不足时先保存再停止。当前为阶段内恢复点，不是阶段完成声明。

## 后端已完成

- `workspace_protocol.py`：生产动作严格白名单与参数/类型/分页检查，不接收文件路径、目标名或任意命令。原 Foundation 默认白名单保持封闭。
- `workspace_bridge.py`：唯一 request 槽、会话、请求去重、延迟原生请求；仅发布 request/reply/event。页面刷新撤销未执行凭证，已运行任务由 Python 保有。
- `workspace_service.py`：单任务、原生授权目录登记、异步扫描/候选/审阅/冻结/整理/记录/导出；精确绑定 session、scanId、revision、snapshotId 和一次性 token。先消费再启动，复用 snapshot_from_review / run_batch / HistoryStore / export_result。
- `workspace_data.py`：ReviewPlan DTO、ID、搜索排序分页和候选。人工审阅先复制原计划，成功后原子替换，失败不留下部分修改。滚动请求可省略完整 ID 列表。
- `workspace_worker.py`：后台线程、可协作停止、错误分类，进度按真实计数节流，避免大量文件时挤满 UI 事件队列。
- 原 core/review 仅加可选取消/进度/错误回调，默认调用兼容；相似度、语言识别、目标命名和 operations 文件执行算法没有重写。Web 扫描边界跳过符号链接或解析到所选目录外的文件，并记录原因。

## 已验证

- 原 32 项 core/review/operations 检查通过。
- 新 `tests/web/test_workspace.py` 13 项通过：只读预览和旧目标一致、参数约束、Qt 发布面、精确确认/ack、重复与重放、刷新前后、冲突不覆盖、审阅原子性、分页、取消、停止、真实历史与独占导出。
- 第一轮测试目录误用了 Windows 不允许的尖括号，已改为合法中文/空格/&/单引号。正常沙箱的 strict resolve 被系统拒绝；未移除严格路径校验，改为在正常权限下运行项目内临时目录检查，13 项通过。

## 检查点时的剩余任务（2026-10-22，现已完成）

1. 完成下面记录的前端接线；当前原生宿主与适配器只是已保存草稿。
2. 定向实际窗口临时目录全流程及必要边界检查，保存截图/文档；确认真实工作台可用后才把 `run_web.py` 切为 `start(workspace=True)`。
3. 更新设计/接口/进度并创建阶段完成提交。阶段 8 EXE 发布不在本轮范围。

## 第二个检查点：宿主与前端适配草稿（2026-10-22 历史）

为遵守“token 要没了保存并停止”，本轮在接线中途保存。**阶段 7 未完成；真实 Web 工作台尚不能使用。** 默认 `run_web.py` 已恢复为可运行的诊断入口；完整真实工具仍为 `run_preview.py`，现代示例仍为 `run_web_preview.py`。

### 已落盘的草稿

- `window.py` 新增内部 `workspace=True` 模式，注册 bridge + appearance；原生目录选择/单目录拖入、已登记 ID 的复制/打开所在目录、原生导出、安全等待后台任务后关窗。目录对话框和导出为延迟回复，页面变化后不执行旧请求。
- `resources.py` 的 WORKSPACE_ASSETS 拒绝诊断与 preview 模块；默认/示例资源策略保持兼容。
- `channel.js` 供 appearance 与 BridgeClient 共用一个 QWebChannel。BridgeClient 支持取消超时和释放 pending，错误保留 code。
- `local-adapter.js`：后台事件/只读状态轮询、等待 job.idle、任务恢复，不自动重试文件操作；原生对话框不设置固定超时。
- `components/local-workspace.js` + `css/local-workspace.css`：真实目录、扫描选项、停止、候选/历史分页和导出控件的构建/控制器。**尚未由 workspace.js 导入，依赖 store.busy、dialogs.syncExecution 等待补充接口。**
- `scan.configure`：严格布尔选项；改动使旧审阅与预览失效，需重新扫描。整理失败清除过时审阅，开始下一批清除上批结果 ID。

### 当时的续接步骤（2026-10-23 已完成）

1. `workspace.js` 删除静态 PreviewAdapter import；根据宿主不可改写的 `__yingxuWorkspaceMode === 'local'` 动态导入 LocalAdapter / PreviewAdapter。生产模式先 prepareLocalWorkspace，再初始化组件；最后挂 LocalWorkspace。初始 load 为 restore；目录按钮 choose，扫描 scan。生产不暴露 yingxuPreview 调试对象。当前生产资源策略会阻止旧静态 preview import，故**接完之前不可启用真实入口**。
2. `store.js` 补 busy（loading 或 adapter.state.busy）；每次查询都带最新 scanId/revision，refresh includeIds:true，滚动 includeIds:false；人工更改期间 busy，取消对话框保留已有状态，异步详情/列表捕捉错误。不要在 job.completed 但 worker 尚未 idle 时启动下一任务。
3. `dialogs.js` 在真实模式不构造已移除的 dataset 模态框，增加 scan-options 模态框。候选使用后端分页；preview.create 结果仅含元数据/token，内容须 preview.query 分页；记录用 history.list 元数据 + history.get/result.get 分页；错误原因、停止计数、历史保存失败等必须展示。保留示例分支。
4. 最终确认由本地 checkbox + 按钮触发，调用 adapter.start('organize.confirmAndStart', {scanId,reviewRevision,snapshotId,confirmationToken,acknowledged:true})，成功 ack 后关预览以露出停止按钮，再 waitJob；刷新结果并显示真实记录。只准按预览冻结计划执行，不自动重试，示例执行始终禁用。
5. `inspector.js` 复制/打开位置传 fileId，经白名单宿主执行；更新真实进度、空状态、选项恢复和命令标签，移除生产中的“示例”文案。结果后清空旧审阅并提示重新扫描，沿用原 Qt 语义。
6. 定向检查真实临时目录：选目录→扫描→人工确认/候选→预览→明确确认→整理→结果→导出；核对未确认不写文件、不覆盖。用 QFileDialog mock 返回项目 work/test-results 临时目录，HistoryStore/QSettings 同样隔离；尽量 QtTest/DOM 自动化，不重复人工电脑控制。保存实际截图后再切默认入口并提交阶段完成。

### 此恢复点检查

- 14 项后端用例通过（10.36 秒），新增扫描选项变化撤销旧审阅/预览且不修改媒体文件的检查。
- 11 项原通信/资源边界用例通过；5 个修改 JS 文件语法、7 个 Python 文件编译通过。
- `work/check_stage7_checkpoint.py` 定向启动诊断和现代示例窗口：两者就绪、诊断中文消息 Python 往返、示例 12 条数据、示例最终执行仍禁用、外观通道连接，控制台均无错误。仅示例入口注册 appearance，诊断入口注册 bridge。
- 原 32 项业务在本轮后端检查点已通过；没有重复全套视觉/GPU/DPI。此恢复点没有测试尚未接通的真实 Web 整理全流程，也没有发布新版 EXE。
- 正常桌面权限运行 GUI 与严格路径用例，测试媒体/历史/外观设置均在项目临时目录。电脑控制工具调用 0 次。

## 接续要点

- Native `folder.choose` / `result.export` 需延迟回复；WebWindow 通过 service.native_requested 收到（action, params, requestId, sessionId），完成后调用 bridge.finish_native。不要把内部回调直接连接到注册 Bridge 的绑定方法，以免 PySide 动态发布。
- service.native_busy 在原生选择期间置 true；用户取消/页面变化后清理；accept_folder 只允许宿主调用。调用前释放 native_busy，严禁 JSON 路径登记。
- 新桥接 action 与 DTO 以 workspace_protocol/service 为准。预览/候选/记录是分页的；preview.create 返回后台 job，最终 job.result 含确认凭证。前端必须等 job.idle 后刷新或执行下一动作。
- 执行结果沿用旧 Qt 语义：清空过时审阅，保留实际结果，提示重新扫描。结果不是安全撤销或崩溃恢复日志。
- 宿主草稿已接入受控后端，但网页尚未切换适配器/分页协议。当前默认仍为诊断、现代工作台仍为示例，旧 Qt 仍为完整真实工具；不得误称真实 Web UI 已交付。

检查点提交消息：`feat: add guarded workspace backend and cancellable scanning`；标签 `stage7-backend-checkpoint`。

第二检查点提交消息：`wip: save native workspace wiring and continuation checkpoint`；标签 `stage7-ui-checkpoint`。保存后停止，等待用户继续。
