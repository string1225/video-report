# 运行环境与恢复

## 安装与来源

最小依赖：Python 3.12+、`requirements.lock` 中锁定的包、Playwright Chromium、FFmpeg和ffprobe、本地中文字体。当前实测环境记录在仓库研究案例的QA，不将版本声明当成每个平台都已实测。

`bootstrap.py --workspace <任务目录>` 在该目录建立 `.venv` 并安装锁文件；Windows用 `.venv/Scripts/python.exe`，Linux/macOS用 `.venv/bin/python`。参数 `--skip-browser` 复用已有浏览器。网络慢时可通过当前进程的 `PIP_INDEX_URL` 选择可访问的PyPI镜像；不需要修改全局pip设置。

Windows `--portable-tools` 复制 imageio-ffmpeg 包内的 FFmpeg，并从 npm registry 固定版本 `@ffprobe-installer/win32-x64@5.1.0` 下载ffprobe，验证包SHA-512，只取执行文件，存到任务目录 `.tools/bin/`；不是系统PATH安装。分发者元数据记录在 `ffprobe-source.json`。二者版本可能不同，必须用实际成片完整解码验证兼容。也可以优先使用已安装的受维护FFmpeg/ffprobe。

Linux/macOS先用系统包管理器安装完整FFmpeg；例如已有brew环境可使用 `brew install ffmpeg`，Debian/Ubuntu可使用系统 `ffmpeg` 包。Playwright浏览器的Linux系统库需要按其官方安装说明补齐。脚本不自动提升权限。

导出模式只需要Chromium headless shell，可用 `python -m playwright install chromium --only-shell`。完整Chromium安装也支持。

下载慢时，可选 `bootstrap.py --workspace . --portable-tools --browser-mirror https://cdn.npmmirror.com/binaries/chrome-for-testing`。该模式按已安装Playwright声明的浏览器版本下载Windows x64 headless shell，检查ZIP CRC、解压路径并记录SHA-256；已有对应浏览器可复用。渲染器会在任务目录或脚本祖先目录的 `.tools/chromium/chrome-headless-shell-win64/` 发现便携浏览器。网络镜像与标准下载源均需按实际环境验证。

工具发现顺序：显式环境变量、PATH、脚本或当前工作目录祖先的 `.tools/ffmpeg/bin` / `.tools/bin`；`VIDEO_REPORT_DEPENDENCIES` 还可指向包含ffmpeg/ffprobe绝对路径的JSON。

- `VIDEO_REPORT_FFMPEG` / `VIDEO_REPORT_FFPROBE`：对应二进制完整路径。
- `VIDEO_REPORT_CHROMIUM`：可选的现有Chromium可执行文件路径。
- 在线配音仅发送本次旁白。edge-tts依赖服务可用性，运行时验证音色；云端密钥不得写入输出HTML与日志。

## 故障 → 动作

| 现象 | 处理 |
| --- | --- |
| Python包没有当前版本轮子 | 新建受支持解释器的venv；不要替换系统Python |
| Playwright找不到浏览器 | 用同一个venv解释器安装对应Chromium；或显式配置已有可执行文件 |
| FFmpeg存在但字幕失败 | doctor确认实际构建含libass；编码从输出目录用相对ASS路径运行，避免Windows盘符转义 |
| 字体方框或图文变化 | 等字体及图片解码，确认实际CJK字体；查看最终帧，修复后重新render/build |
| 页面溢出 | 缩短标题/正文或减少卡片内容；修复画面再导出，不无条件缩小全部文字 |
| TTS第三页失败 | 记录错误，修复网络/音色后重复build；有效场景缓存继续使用，失败最多重试三次 |
| 修改旁白后字幕偏移 | 重做相应配音、重算后续采样与字幕；render命令会拒绝与现有时间轴不匹配的旁白输入 |
| 没有真正逐词时间 | 保留句/段级精度；缩短合成分段，或单独接入对齐工具 |
| 画面/声音总长变化 | 检查累计帧边界和头尾停顿；不要独立拼MP3后沿用旧秒数 |
| 音轨存在但没有声音 | 完整解码加音量检测；不能只检查文件大小或音轨字段 |

缓存按文本、声音、语速、服务版本和schema保存。未完成的合成不写完成标记；改画面不重新请求相同配音。视频片段按截图内容、帧数和编码设置缓存。`manifest.json` 记录每阶段状态；修复后重复 `build`。

FFmpeg实际支持的字幕、编码器和音频滤镜以 `doctor.py` 为准。音量/真峰值规范、音乐混音、商业配音服务、批量渲染应按具体任务另行增加，不在当前脚本中暗示已经实现。

## 可选发布环境

只有上传或发布任务需要 Node.js 18+、Ego Lite、可用的 `ego-browser` 和在 Ego Lite 中登录的创作者账号。内置 `publisher/` 使用 Node 内置模块，不需要 npm install；Python 的 `bootstrap.py` 和 `doctor.py` 只负责制作环境，不安装或验证发布浏览器。现成视频可直接进入发布流程，不必安装配音和渲染依赖。

路径、配置检查及账号 onboarding 见 [发布与成片交接](publishing.md)。Windows 使用内置 `.cmd` 或直接调用 `node publisher/scripts/v2/publisher.mjs`；含中文或空格的路径加引号。生产脚本直接通过 UTF-8 stdin 调用 Ego；中文 Windows 输出按严格 UTF-8 解码，必要时回退 GB18030。不要用 PowerShell 文本管道重写这条输入通道。
