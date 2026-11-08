# Video Report

把调研、总结或概述制作成可编辑的类PPT HTML、中文配音、同步字幕和MP4；按需把成片或现成视频准备到小红书、抖音、B站、微信视频号和YouTube草稿。包含可安装的 Codex skill、内容与画面 SOP、环境诊断、制作与发布脚本和真实研究案例。

## 快速开始

在仓库根目录用独立环境安装。Windows便携模式把媒体工具放进 `.tools/`：

```powershell
python skills/video-report/scripts/bootstrap.py --workspace . --portable-tools
.venv/Scripts/python.exe skills/video-report/scripts/doctor.py
.venv/Scripts/python.exe skills/video-report/scripts/video_report.py init report.json
.venv/Scripts/python.exe skills/video-report/scripts/video_report.py build report.json --output output/demo
```

标准下载源较慢时，可以只在当前进程选择镜像，并使用可选的Chromium镜像入口：

```powershell
$env:PIP_INDEX_URL = 'https://mirrors.aliyun.com/pypi/simple/'
python skills/video-report/scripts/bootstrap.py --workspace . --portable-tools --browser-mirror https://cdn.npmmirror.com/binaries/chrome-for-testing
```

Chromium版本由锁定的Playwright包确定，便携下载检查ZIP CRC、解压路径并记录SHA-256。已安装工具也可用 `VIDEO_REPORT_FFMPEG`、`VIDEO_REPORT_FFPROBE`、`VIDEO_REPORT_CHROMIUM` 指定。Linux/macOS使用 `.venv/bin/python`，自行安装完整FFmpeg和中文字体；便携下载模式当前面向Windows x64。

## 真实研究案例

[案例输入](examples/format-acceptance/report.json) 比较PPT、文档、介绍视频的接受度、观看参与及学习效果。它区分主观偏好、理解、记忆和实际操作，并保留研究情境与核读范围，不制造三种载体的普遍排名。

```powershell
.venv/Scripts/python.exe skills/video-report/scripts/video_report.py build examples/format-acceptance/report.json --output output/format-acceptance
.venv/Scripts/python.exe skills/video-report/scripts/video_report.py check output/format-acceptance
```

当前精简版：8页，约1分35秒，1920×1080、30fps；口播由1,313字精简至533字。保留原TTS基准语速 `+5%`，再按 `voice.speed: 1.25` 保音高变速；22条整句字幕随音频同步缩放，长句可分两行。文献证据见 [研究核对](docs/research/format-acceptance-evidence.md)，制作与验收记录见 [案例QA](examples/format-acceptance/qa-summary.json)。媒体文件在本地 `output/`，不会随源码提交。

## 安装为个人 skill

skill源码位于 [skills/video-report](skills/video-report/SKILL.md)。可复制到个人技能目录，或在Windows下建立指向本仓库的目录联接；现有同名技能请先检查，不覆盖不相关内容。

```powershell
$skillSource = (Resolve-Path skills/video-report).Path
$skillDestination = Join-Path $env:USERPROFILE '.codex/skills/video-report'
New-Item -ItemType Junction -Path $skillDestination -Target $skillSource
```

之后可用 `$video-report` 请求制作或准备发布草稿。安装后的脚本使用实际skill路径，任务环境和输出目录可放在当前工作目录。发布模块随技能一起安装，无需再装独立的 `video-publisher`。

## 内容与导出

- `validate`：检查结构、场景ID、来源引用。
- `tts`：生成或复用配音，统一为48kHz PCM，按实际样本建立时间轴与SRT/ASS。
- `render`：生成HTML并截图；检查实际文字溢出、字体/图片加载和播放器导航、拖动、播放与暂停。
- `build`：依次执行音频、渲染、编码与检查；有效缓存可恢复复用。
- `check`：完整解码视频，检查编码、尺寸、帧率、实际帧数、音轨、音量和字幕区间。

输出包括 `video.mp4`、`deck/index.html`、字幕、配音、分镜、来源、封面、联系表、统一时间轴、制作记录与QA。HTML可独立编辑预览；再次 `render/build` 会生成并覆盖它。需要反复导出的视频定制应修改skill的assets模板／样式或报告JSON。

字幕以完整句子为单位，`max_caption_chars`默认36，是每行排版目标；不会按字数或句中停顿把句子切成前后两条。允许第二行，仍须在成片中核对可读性和安全区。

完整构建还输出 `costs.json`，报告实测阶段耗时、缓存与新增合成量。当前没有配置收费配音API；模型／订阅、电力等未提供账单的成本保持未知，不能将总成本一概记为零。案例最新成本见 [成本记录](examples/format-acceptance/costs.json)。

当前采用静态页面与硬切。已有录音可配合内联 `scene.captions` 使用；外部SRT需先转换成这些记录。任意自定义SSML、ASR、Remotion、Azure适配器、PPTX导入、持续动画与无人值守自动发布不在已实现功能中。

## 多平台发布草稿

内置 [oil-oil/video-publisher-skill](https://github.com/oil-oil/video-publisher-skill) 的生产模块，固定提交与 MIT 归属见 [上游记录](skills/video-report/publisher/UPSTREAM.md)。支持并行上传、串行填写、草稿身份与封面回执核验、中断恢复及未发布草稿换封面。

```text
使用 $video-report，把现有材料做成中文介绍视频，然后准备到 B 站和小红书草稿，停在最终发布前。
使用 $video-report，把 C:/Videos/demo.mp4 准备到我已配置的平台草稿，不需要重新制作视频。
```

发布另需 Node.js 18+、[Ego Lite](https://lite.ego.app/)、可用的 `ego-browser` 与已登录的目标创作者账号；只制作视频时不需要这些依赖。发布模块不需要 npm install。Python 的渲染浏览器不替代 Ego Lite 的账号和任务空间。

制作 `report.json` 与发布内容包分开保存；已有成片直接复用。默认使用平台封面，定制封面按平台需要准备3:4、4:3或16:9文件，不能把16:9的 `poster.png` 当作所有平台封面。具体交接与命令见 [发布流程](skills/video-report/references/publishing.md)。

默认停在最终发布前并保留草稿页面；`READY` 只表示页面核验完成。只有用户明确要求将本次已确认内容发布到指定平台，才重新核对、解除对应页面守卫并读取发布结果。制作、上传和长期配置不构成最终发布授权。个人配置与任务状态保存在用户目录，不进入仓库。

真实平台的历史验收范围见 [验收记录](skills/video-report/publisher/references/acceptance-history.md)。当前五平台同跑、Windows全平台及最终发布并未全部线上验收；本地自动化测试不能替代这些检查。

## 验证

```powershell
.venv/Scripts/python.exe -m unittest discover -s tests -v
.venv/Scripts/python.exe skills/video-report/scripts/doctor.py
node --test skills/video-report/publisher/scripts/tests/*.test.mjs skills/video-report/publisher/scripts/v2/tests/*.test.mjs
```

已实测Windows、Python3.14.3、edge-tts7.3.1、Playwright1.64.1和FFmpeg9.0.2，涵盖真实媒体编码、播放器交互、文本溢出、字幕重叠、部分失败、静音拒绝与缓存恢复。自动检查与人工／助理视觉检查、抽听记录分开保存，不将未执行的检查写成通过。
