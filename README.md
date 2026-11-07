# Video Report

把调研、总结或概述制作成可编辑的类PPT HTML、中文配音、同步字幕和MP4。包含可安装的 Codex skill、内容与画面 SOP、环境诊断、制作脚本和真实研究案例。

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

实测成片：11页，约4分41秒，1920×1080、30fps，中文神经配音，82条使用真实词边界的字幕。文献证据见 [研究核对](docs/research/format-acceptance-evidence.md)，制作与验收记录见 [案例QA](examples/format-acceptance/qa-summary.json)。媒体文件在本地 `output/`，不会随源码提交。

## 安装为个人 skill

skill源码位于 [skills/video-report](skills/video-report/SKILL.md)。可复制到个人技能目录，或在Windows下建立指向本仓库的目录联接；现有同名技能请先检查，不覆盖不相关内容。

```powershell
$skillSource = (Resolve-Path skills/video-report).Path
$skillDestination = Join-Path $env:USERPROFILE '.codex/skills/video-report'
New-Item -ItemType Junction -Path $skillDestination -Target $skillSource
```

之后可用 `$video-report` 请求制作。安装后的脚本使用实际skill路径，任务环境和输出目录可放在当前工作目录。

## 内容与导出

- `validate`：检查结构、场景ID、来源引用。
- `tts`：生成或复用配音，统一为48kHz PCM，按实际样本建立时间轴与SRT/ASS。
- `render`：生成HTML并截图；检查实际文字溢出、字体/图片加载和播放器导航、拖动、播放与暂停。
- `build`：依次执行音频、渲染、编码与检查；有效缓存可恢复复用。
- `check`：完整解码视频，检查编码、尺寸、帧率、实际帧数、音轨、音量和字幕区间。

输出包括 `video.mp4`、`deck/index.html`、字幕、配音、分镜、来源、封面、联系表、统一时间轴、制作记录与QA。HTML可独立编辑预览；再次 `render/build` 会生成并覆盖它。需要反复导出的视频定制应修改skill的assets模板／样式或报告JSON。

当前采用静态页面与硬切。已有录音可配合内联 `scene.captions` 使用；外部SRT需先转换成这些记录。任意自定义SSML、ASR、Remotion、Azure适配器、PPTX导入、持续动画与自动发布不在已实现功能中。

## 验证

```powershell
.venv/Scripts/python.exe -m unittest discover -s tests -v
.venv/Scripts/python.exe skills/video-report/scripts/doctor.py
```

已实测Windows、Python3.14.3、edge-tts7.3.1、Playwright1.64.1和FFmpeg9.0.2，涵盖真实媒体编码、播放器交互、文本溢出、字幕重叠、部分失败、静音拒绝与缓存恢复。自动检查与人工／助理视觉检查、抽听记录分开保存，不将未执行的检查写成通过。
