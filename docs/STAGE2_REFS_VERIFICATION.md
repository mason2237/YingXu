# 第二阶段参考版

日期：2026-10-20。

## 范围和参考

用户提供网站清单并授权尝试。本次在阶段二内调整信息层级和交互，不进入匹配功能或文件执行阶段。

| 参考 | 采用的思路 | Qt 实现 |
| --- | --- | --- |
| [Beautiful UI](https://www.beautifului.dev/) Records Table | 记录层级、状态标签 | 视频/字幕双行、文字加色点状态、整行悬停 |
| [Component Gallery 表格](https://component.gallery/components/table/)及[折叠](https://component.gallery/components/accordion/) | 主信息稳定展示，次要信息按需展开 | 详情优先展示名称、目标与评分，完整路径折叠 |
| [Transitions.dev Panel Reveal](https://transitions.dev/studio.html?lib=panel-reveal) | 短暂展开与减少动态效果 | 160ms OutCubic 高度动画，可反向、可关闭 |

参考的是页面描述的组件模式；代码由项目独立实现，没有复制 React 组件、加载远端资源或上传媒体文件。
Windows 动画偏好通过只读的 `SPI_GETCLIENTAREAANIMATION` 查询，参照 [Microsoft API 文档](https://learn.microsoft.com/en-us/windows/win32/api/winuser/nf-winuser-systemparametersinfow)。

## 改动

- 目录名与完整路径分层，文件列表主文字为 12pt、辅助为 10.5pt。
- 详情标题同行显示状态，保留更多正文空间。
- 新增 `yingxu/qt_ui/interactions.py` 管理整行悬停和路径展开。
- 复制目标名称后显示勾选图标；所有现有操作仍具有真实功能。
- 没有修改 `core.py`、旧版文件执行逻辑或新增运行依赖。

## 验证

在实际 Windows 交互桌面运行 `work/check_preview.py`，退出码 0：

- 10 个视频的真实扫描和三种匹配状态。
- 1240×840、1000×700 窗口；详情收起/展开；列表没有横向滚动。
- 上下键选择、复制名称、选项变更使旧预览失效。
- 空目录、无字幕、无效路径、扫描中关闭窗口。
- 新增：展开中立即反向关闭；禁用动画时立即展开/关闭。
- 临时样本扫描前后内容一致。

人工查看真实窗口截图，确认目录、列表、详情对齐；长文件名在详情换行并可纵向滚动。
截图保存为 `outputs/stage2_refs_initial.png`、`stage2_refs_scanning.png`、`stage2_refs_wide.png`、`stage2_refs_narrow.png`、`stage2_refs_narrow_details.png`、`stage2_refs_empty.png`。
截图中的目录来自自动清理的临时样本。

## 产物

参考版独立输出到 `outputs/stage2-refs/YingXuSubtitleOrganizer.exe`；旧版及原阶段二 EXE 保留。
PyInstaller 构建成功；`work/check_packaged.ps1` 检测到“映序 · 字幕匹配预览”主窗口，并正常关闭，退出码 0。

- 大小：39,415,543 字节。
- SHA256：`81C262E5C6631815E11BCBBA69761921DA9BDAB63C5333EEE6A9BF80E10E693C`。
- 恢复标签：`stage2-reference-preview`。

## 剩余事项

等待用户验收参考版。搜索、排序、人工调整、拖拽和多语言匹配仍属于阶段三。
整理确认、执行与记录仍属于阶段四；多 DPI、跨屏与干净 Windows 环境测试留待后续。
