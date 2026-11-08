---
name: video-report
description: Use when 用户希望把调研、总结、概述、文档或知识介绍做成带配音和字幕的视频，尤其需要可编辑的类PPT HTML与MP4，或排查制作环境、时间轴与字幕同步问题。单纯制作PPTX或文字稿时不触发。
---

# Video Report

把材料变成可编辑 HTML、中文旁白、字幕与 MP4。先组织信息，再用脚本测量和导出。**音频实际采样数是时间依据，画面和字幕共用一条时间轴。**

## 使用顺序

1. 从用户材料及当前对话提取受众、目的、语言和时长。默认中文、16:9、1080p30、约3～5分钟；关键偏好缺失才问，不要求用户逐页批准。
2. 阅读 [制作 SOP](references/workflow.md)。有现成调研就复用；新增事实核对原始来源，区分事实、推断与建议。不要捏造接受度排名、百分比或引用。
3. 写分镜和 `report.json`。每页一个信息任务，页面展示证据，旁白解释意义。数据字段及时间规则见 [输入与字幕](references/timing-and-captions.md)；布局见 [画面设计](references/visual-design.md)。
4. 环境未配置时，按 [环境与故障恢复](references/environment-and-troubleshooting.md) 运行 `scripts/bootstrap.py`，再运行 `scripts/doctor.py`。在任务目录建立 venv，复用已安装的工具；不安装全局 Python 包。
5. 用 `video_report.py validate` 检查输入，先构建一个短样片；检查画面、音色、术语和字幕位置后执行完整 `build`。修改内容后重复 `build`，有效配音缓存会复用。
6. 检查联系表和关键场景，运行 `check` 完整解码；抽查开头、中段、结尾及跨页。自动检查不等于人工抽听，不把未做的检查写成通过。
7. 交付视频、HTML、字幕、旁白、分镜、来源与 QA，并按 [成本与交付](references/cost-and-delivery.md) 总结成本。视频用绝对路径展示；发布或上传仅在任务要求时执行。

## 脚本入口

以下命令从仓库根目录执行；安装为个人 skill 时，使用当前 `SKILL.md` 旁 `scripts/` 的实际绝对路径替代仓库内脚本路径。任务目录可以是任意可写工作目录。

```powershell
python skills/video-report/scripts/bootstrap.py --workspace . --portable-tools
.venv/Scripts/python.exe skills/video-report/scripts/doctor.py
.venv/Scripts/python.exe skills/video-report/scripts/video_report.py init report.json
.venv/Scripts/python.exe skills/video-report/scripts/video_report.py validate report.json
.venv/Scripts/python.exe skills/video-report/scripts/video_report.py build report.json --output output/report
.venv/Scripts/python.exe skills/video-report/scripts/video_report.py check output/report
```

`tts` 单独准备配音和时间轴；`render` 复用已匹配的音频输入生成 HTML 和截图。参数以 `--help` 为准。Linux/macOS 使用 `.venv/bin/python`，并配置系统 FFmpeg/ffprobe。

## 决策与限制

- 默认模板适合类PPT研究简报，支持封面、卡片、证据条形图、流程、任务选择及结尾。支持编辑 HTML/CSS；持续动画和任意已有网页自动导入需单独实现适配器。
- 配音默认 edge-tts 7.3.1，在线合成并保留真实边界。它不支持任意自定义 SSML。停顿可分段合成后插入 PCM 静音，或换用明确支持该能力的服务。
- 只有句／段级时间时，保留该精度；不能按字数插值后声称逐词精确。已有录音可通过 `scene.audio` 加相对时间的 `scene.captions` 使用。
- 字幕按完整句子组成一条cue，允许较长文字和第二行；不能按字数或句中停顿把一句话拆到前后两条。每行默认目标36字，优先在句内标点换行。整句超出两行可读范围时，先改稿或调整布局，不能机械截句；配音分段也优先完整句。
- TTS 失败保留有效缓存，修复原因后续跑；三次失败即报错，不能用静音掩盖。缺图、溢出和浏览器错误必须修复后再交付。
- 当前模板导出静态页面状态及硬切。Remotion、Azure、ASR对齐、PPTX导入、背景音乐和批量发布均不是已实现功能。

真实案例及核对过的研究材料在仓库 `examples/format-acceptance/`、`docs/research/`；例子帮助理解输入，不作为未来任务必须套用的结论。
