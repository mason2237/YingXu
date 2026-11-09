# 映序 YingXu：字幕能力升级研究与执行报告

> 最新本机接续：YX-03 可解释匹配与 YX-04 只读质检已完成并分别保存；见 [YX-03 验证](evidence/yx03-windows.json)、[YX-04 验证](evidence/yx04-windows.json) 及根目录 PROGRESS.md。以下后续卡及原始研究记录不代表全部升级已完成；尚未打包或发布本轮源码。

> YX-02 本机接续已完成：结构化识别只作核对依据；语言用途变体、正确替换和旧草稿迁移已接入。实测见 [yx02-windows.json](evidence/yx02-windows.json)，可选解析器试验见 [GUESSIT_TRIAL.md](GUESSIT_TRIAL.md)。YX-03/04 仍待实施，后文为原始研究记录。

> 本机接续（2026-11-09）：从用户指定研究聊天恢复报告、12 张任务卡、源码补丁与可用证据。原始交付 ZIP、完整上游日志及 source-map.json 未传入本机，不将聊天中的测试结果冒充本机验证。当前本机结果见 evidence/windows-baseline.json。按用户此前明确要求，取消干净 Windows 测试；本机 Windows、冻结包及必要安全测试继续保留。报告后文为原研究记录，其平台、时间和待办状态不代表本机现状。

核查日期：2026-11-09（Asia/Shanghai）。用途：交给后续 agent 分阶段实施、复现测试和审阅，不作为已完成全部升级或可发布的声明。

建议先完成“结构化识别 → 可解释匹配 → 只读质量检查”，再加入缺失字幕策略、供应服务治理和可选同步。保留现有 Electron + Python 分层、独立使用、最终预览确认和文件事务，不引入 Sonarr/Radarr，不建设完整字幕编辑器，不默认提取所有视频内容。

本轮已实际检查九个仓库的 README、源码结构、核心实现、测试入口、依赖和许可证；执行了映序测试及三个参考项目的重点测试；落地一个标准库实现的多集冲突修复。后续任务、依赖和验收项见 [tasks.json](tasks.json)。源码版本锁定清单见 [source-lock.json](evidence/source-lock.json)，验证汇总见 [validation.json](evidence/validation.json)。

## 1. 映序当前基线

| 项目 | 实际核查结果 |
| --- | --- |
| 默认分支最新提交 | `c7b8056b35d02e335723366e9916512032133a13`，2026-10-27 13:52:22 +08:00；内容为 rc.3 发布记录 |
| 最新发布 | `v0.11.0-rc.3`，预发布，2026-10-27 13:45:16 +08:00；Windows ZIP、源码 ZIP、SHA256SUMS |
| 发布标签指向 | `8ec090ff7b49a5b43c576339f1e53ab41456c33b`，与主分支最后一次文档提交区分 |
| 代码版本 | `desktop/electron/package.json`：`0.11.0-rc.3`；Electron 固定 `45.0.0` |
| 运行依赖 | Python 3.12；`requirements-runtime.txt` 仅 `pymediainfo==7.0.1`；domain 必须只依赖标准库 |
| GitHub CI | Actions runs 返回 0；提交 status 返回 `pending`、空 statuses，表示没有已报告检查，不能解读为正在运行或测试通过 |
| 当前许可证 | 原创部分 PolyForm Noncommercial 1.0.0；第三方权利单独保留 |

GitHub 核查入口：[提交][yx-head]、[发布][yx-release]、[标签对象][yx-tag]、[工作流记录][yx-runs]。本轮没有修改版本号、打包或发布 Windows EXE。

### 1.1 已有架构应保留

实际入口为 `run.py → Electron main.cjs → v2 NDJSON → yingxu.desktop.host`。`frontend/` 管展示，`desktop/` 管窗口与协议，`application/` 管用例与任务，`domain/` 管规则，`ports/` 定义接口，`adapters/` 接文件、SQLite、MediaInfo 和网站。

现有值得保留的能力包括：8 KiB IPC 限额与详情分页、revision/effect ID 防过期回调、任务与回执原子保存、草稿恢复后不恢复旧执行授权、文件意图日志、按文件身份防覆盖、恢复与撤销独立确认、暂存下载与受限解压。同步和新供应服务必须接入这些边界，不建立绕过它们的第二套写文件流程。

当前匹配入口是 `domain/matching.py`、`planning.py`、`review.py`。原实现以 `SequenceMatcher` 得分为主，候选阈值 0.52，自动进入待整理阈值 0.76；识别到相同季集会设置最低分，再增加同目录加分。`planning.build_plan` 按视频输入顺序贪心分配；`ReviewPlan` 随后添加不同语言。当前语言后缀无法完整表达 forced、SDH、commentary 等用途，同语言不能同时关联多种用途。

`adapters/subtitle_downloads.inspect_download` 读取前 64 KiB，识别字幕或压缩格式；`subtitle_imports` 做私有暂存、配额与安全解压。这些是安全与格式候选检查，尚不是逐条字幕质量检查。实测只有 `[Events]` 的空 ASS、结束早于开始的 SRT 都返回 `subtitle_candidate`，不能对用户显示“质量合格”。

### 1.2 本轮测试结果与可证明范围

环境为 Linux、Python 3.12.14、Node 24.22.1。测试使用仓库生成媒体、临时文件与自制字幕，没有访问用户媒体或在线字幕账户。

| 检查 | 结果 | 可证明范围 |
| --- | --- | --- |
| 初始 `python -S -m unittest discover -s tests -v` | 198 项：141 成功、2 failure、32 error、23 skipped | 全量不通过；保留原始日志 |
| 修改前 unit | 37/37 通过 | 平台无关单元基线 |
| 修改后 unit | 44/44 通过 | 含新增 7 个测试方法及多组子场景、架构边界 |
| 修改后 core contract | 15/15 通过 | 原文件名行为、规划、无未确认文件变更 |
| 修改后 subtitle sources contract | 11/11 通过 | 站点候选与搜索边界 |
| 前端 online、visibility、review_details | 3 个脚本均通过 | 前端契约，不是完整 Electron 可见窗口验收 |
| 8100 组单集打分前后对照 | 全部相等 | 这组生成语料未产生评分回归；不是真实准确率测量 |
| SubSyncr 选定测试 | 57 通过 | matcher、language、speech_cache、output、架构边界 |
| GuessIt 选定测试 | 2344 通过，1 条弃用警告 | API 与 YAML 文件名语料 |
| ffsubsync 选定测试 | 36 通过 | alignment、quality_gate、split_aligner、multi_segment；部分采用 mock |
| ffsubsync 真实调用实验 | 2 组各 100 条字幕通过 | 参考字幕路径：2.5 秒偏移及 25/24 漂移；最大起点误差分别 0、1 ms；原文件和正文不变 |

初始 32 个 error 可分为：9 个测试未创建 `work/test-results`；9 个直接触发 `UNSUPPORTED_PLATFORM`；13 个宿主启动等待超时；1 个 MediaInfo 助手未启动。之后已创建测试目录，并在隔离 venv 安装 pymediainfo 重试：内嵌字幕集成测试 19 项中 18 成功、1 error。源码强制寻找 `MediaInfo.dll`，Linux 安装依赖不能替代 Windows DLL。单独启动宿主已得到 `startup.error / UNSUPPORTED_PLATFORM`，不应修改文件安全策略来强行跑通 Linux 宿主。

2 个 failure 位于旧 `test_operations.py`，分别涉及模拟 `os.rename` 权限失败与重命名目标竞争；现有代码/测试依赖 Windows 重命名与路径语义。它们不是本次修改引入，但仍需在 Windows 重现后关闭，不能仅凭平台判断宣称安全。正式事务执行与恢复的 23 个 Windows/原生解压测试被明确跳过。

没有执行：全套上游测试、Bazarr/AutoSubSync 完整应用、两个 .NET 项目的测试、真实影片音频同步、真实在线下载、当前改动的 Windows EXE/干净系统验收。报告中的待验收项不计入通过项。

## 2. 八个参考项目：源码发现与采用决定

下列短 SHA 对应实际检出的默认分支，不保证等于各项目最新稳定发布。完整 SHA 和提交时间已锁定；后续 agent 必须按锁定版本复现，升级依赖时重新验证。

| 项目 | 锁定 SHA / 源码信息 | 主许可 | 采用方向 |
| --- | --- | --- | --- |
| Bazarr | `bfe4593` / master | GPL v3 | 学习评分分解、语言政策、升级历史、限流；独立实现 |
| Subtitle Edit | `d6b1928` / main，当前已是 `src/libse` + Avalonia UI 结构 | MIT | 学习解析与问题定位；不引入 .NET 编辑器运行时 |
| SuperSubber | `3ed8101` / 1.6.8 提交 | MIT | NFO/IMDb、哈希、已有字幕判断；不引入 Tk GUI |
| SubSyncr | `b63c2c6` / pyproject 0.1.0 | MIT | 重点：多份字幕分组、歧义解释、队列、引擎结果与缓存 |
| AutoSubSync | `db7875b` / v6.5 提交，Python 包名 `assy` | GPL-3.0-or-later | 研究手动偏移、CLI、argv 与进程生命周期；独立实现适配器 |
| ffsubsync | `de310ac` / 本轮安装 0.5.1 | MIT | 可选外部同步 worker，先参考字幕后音频 |
| EpisodeMatcher | `86aacb7` / master | MIT | 用户触发的文本辅助匹配；不默认提取、OCR 或改视频名 |
| GuessIt | `3c73072` / develop，4.4.0 | LGPL-3.0-or-later | 可替换的可选解析适配器；domain 不直接导入 |

### 2.1 Bazarr

已读 [README][bz-readme]、[评分实现][bz-score]、[缺失索引][bz-index]、[升级逻辑][bz-upgrade]、[自适应搜索][bz-adaptive]、[调度][bz-scheduler]、[provider 限流][bz-throttle] 与 [评分测试][bz-tests]。

评分按作品身份、季集、年份、片源、发行组、codec/resolution 等拆解。当前 episode hash 权重 359，movie hash 179；可验证哈希仍检查若干关联字段，不能把一个散列匹配当作无条件真值。IMDb、TVDB 等身份信号会映射为对应的作品特征；返回总分与不含 hash 的分数。映序应保存“证据”和“冲突”，而非只存一个浮点数，也不应直接沿用 Bazarr 分值。

缺失字幕由语言 profile 与已有字幕清单比较，包含 forced、HI、音轨条件和 cutoff；升级要求更高分、仍满足语言需求、历史路径和现存字幕对应，调用最低分为原分 +1，并记录升级来源。映序应更保守：人工提供或修改过的字幕默认锁定，升级先成为候选，独立确认后再提交，不能以“下载较新”替代质量比较。

调度设置 `max_instances=1`、coalesce 和 misfire 边界；长期无结果会降低搜索频率；供应商按异常分类停用一段时间。映序可学习限流和错误分类，但现有“启动不自动联网、恢复需确认”应保留；后台无人值守策略属于未来显式启用的能力。

依赖不仅是根目录的 lxml、numpy、webrtcvad-wheels、Pillow、pywin32，还包括大量 `libs/`、`custom_libs/` 内置组件、Web 服务与 Sonarr/Radarr 集成。没有整体移植价值。许可证见 [LICENSE][bz-license]，依赖入口见 [requirements][bz-deps]。未运行 Bazarr 全应用或供应商网络测试。

### 2.2 Subtitle Edit

已读 [README][se-readme]、[SubRip][se-srt]、[ASS][se-ass]、[SSA][se-ssa]、[WebVTT][se-vtt]、[重叠检查][se-overlap]、[编码检测][se-encoding]、[相关测试][se-tests]。当前结构为 `src/libse` 解析/模型/规则、`src/ui` 界面、`src/seconv` 转换入口，以及分组测试。不能按旧 WinForms 项目印象设计集成。

解析器返回 cue/paragraph、时间、文本和错误信息；SRT 有容错解析，ASS/SSA 依据 Events 的 Format 字段读取，保留样式、注释、带逗号正文；VTT 处理多种时间形式和附加内容。重叠规则区分字幕格式，错误定位关联具体段落。映序应先建立只读 `Cue + QualityIssue`，保留行号与原文本，再检查负时长、零时长、乱序、疑似乱码、空正文和可配置阅读速度。ASS 的分层对白、特效及双语同时出现可能是合法重叠，不能一律报错或自动修复。

编码工具使用 UTF.Unknown；用户仍可手动指定编码。对映序，BOM 与严格解码优先，无法确定时展示候选编码和短预览，不能静默用 replacement 字符重写原文件。

OCR 通过 [IOcrSubtitle 的具体实现][se-ocr] 隔离图像/时间信息；[波形渲染][se-wave]使用独立的渲染数据与缓存；[点同步][se-sync]将同步点作用于复制后的字幕数据。借鉴“解析、诊断、视图、变换分开”的边界即可。完整 OCR、波形编辑、多点编辑器本轮均不引入。

主项目和 libse 均 MIT，但依赖另核：[libse 项目][se-deps]包含 SkiaSharp、UTF.Unknown，UI 还有 Avalonia、播放器及云服务依赖。测试使用 .NET 10/xUnit；本轮只阅读，未执行 .NET 测试。

### 2.3 SuperSubber

已读 [README][ss-readme]、[core.py][ss-core]、[requirements][ss-deps]、[第三方声明][ss-third]、[LICENSE][ss-license]。结构主要是 `core.py` 工作流水线、Tkinter `app.py`、配置与日志；未在该快照找到自动化测试目录或测试文件，测试成熟度不能按功能列表推断。

识别优先完整文件名，缺信息时才使用路径，避免父目录中另一部电影的标题污染结果。NFO 查找有范围：电影先同名 NFO，单影片目录才考虑其他 NFO；剧集使用当前或父目录的 `tvshow.nfo`，区别剧集 ID 与系列 ID；NFO 读取有 512000 字节限制。映序应保存 ID 的类型、来源和冲突，不把一次命中扩散到整个混合目录。

哈希通过 subliminal `refine(..., refiners=('hash',))`，不是另一个文本相似度。该算法通常取文件大小、开头/结尾各 64 KiB 的 64 位小端字求和并按 64 位取模；不足 128 KiB 不产生有效哈希。独立实现必须有标准向量、大小边界、取消及读取中变化测试，结果只作版本证据，不替代完整文件身份或 SHA256。

已有字幕检查区分语言标签、文本语言检测、内嵌轨道、forced、SDH 和 unsynced；forced/未知轨道不当作完整语言字幕。当前还用 cue 密度辅助识别不完整下载，阈值不能直接套在寡对白、短片和歌曲上。同步失败与可疑大幅移位单独处理，保留原始下载是有价值的恢复设计。

依赖固定 `subliminal==2.7.1`，因为修改其 provider 内部行为；不要复制这种内部 monkey patch，映序适配器应只依赖公开契约。其 alass/FFmpeg 二进制另受 GPL 等许可，MIT 外壳不改变这些义务。

### 2.4 SubSyncr：重点研究结果

已读 [README][sy-readme]、[matcher][sy-matcher]、[language][sy-language]、[queue][sy-queue]、[worker][sy-worker]、[缓存][sy-cache]、[输出事务][sy-output]、[测试][sy-tests] 与 [依赖][sy-deps]。

匹配分三层：唯一季集或播出日期 → 标准化名称完全一致 → RapidFuzz。它将仅语言/用途不同的字幕分成组，一个视频关联一组，因此 en、es、en.forced 不会抢占同一视频。模糊阶段以 WRatio、token sort、token set 的最大值打分，全局按得分贪心分配，并在第一、第二候选差距小于 5/100 时增加核对原因。这是启发式分数，不是概率；贪心也不是全局最优分配。

**不能直接照搬的实测问题：** `Alpha.S01E01.mkv` 与唯一的 `Zebra.S01E01.en.srt` 被标为 identifier、100 分，仅因季集唯一。模糊阶段的候选差距主要检查视频这一侧，尚不能完整表达“同一字幕同样适合两个视频”。因此映序设计必须增加作品身份门槛、季集集合冲突、视频侧与字幕侧双向差距；相同片源的多语言应先分组，再计算竞争，避免语言变体造成虚假歧义。

队列以一个参考视频及共享选项的一组字幕为单位运行 worker，复用音频提取。失败和低质量可以进入后备引擎，取消任务不会继续回退。取消一项可能取消其所在运行组的剩余任务，映序必须明确显示受影响范围，不能承诺逐条完全独立取消。恢复的待办与历史保存在 store，CLI/Qt 共用无 GUI 的 core，并用导入边界测试约束。

worker 用进程隔离库的日志、内存和取消问题，通过 NDJSON 回报；stdout 专属协议通道。输出写临时文件，只有可信成功才发布，备份失败则阻止覆盖。ffsubsync 的低质量分支会把原字幕写到输出，即便输出存在也不能宣布“同步成功”。

跨会话 speech cache 使用参考路径、size、mtime 与提取选项，暂存只接受本实例发放路径，并检查 npz 完整性。映序应进一步纳入文件身份、可靠内容验证、轨道与引擎/VAD 版本，防止同大小同时间替换文件复用旧缓存；npz 禁止 pickle、限制展开大小。缓存失败应退化为重算，不影响已完成结果。

语言 canonical 目前不比较 region/script，这对映序的简繁中文要求不足；变体模型必须保留 script，不能仅按 zh 合并。当前依赖包含 PySide6、RapidFuzz、pysubs2、平台目录与同步库；还固定了临时 ffsubsync fork 的发布 tarball。本轮 57 项重点测试通过，但没有证明整个同步队列与所有引擎在 Windows 可用。MIT 许可允许按条件复用，仍需保留署名；本轮只借鉴设计，没有复制该实现。

### 2.5 AutoSubSync

已读 [README][as-readme]、[sync_core][as-core]、[手动偏移][as-shift]、[CLI][as-cli]、[进程工具][as-utils]、[测试][as-tests]、[依赖][as-deps]、[LICENSE][as-license]。

`sync_core.run_sync` 提供不直接依赖 Qt 事件循环的编排、回调与结果模型，CLI 和 GUI 复用。命令使用 argv 模板构建；不同引擎声明格式与参考字幕能力，格式转换、备份、进程输出和结果统一接入。`assy-cli sync/shift/batch --json` 是可参考的机器接口。这里的 AutoSubSync GUI 项目（包名 assy）与 `oseiskar/autosubsync` 引擎不是同一个项目。

手动偏移遍历时间戳并另存，适合作为映序同步 MVP；但 ASS/VTT 需要保留样式、注释、cue 设置等，不能一律转成 SRT。能力不支持时回退不等于所有失败都应换引擎：取消、权限错误、磁盘满、非法输出应终止；仅明确可重试或质量不达标的结果才允许进入用户配置的下一引擎。

进程工具包含 Windows CTRL_BREAK/terminate/kill 与 Unix 进程组处理。映序应使用自己的有界 argv 适配器和 Windows Job Object 管理整棵同步子进程树，不全局 monkey patch `subprocess.Popen`，不影响主业务宿主。设置总时限、stdout/stderr 限额并回收孙进程。

依赖包含 PyQt6、rich、psutil、ffsubsync、autosubsync、static-ffmpeg、onnxruntime 等；直接引入包会增加体积和 GUI/许可耦合。GPL-3.0-or-later 源码不拷入映序 PolyForm 核心；只学习接口、测试场景和失败语义。本轮没有运行此应用的全套测试。

### 2.6 ffsubsync

已读 [README][ff-readme]、[FFT aligner][ff-align]、[分段算法][ff-split]、[同步与质量门控][ff-core]、[语音变换][ff-speech]、[测试][ff-tests]、[依赖][ff-deps]、[LICENSE][ff-license]。

音频经 VAD 变为语音活动序列，字幕经出现区间变为同频序列，默认 100 Hz。FFT 互相关搜索整体时间偏移；遍历常见帧率比或 golden-section search 寻找时间尺度，复杂度与样本数相关。参考字幕可直接产生时间序列，不必解码整段视频。

这里要区分两种“分段”：`--multi-segment-sync` 是在长音频上采样多个窗口以降低读取量，仍做整体偏移/比例搜索；`--split-penalty` 是允许不同时段使用不同偏移的动态规划，目标包含对齐收益与分段惩罚，处理删减、广告断点等。它们不能互相替代。只取影片开头也不能证明尾部漂移已经解决。

当前质量门控检查原始得分、偏移绝对值和帧率偏离；阈值依赖内容长度与样本，不能转成跨片比较的准确概率。成功至少需要 `retval==0`、`sync_was_successful`、输出存在且重新解析/质量检查通过。低质量输出必须留在私有暂存并标为未采用。

本轮除了 36 项选定测试，还真正调用 ffsubsync 对生成的参考 SRT 和偏移/漂移 SRT 同步，证据见 [sync-probe.json](evidence/sync-probe.json)。没有证明音频 VAD、寡对白影片、不同剪辑、多语言字幕密度差、PGS 或任何实际影片已达到同样误差。

MIT 引擎可作为可选 worker，但其 numpy、VAD、检测编码库及 FFmpeg 构建仍需逐项清单。先支持参考字幕与手动偏移，再选择一种音频 VAD；不在默认包引入 torch、Whisper、模型自动下载或远程 URL。

### 2.7 EpisodeMatcher

已读 [README][em-readme]、[Matcher][em-core]、[提取器][em-extract]、[测试][em-tests]、[项目依赖][em-deps]、[LICENSE][em-license]。

将内嵌字幕规范化后与已正确命名的参考字幕比较，实际公式是 `0.85 × Bigram Cosine + 0.15 × Jaro-Winkler`，返回前三候选与歧义状态。代码的默认接受阈值为 0.20，歧义差距为 0.03；README 表格仍写 0.05，应以源码为准。`Cosine(2)` 是字符 bigram/shingle，不应把注释中的 word tokens 直接解释成词级 embedding。

默认提取开头 30 秒，文字字幕优先，位图字幕再走 OCR。共同片头、回顾、歌曲、短文本以及不同语言会产生强干扰，因此映序只在用户选中疑难条目后，允许选择已有文本轨和可信参考字幕；先限定同语言，抽取开头/中部/尾部有限窗口，扣除共同文本或降低其权重，展示片段与前两候选。内容证据用于补充文件名，不直接重命名视频、不默认 OCR。

core 面向 .NET 8、依赖 F23.StringSimilarity 7.0.1；测试项目面向 .NET 10/xUnit，并引用 GUI。MIT 主许可不代表 FFmpeg/Tesseract 等外部工具许可已自动满足。本轮未执行 .NET 测试。

### 2.8 GuessIt

已读 [README][gi-readme]、[季集规则][gi-episodes]、[片源规则][gi-source]、[API 测试][gi-tests]、[YAML 语料][gi-yaml]、[依赖][gi-deps]、[LICENSE][gi-license]。

通过 Rebulk 规则、匹配位置、冲突处理与后处理解析 title、year、season、episode、release_group、source、edition、分辨率等。episode 可以是列表，不能截成第一个；标题中的数字、年份、1080p、x265 和集数需要冲突消解。当前规则也含中文季集数字处理，不能用少量正则声称替代完整 GuessIt。

映序应定义自己的不可变 `ParsedRelease` 数据契约，在 adapter 内调用 GuessIt 4.4.0，保留未知值、字段来源和解析器版本。逐个映射为标准库类型，禁止把库私有对象或 MatchesDict 传到 domain。缺库/解析失败退回现有保守规则并标注缺失证据，不让扫描或草稿恢复崩溃。

运行依赖是 Rebulk、babelfish、python-dateutil，须锁定兼容版本和许可证。LGPL 动态/可替换集成可评估，但不能删掉许可义务；Windows 冻结包需提供库源码、改动说明、替换方法及所需许可材料，分发前审查。只把它运行在子进程中也不是自动免责。本轮没有给映序新增 GuessIt 运行依赖。

## 3. 本轮实际改进

任务 `YX-01` 已实现，尚未做 Windows 发布验收。

| 原问题 | 修改后的行为 |
| --- | --- |
| `S01E01E02` 与单集 `S01E01` 得分约 0.9096 | 比较完整已识别集数集合，冲突得分 0 |
| `S01E01-E03` 被当作第一集 | 有界展开范围，识别为 1/2/3 集 |
| `S01E01E03` 与 `S01E01E02` 得分约 0.9631 | 集合不同，得分 0 |
| 全角 `Ｓ０１Ｅ０１` 与 `S01E02` 得分 0.94 | NFKC 规范化后判断集数冲突 |
| 候选解释只看第一集 | 显示完整范围，冲突候选不标为“优先核对”；在线结果使用同一冲突规则 |

新增 `EpisodeIdentity` 与共享冲突函数，支持已有单集形式、显式 `S01E01E02`、`S01E01-E03`、`S01E01-03`、重复 S/E 标记及对应 x 形式。倒序、过大范围与跨季混合标记保守返回不确定；自动打分为 0，人工仍可指定并确认。不会把 `-1080p`、`-x265`、`-2024` 当作连续集范围。

这不是完整结构化片源系统：裸数字、复杂动画编号、日期集、跨季合辑、所有中文范围写法仍需要 `YX-02`。没有改变原最终执行确认、文件写入、SQLite schema、依赖或安全解压。

代码入口：`yingxu/domain/matching.py`、`yingxu/application/reviewing.py`、`yingxu/adapters/subtitle_sites/candidates.py`；回归测试 `tests/unit/test_episode_coverage.py`。新增测试含临时文件的审阅/人工确认闭环，并验证视频与字幕字节不变。对照脚本见 [reproduce_matching.py](reproduce_matching.py)。

四个前后对照故障样例及新增测试覆盖了本次修复，不能据此声称全库匹配准确率提高某个百分比。8100 组普通单集测试是评分兼容性检查；单次耗时仅存档于证据文件，不构成性能提升结论。

## 4. 目标模型与决策边界

### 4.1 将五种证据分开

后续模型建议如下，字段名为拟议契约，尚未全部实现：

| 模型 | 关键字段 | 用途 |
| --- | --- | --- |
| ParsedRelease | title、year、season、episodes[]、source、edition、group、parser_version、evidence[] | 作品与片源身份；未知值保留 null |
| SubtitleVariant | language、script、forced、sdh、commentary、origin | 一视频多语言/用途；不只按语言去重 |
| MatchAssessment | identity_score、release_score、hard_conflicts[]、reasons[]、runner_up_margin、reverse_margin、policy_version | 匹配解释和歧义；分数不等于概率 |
| QualityReport | parse_status、encoding、cue_count、issues[]、content_hash、checker_version、truncated | 字幕结构/时间/文本；不替代匹配 |
| SyncResult | verdict、engine_version、offset、scale、quality_before/after、artifact_id、attempts[] | 同步结果，不代表已授权写入媒体目录 |

先排除可信身份、年份、季集集合等硬冲突，再计算片源软证据与文本相似度；edition 不一致阻止自动采纳。缺失证据不是匹配证据。名称相近但冲突明确的候选不能被语言偏好、同目录或下载量加分抬回自动通过。

为一个视频比较同用途候选的第一/第二差距，同时比较该字幕在不同视频间的差距；多语言同版字幕先成组。保留未匹配选择，不为了“全部分配”强配。人工确认优先，但文件或证据版本变化后应重新预览，不能恢复旧确认令牌。

初始实验阈值可设归一化分数 0.85、双向差距 0.08，**仅供 shadow 模式测量**；它们不是本轮得出的最佳值。实际阈值须由按作品划分的标注集校准，再分语言/内容类型验证。展示名称用“匹配分”和具体原因，不写“准确率 85%”。

### 4.2 只读字幕质量检查

新增端口读取有界字节，纯 parser 生成 cue，纯 checker 生成问题；首版只做诊断和定位，不重排、不修复、不改编码。保持单字幕 8 MiB 限额；建议最多 50000 cues、500 条可展示问题，超限明确标注未完成检查，采用现有分页而非静默截断。

严重问题：不可解析、时间字段非法、结束早于开始、完全无有效 cue、不可可靠解码。提示问题：零时长、乱序、可疑字符、异常阅读速度、重复文本、超视频时长。ASS 多层重叠与双语并行应按用途/层级降为信息提示；统计阈值可配置。所有问题关联源行、cue ID、起止时间和简短正文；正文按纯文本显示。

下载安全识别、字幕质量、版本匹配、时间同步四个状态分开显示。一个有效 SRT 可能属于另一部电影；一个时间轴整齐的字幕仍可能整体晚 10 秒；一个无法自动判断编码的文件应保留检查机会。

### 4.3 缺失、升级、重试

按 `(视频, language/script, purpose)` 计算用户所需与已有可用字幕之差。forced、commentary 和未知语言不默认满足完整对白需求；同语言 SDH 是否满足普通字幕由显式政策决定。外部未改名字幕、内嵌文本和位图轨分开记录能力。用户能看到“为什么还缺”。

升级要满足同作品、同用途、质量非退化、片源更合适、内容确有变化且政策版本一致；人工锁定字幕不自动升级。保留旧版本和来源历史，输出先进入暂存审阅。用文件内容与身份核对防止覆盖用户后续修改。

provider 端口声明 search/download/hash/ID/browser/manual 等能力，回报事实与类型化错误。暂时网络错误采用有上限退避与抖动，尊重 Retry-After；验证码/登录转 awaiting_user，权限/格式/安全失败停止。重启保持暂停；恢复网络任务需现有的新确认。可取消计算 worker，但不能强杀正在提交媒体文件的事务线程。

### 4.4 独立同步模块

第一阶段只接手动毫秒偏移和参考字幕；第二阶段在可选 worker 中接本地音频。默认仅支持本地受登记的文件 ID，不开放任意命令、远程 URL、任意输出路径。引擎产物必须在私有暂存、重新解析、检查文本/样式保真，再导入现有审阅和事务流程。

失败、低质量、取消、成功分开；取消不能触发后备引擎。不同引擎能力和许可证分别登记。初始并发为 1，可根据 HDD/SSD、内存和实测提升至 2；不直接使用“CPU 核数一半”作为 Windows 媒体库默认值。

音频分析按参考视频身份、轨道、引擎/VAD 版本、采样参数复用。跨会话复用需要内容可靠性策略：仅 size/mtime 不够；若强内容核对成本不可接受，就关闭跨会话复用，只复用同次受保护分析结果。缓存有独立预算和活跃引用保护，损坏即重算，不占用可恢复/可撤销文件。

## 5. Agent 实施顺序与完成门槛

机器可读的完整工作卡见 [tasks.json](tasks.json)。每卡包含基线、依赖、文件入口、操作步骤、测试命令、验收和回退。以下是推荐顺序，不是全部已经实施的功能：

| 阶段 | 任务 | 完成后可交付 |
| --- | --- | --- |
| 基线 | YX-00 测试环境/Windows CI；YX-01 本轮修复 | 可重现问题与小范围修复；先解决平台验证 |
| 匹配与检查 | YX-02 结构化信息/变体；YX-03 双向歧义；YX-04 轻量质检 | 用户看懂为什么配、为什么不配、字幕有什么问题 |
| 查找可靠性 | YX-05 缺失与升级；YX-06 NFO/ID/hash；YX-07 provider/重试 | 独立运行的缺失语言查找、可靠来源与任务恢复 |
| 同步 | YX-08 手动/参考字幕；YX-09 音频、缓存与引擎回退 | 可选同步模块与可信失败回退 |
| 内容辅助 | YX-10 用户触发文本匹配 | 文件名不可信时的辅助候选与片段解释 |
| 发布 | YX-11 分阶段 Windows 验收 | 当阶段功能通过后再构建候选包；不要求等全部远期功能完成 |

### 5.1 执行前必须读取

执行 agent 先读仓库现行 `AGENTS.md`（若后来新增）、`architecture.txt`、`docs/DEVELOPMENT.md`、`todo.txt`，再读本报告和任务卡。拉取远端、记录实际 HEAD；若已偏离本报告基线，检查对应文件差异并重跑基线，不覆盖用户改动，不盲用旧补丁。

每项任务在独立分支交付一个可审阅的改动；新任务从 `pending` 改为 `in_progress`，完成后填写实际命令、计数、环境、artifact 路径和局限。预期输出与实际输出必须分开。遇到风险先关闭新能力开关或退回原保守行为，不放宽既有文件保护、协议限制或确认机制。

### 5.2 准确率与性能实验

建立有来源授权的标注集：按作品分训练/验证/保留测试集，覆盖中英文别名、简繁、双语、forced/SDH、不同剪辑、近似片名、重拍年份、合辑、多集、SP、日期集、动画绝对集号、错误后缀和损坏字幕。上游 fixture 可提供思路，复制 fixture 同样核对许可；真实字幕语料需确认使用权。

同时报告：自动建议 precision、覆盖率、人工审阅率、错误接受数量、未匹配率和置信区间。目标可定为保留集自动建议 precision ≥99.5%，但样本不足不得达标宣告。硬冲突对抗集必须零自动接受，人工覆盖路径须保留；不得通过把全部候选降为需确认来宣称准确率提升。至少 1000 个自动建议并附置信区间才评估自动化表现，比较旧基线的覆盖率。

对 100/1000/5000 项扫描记录总耗时、p50/p95、峰值内存、实际读取字节、取消响应时间。分别统计冷/热缓存与 HDD/SSD；开发机耗时、业务 benchmark、浏览器 rAF 都不能证明稳定 120fps。

同步样本至少包含固定偏移、23.976/25 与 24/25 漂移、剪辑断点、寡对白/静音、错片源、稀疏 forced、错轨、同大小同 mtime 文件替换、取消时产生孙进程和损坏缓存。对于可信人工标注锚点报告误差分布；低质量拒绝比“强行产出文件”优先。

### 5.3 Windows 发布门槛

在干净 Windows 11 x64、Python 3.12、固定依赖下运行全部单元/契约/集成/恢复测试；创建测试输出目录；补足失败项与 skip 原因。跑源码和冻结后台，并通过三个真实桌面脚本、生成媒体审阅/确认/整理/重启/恢复/撤销闭环。验证中文长路径、文件锁、大小写冲突、目标竞争、跨卷、草稿失效、下载取消及旧 effect 回调。

新同步组件必须额外证明进程树回收、磁盘满/拒写/超时保留原文件、备份与撤销可用；检查最终包无 Qt、依赖许可与源码材料齐全、可选工具 SHA256 可验证。未完成这些门槛，只交付源码候选和测试证据，不称为可发布 Windows 更新。版本号和发布内容由最终实际完成范围决定，不预先承诺 v0.12 的完整功能。

## 6. 许可证与依赖落地规则

本轮修改是独立标准库实现，没有将第三方库加入映序运行包。研究报告引用源码链接并不意味着已经取得任意形式的合并或分发许可。

MIT 项目可评估复用，但复制实质代码或 fixtures 应附原版权声明与许可；第三方二进制另列。Bazarr/AutoSubSync GPL 源码不直接合入现有 PolyForm 核心；如未来整体集成，应单独决定许可兼容方案。GuessIt 采用可替换库边界，提供所需源码、变更、替换/重链接说明与许可。FFmpeg 许可取决于具体构建选项，不能笼统写“FFmpeg 都是 LGPL”；alass、lapse 及模型在选定实际版本后再独立审查，未知许可不进入发行包。进程隔离是架构边界，不是免除许可义务的结论。

新增依赖前更新 `docs/DEPENDENCIES.md`、`THIRD_PARTY_NOTICES.md`、`release_payload.py` 对应清单，衡量安装体积、启动成本、离线能力、可替换性和 Windows 冻结支持；报告中尚未选定的引擎不应提前加入 requirements。

## 7. 复现入口

以下命令均从仓库根目录执行。Linux 命令验证平台无关部分；Windows 在已配置的 `.venv-core/Scripts/python.exe` 下执行对应命令。

```sh
python -S -m unittest discover -s tests/unit -v
python -S -m unittest discover -s tests/contract -p test_core.py -v
python -S -m unittest discover -s tests/contract -p test_subtitle_sources.py -v
node tests/frontend/online.cjs
node tests/frontend/visibility.cjs
node tests/frontend/review_details.cjs
python -S docs/research/subtitle-upgrade-2026-11/reproduce_matching.py
```

`reproduce_matching.py` 从锁定 Git 提交读取旧算法，对照当前实现；若浅克隆没有该提交，先 fetch 该基线。生成字幕同步实验另见 [reproduce_sync.py](reproduce_sync.py)，需隔离的研究环境，不安装进应用 runtime。

```sh
# 将八个仓库检出到 source-lock.json 的 SHA 后，在独立 venv 安装测试依赖。
# 在 SubSyncr 根目录：
PYTHONPATH=src:tests python -m pytest -q tests/core/test_matcher.py tests/core/test_language.py tests/core/test_speech_cache.py tests/core/test_output.py tests/test_boundary.py
# 在 GuessIt 根目录：
python -m pytest -q -o addopts='' guessit/test/test_api.py guessit/test/test_yml.py
# 在 ffsubsync 根目录：
python -m pytest -q tests/test_alignment.py tests/test_quality_gate.py tests/test_split_aligner.py tests/test_multi_segment.py
# 回到映序根目录，使用上述隔离 venv 的 python：
python docs/research/subtitle-upgrade-2026-11/reproduce_sync.py
```

本轮研究环境的实际包版本见 [research-requirements.txt](evidence/research-requirements.txt)。该清单不是映序发布依赖文件。Windows 的 `PYTHONPATH` 设置用 PowerShell `$env:PYTHONPATH='src;tests'`，不要直接照用 POSIX 分隔符。

## 8. 源码证据索引

以下链接均指向锁定提交；README、许可证、依赖、实现、测试分别引用，避免仅依据项目简介。未执行的上游测试已在第 1 节注明。更多文件入口保存在任务卡内。

| 项目 | README | 依赖 | 许可 | 测试入口 |
| --- | --- | --- | --- | --- |
| Bazarr | [README][bz-readme] | [依赖][bz-deps] | [LICENSE][bz-license] | [测试][bz-tests] |
| Subtitle Edit | [README][se-readme] | [依赖][se-deps] | [LICENSE][se-license] | [测试][se-tests] |
| SuperSubber | [README][ss-readme] | [依赖][ss-deps] | [LICENSE][ss-license] | 该快照未找到自动化测试文件 |
| SubSyncr | [README][sy-readme] | [依赖][sy-deps] | [LICENSE][sy-license] | [测试][sy-tests] |
| AutoSubSync | [README][as-readme] | [依赖][as-deps] | [LICENSE][as-license] | [测试][as-tests] |
| ffsubsync | [README][ff-readme] | [依赖][ff-deps] | [LICENSE][ff-license] | [测试][ff-tests] |
| EpisodeMatcher | [README][em-readme] | [依赖][em-deps] | [LICENSE][em-license] | [测试][em-tests] |
| GuessIt | [README][gi-readme] | [依赖][gi-deps] | [LICENSE][gi-license] | [测试][gi-tests] |

[bz-score]: https://github.com/morpheus65535/bazarr/blob/bfe4593b04caa16eb4a09c2a233777b0bd7723b6/custom_libs/subliminal_patch/score.py
[bz-index]: https://github.com/morpheus65535/bazarr/blob/bfe4593b04caa16eb4a09c2a233777b0bd7723b6/bazarr/subtitles/indexer/series.py
[bz-upgrade]: https://github.com/morpheus65535/bazarr/blob/bfe4593b04caa16eb4a09c2a233777b0bd7723b6/bazarr/subtitles/upgrade.py
[bz-adaptive]: https://github.com/morpheus65535/bazarr/blob/bfe4593b04caa16eb4a09c2a233777b0bd7723b6/bazarr/subtitles/adaptive_searching.py
[bz-scheduler]: https://github.com/morpheus65535/bazarr/blob/bfe4593b04caa16eb4a09c2a233777b0bd7723b6/bazarr/app/scheduler.py
[bz-throttle]: https://github.com/morpheus65535/bazarr/blob/bfe4593b04caa16eb4a09c2a233777b0bd7723b6/bazarr/app/get_providers.py
[bz-tests]: https://github.com/morpheus65535/bazarr/blob/bfe4593b04caa16eb4a09c2a233777b0bd7723b6/tests/subliminal_patch/test_score.py
[bz-deps]: https://github.com/morpheus65535/bazarr/blob/bfe4593b04caa16eb4a09c2a233777b0bd7723b6/requirements.txt
[se-srt]: https://github.com/SubtitleEdit/subtitleedit/blob/d6b1928eaad1fdc5d712b9dad9b0dd85aa86ded6/src/libse/SubtitleFormats/SubRip.cs
[se-ass]: https://github.com/SubtitleEdit/subtitleedit/blob/d6b1928eaad1fdc5d712b9dad9b0dd85aa86ded6/src/libse/SubtitleFormats/AdvancedSubStationAlpha.cs
[se-ssa]: https://github.com/SubtitleEdit/subtitleedit/blob/d6b1928eaad1fdc5d712b9dad9b0dd85aa86ded6/src/libse/SubtitleFormats/SubStationAlpha.cs
[se-vtt]: https://github.com/SubtitleEdit/subtitleedit/blob/d6b1928eaad1fdc5d712b9dad9b0dd85aa86ded6/src/libse/SubtitleFormats/WebVTT.cs
[se-overlap]: https://github.com/SubtitleEdit/subtitleedit/blob/d6b1928eaad1fdc5d712b9dad9b0dd85aa86ded6/src/libse/Forms/FixCommonErrors/FixOverlappingDisplayTimes.cs
[se-encoding]: https://github.com/SubtitleEdit/subtitleedit/blob/d6b1928eaad1fdc5d712b9dad9b0dd85aa86ded6/src/libse/DetectEncoding/EncodingTools.cs
[se-tests]: https://github.com/SubtitleEdit/subtitleedit/blob/d6b1928eaad1fdc5d712b9dad9b0dd85aa86ded6/tests/libse/Forms/FixCommonErrors/FixOverlappingDisplayTimesTest.cs
[se-ocr]: https://github.com/SubtitleEdit/subtitleedit/blob/d6b1928eaad1fdc5d712b9dad9b0dd85aa86ded6/src/ui/Features/Ocr/OcrSubtitle/OcrSubtitleMkvBluRay.cs
[se-wave]: https://github.com/SubtitleEdit/subtitleedit/blob/d6b1928eaad1fdc5d712b9dad9b0dd85aa86ded6/src/ui/Controls/AudioVisualizerControl/SkiaWaveformRenderer.cs
[se-sync]: https://github.com/SubtitleEdit/subtitleedit/blob/d6b1928eaad1fdc5d712b9dad9b0dd85aa86ded6/src/ui/Features/Sync/PointSyncViaOther/PointSyncer.cs
[se-deps]: https://github.com/SubtitleEdit/subtitleedit/blob/d6b1928eaad1fdc5d712b9dad9b0dd85aa86ded6/src/libse/LibSE.csproj
[ss-core]: https://github.com/Cosmopolyte/supersubber/blob/3ed81011b20840bff3e2148c0017934453c6d250/supersubber/core.py
[ss-deps]: https://github.com/Cosmopolyte/supersubber/blob/3ed81011b20840bff3e2148c0017934453c6d250/requirements.txt
[ss-third]: https://github.com/Cosmopolyte/supersubber/blob/3ed81011b20840bff3e2148c0017934453c6d250/THIRD-PARTY.md
[sy-matcher]: https://github.com/jessielw/SubSyncr/blob/b63c2c6ca21880b896d3c8edfa3e1b39dced9e17/src/subsyncr/core/matcher.py
[sy-language]: https://github.com/jessielw/SubSyncr/blob/b63c2c6ca21880b896d3c8edfa3e1b39dced9e17/src/subsyncr/core/language.py
[sy-queue]: https://github.com/jessielw/SubSyncr/blob/b63c2c6ca21880b896d3c8edfa3e1b39dced9e17/src/subsyncr/core/queue.py
[sy-worker]: https://github.com/jessielw/SubSyncr/blob/b63c2c6ca21880b896d3c8edfa3e1b39dced9e17/src/subsyncr/core/worker.py
[sy-cache]: https://github.com/jessielw/SubSyncr/blob/b63c2c6ca21880b896d3c8edfa3e1b39dced9e17/src/subsyncr/core/speech_cache.py
[sy-output]: https://github.com/jessielw/SubSyncr/blob/b63c2c6ca21880b896d3c8edfa3e1b39dced9e17/src/subsyncr/core/output.py
[sy-tests]: https://github.com/jessielw/SubSyncr/blob/b63c2c6ca21880b896d3c8edfa3e1b39dced9e17/tests/core/test_matcher.py
[sy-deps]: https://github.com/jessielw/SubSyncr/blob/b63c2c6ca21880b896d3c8edfa3e1b39dced9e17/pyproject.toml
[as-core]: https://github.com/denizsafak/AutoSubSync/blob/db7875b8ab89832c0223ca4253f050ecb724860f/main/sync_core.py
[as-shift]: https://github.com/denizsafak/AutoSubSync/blob/db7875b8ab89832c0223ca4253f050ecb724860f/main/sync_manual.py
[as-cli]: https://github.com/denizsafak/AutoSubSync/blob/db7875b8ab89832c0223ca4253f050ecb724860f/main/cli.py
[as-utils]: https://github.com/denizsafak/AutoSubSync/blob/db7875b8ab89832c0223ca4253f050ecb724860f/main/utils.py
[as-tests]: https://github.com/denizsafak/AutoSubSync/blob/db7875b8ab89832c0223ca4253f050ecb724860f/tests/test_ffsubsync_features.py
[as-deps]: https://github.com/denizsafak/AutoSubSync/blob/db7875b8ab89832c0223ca4253f050ecb724860f/pyproject.toml
[ff-align]: https://github.com/smacke/ffsubsync/blob/de310ac6944b8260431a48ee741e7063cec49b0f/ffsubsync/aligners.py
[ff-split]: https://github.com/smacke/ffsubsync/blob/de310ac6944b8260431a48ee741e7063cec49b0f/ffsubsync/split_aligner.py
[ff-core]: https://github.com/smacke/ffsubsync/blob/de310ac6944b8260431a48ee741e7063cec49b0f/ffsubsync/ffsubsync.py
[ff-speech]: https://github.com/smacke/ffsubsync/blob/de310ac6944b8260431a48ee741e7063cec49b0f/ffsubsync/speech_transformers.py
[ff-tests]: https://github.com/smacke/ffsubsync/blob/de310ac6944b8260431a48ee741e7063cec49b0f/tests/test_quality_gate.py
[ff-deps]: https://github.com/smacke/ffsubsync/blob/de310ac6944b8260431a48ee741e7063cec49b0f/requirements.txt
[em-core]: https://github.com/BoxOfSnoo/EpisodeMatcher/blob/86aacb714c134af09b46eae12f68eadfa458b3f9/source/EpisodeMatcherCore/Matcher.cs
[em-extract]: https://github.com/BoxOfSnoo/EpisodeMatcher/blob/86aacb714c134af09b46eae12f68eadfa458b3f9/source/EpisodeMatcherCore/SubtitleExtractor.cs
[em-tests]: https://github.com/BoxOfSnoo/EpisodeMatcher/blob/86aacb714c134af09b46eae12f68eadfa458b3f9/source/EpisodeMatcherTests/MatcherTests.cs
[em-deps]: https://github.com/BoxOfSnoo/EpisodeMatcher/blob/86aacb714c134af09b46eae12f68eadfa458b3f9/source/EpisodeMatcherCore/EpisodeMatcherCore.csproj
[gi-episodes]: https://github.com/guessit-io/guessit/blob/3c73072b8971d412935c6f749be63c564dd41385/guessit/rules/properties/episodes.py
[gi-source]: https://github.com/guessit-io/guessit/blob/3c73072b8971d412935c6f749be63c564dd41385/guessit/rules/properties/source.py
[gi-tests]: https://github.com/guessit-io/guessit/blob/3c73072b8971d412935c6f749be63c564dd41385/guessit/test/test_api.py
[gi-yaml]: https://github.com/guessit-io/guessit/blob/3c73072b8971d412935c6f749be63c564dd41385/guessit/test/rules/episodes.yml
[gi-deps]: https://github.com/guessit-io/guessit/blob/3c73072b8971d412935c6f749be63c564dd41385/pyproject.toml
[bz-readme]: https://github.com/morpheus65535/bazarr/blob/bfe4593b04caa16eb4a09c2a233777b0bd7723b6/README.md
[bz-license]: https://github.com/morpheus65535/bazarr/blob/bfe4593b04caa16eb4a09c2a233777b0bd7723b6/LICENSE
[se-readme]: https://github.com/SubtitleEdit/subtitleedit/blob/d6b1928eaad1fdc5d712b9dad9b0dd85aa86ded6/README.md
[se-license]: https://github.com/SubtitleEdit/subtitleedit/blob/d6b1928eaad1fdc5d712b9dad9b0dd85aa86ded6/LICENSE
[ss-readme]: https://github.com/Cosmopolyte/supersubber/blob/3ed81011b20840bff3e2148c0017934453c6d250/README.md
[ss-license]: https://github.com/Cosmopolyte/supersubber/blob/3ed81011b20840bff3e2148c0017934453c6d250/LICENSE
[sy-readme]: https://github.com/jessielw/SubSyncr/blob/b63c2c6ca21880b896d3c8edfa3e1b39dced9e17/README.md
[sy-license]: https://github.com/jessielw/SubSyncr/blob/b63c2c6ca21880b896d3c8edfa3e1b39dced9e17/LICENSE
[as-readme]: https://github.com/denizsafak/AutoSubSync/blob/db7875b8ab89832c0223ca4253f050ecb724860f/README.md
[as-license]: https://github.com/denizsafak/AutoSubSync/blob/db7875b8ab89832c0223ca4253f050ecb724860f/LICENSE
[ff-readme]: https://github.com/smacke/ffsubsync/blob/de310ac6944b8260431a48ee741e7063cec49b0f/README.md
[ff-license]: https://github.com/smacke/ffsubsync/blob/de310ac6944b8260431a48ee741e7063cec49b0f/LICENSE
[em-readme]: https://github.com/BoxOfSnoo/EpisodeMatcher/blob/86aacb714c134af09b46eae12f68eadfa458b3f9/README.md
[em-license]: https://github.com/BoxOfSnoo/EpisodeMatcher/blob/86aacb714c134af09b46eae12f68eadfa458b3f9/LICENSE
[gi-readme]: https://github.com/guessit-io/guessit/blob/3c73072b8971d412935c6f749be63c564dd41385/README.md
[gi-license]: https://github.com/guessit-io/guessit/blob/3c73072b8971d412935c6f749be63c564dd41385/LICENSE
[yx-head]: https://github.com/mason2237/YingXu/commit/c7b8056b35d02e335723366e9916512032133a13
[yx-release]: https://github.com/mason2237/YingXu/releases/tag/v0.11.0-rc.3
[yx-tag]: https://api.github.com/repos/mason2237/YingXu/git/ref/tags/v0.11.0-rc.3
[yx-runs]: https://api.github.com/repos/mason2237/YingXu/actions/runs?per_page=5
