# 发布与成片交接

本技能内置 `oil-oil/video-publisher-skill` 的五平台草稿模块。这里只处理从视频制作到发布的交接；具体平台操作遵循 [发布工作流](../publisher/WORKFLOW.md)，草稿准备和验收只调用维护好的生产入口，不手工拆分平台阶段。最终发布是该工作流中单独授权、复核和操作的分支，没有 `--publish` 参数或 publish phase。

## 选择输入

- **本次生成的视频**：使用本次输出目录里已通过 `check` 的 `video.mp4` 的精确绝对路径。先核对 `qa.json`、制作记录及实际成片；QA 未通过时先修复，不上传旧版本或相似文件。
- **用户提供的现成视频**：直接核对其精确路径和主题，必要时用同目录字幕或预览辅助；不要求本技能专用的时间轴、`report.json` 或制作环境。`video_report.py check` 针对完整制作目录，不能当作任意 MP4 的通用检查入口；发布入口有自己的媒体预检。
- **恢复原上传**：沿用原内容包、`--job-id` 和平台任务空间，仅恢复未完成且未发布的平台。标题、视频或标签变化不能假装是原 Job 恢复；明确另发一条才使用新 Job 和 repost 分支。
- **换封面**：仅限已 READY 且尚未发布的原草稿，使用原 Job 的 `--operation replace-cover`；不得修改视频、标题、正文或标签。修改已发布内容与原稿换源不属于该入口。

继承同一任务已确认的标题、平台、封面意图与自制依据，以及用户对助手制作成片的明确长期授权，不重复询问。发布前按[持续自制授权](../publisher/references/originality-policy.md)读取本机偏好；补图、必要截图引用或后续剪辑仍沿用适用的授权，继续记录素材来源与使用范围。只有没有适用依据的外来现成视频才补问缺项。

## 发布环境

将本技能根目录记为 `SKILL_DIR`，发布模块目录是 `PUBLISHER_DIR = SKILL_DIR/publisher`。以下发布命令在 `PUBLISHER_DIR` 执行；可从任意目录用脚本绝对路径调用。不要把模块的 `scripts/` 与根目录的 Python 制作脚本混淆。

发布需要 Node.js 18+、[Ego Lite](https://lite.ego.app/)、PATH 中可用的 `ego-browser` 命令，以及在 Ego Lite 中登录的目标平台账号。发布 CLI 只使用 Node 内置模块，无需 npm install。不能用视频渲染的 Playwright 浏览器代替 Ego Lite 的任务空间与账号会话。

仅在发布任务中检查依赖，例如 Windows PowerShell：

```powershell
$publisherDir = Join-Path $env:USERPROFILE '.codex/skills/video-report/publisher'
node --version
Get-Command ego-browser
Set-Location $publisherDir
node scripts/config.mjs status
```

缺少 Ego Lite 或命令时，报告具体缺项，保留成片与内容包；不要打开另一浏览器尝试发布，也不要把本地内容包写完当作草稿已就绪。

`onboardingRequired:true` 时按 [首次配置](../publisher/references/configuration.md) 确认用户实际拥有的平台、默认平台、素材目录和原创策略，再运行配置 CLI 和 `validate`。完成前不打开创作者后台。已有配置只读取并复用，不重新 onboard 覆盖它。新增账号使用 `add-platform`。

配置沿用 `~/.config/video-publisher/config.json`，任务状态沿用 `~/.video-publisher/v2-jobs/`；保留与上游的兼容性。不把个人配置、cookie、token、内容包、任务状态或浏览器证据提交到技能仓库。

## 标题、标签与封面

读取 [内容确认](../publisher/references/intake-workflow.md) 与 [内容包字段](../publisher/references/content-package.md)。`report.json` 是制作输入，不是发布内容包，不能直接传给 publisher。

复用同一任务已经确认的标题与关键词；用户没有要求长文案时，描述先用标题或标题加标签。需要建议标题或标签而尚未获得代拟授权时，集中只确认缺项。平台标题超限时提出平台专用缩写，不静默改变统一标题或视频主题。YouTube 的说明、受众和可见性等设置遵守内容包校验，不把研究来源文件的链接列表直接灌入说明。

未要求定制封面时设置 `cover.uploadCustomCover=false`，使用平台默认封面。生成目录的 `poster.png` 是第一张演示页截图，常为 16:9；必须先检查尺寸、内容和授权，不因为文件存在就自动上传。

用户要求“带封面”“做封面并发布”或明确上传已有封面时，继承该意图，按 [封面流程](../publisher/references/cover-workflow.md) 准备精确文件：

| 平台 | 需要的比例 |
| --- | --- |
| 小红书 | 3:4 |
| 抖音 | 3:4、4:3 |
| B 站 | 4:3 首页推荐、16:9 个人空间 |
| 微信视频号 | 3:4、4:3 |
| YouTube | 16:9 |

可以根据已确认风格重新排版导出对应比例的封面，实际查看后再交给发布模块；模块本身不制作封面。不要把 16:9 截图填到 3:4／4:3 路径，也不要擅自裁剪、拉伸、替换用户指定封面。缺少必须文件时补齐或询问缺项，不能静默降级为默认封面。

## 内容包与运行

将 `publish-package.json` 放到任务工作目录或制作输出目录，必须在技能目录之外。以下为仅准备 B 站、使用平台默认封面的内容包；路径、标题和标签应来自本次已确认输入：

```json
{
  "videoPath": "C:/Videos/report/video.mp4",
  "title": "模型评估入门",
  "bilibiliDescription": "模型评估入门",
  "bilibiliTags": ["模型评估", "人工智能"],
  "cover": { "uploadCustomCover": false }
}
```

确认配置和内容包后，按 [发布工作流](../publisher/WORKFLOW.md) 调用生产入口。当前视频已经确认，或符合用户明确授予的助手制作成片长期自制政策时，直接使用 `--confirm-original-rights`，不再向用户重复确认。

```powershell
# 在 PUBLISHER_DIR；任务标识只使用本次任务实际值。
node scripts/v2/publisher.mjs --package 'C:/Videos/report/publish-package.json' --platform bilibili --job-id report-demo --confirm-original-rights --no-cleanup-stale-spaces

# 同一任务的只读复查，保持内容包与 job-id 不变。
node scripts/v2/publisher.mjs --package 'C:/Videos/report/publish-package.json' --platform bilibili --job-id report-demo --inspect-only --no-cleanup-stale-spaces
```

Windows 也可使用 `scripts/run-safe-platforms.cmd`，Linux/macOS 可使用 `bash scripts/run-safe-platforms.sh`，参数一致。实际新任务应使用唯一 Job ID，不复用示例值。多平台可重复传入 `--platform`；部分恢复必须沿用原 Job 并加 `--no-cleanup-stale-spaces`，保护未选平台的待发布页面。本技能默认显式使用该参数，避免影响其他工作。

上传可并行，填写和封面操作由唯一串行 UI 队列控制。最终按钮守卫必须已启用；`READY` 是当前页面证据完整、可以复核的状态，不等于平台已保存草稿或已经公开发布。默认保留任务空间供用户检查。

## 恢复、最终发布与交付

- 普通平台 blocker 只处理对应平台；已经 READY 的平台不重复上传。`INPUT_CHANNEL_BROKEN` 时保留状态，通道恢复后再用原 Job 恢复；`USER_CONTROL` 时停止全部浏览器操作，等用户明确继续。
- 用户明确要求把本次已确认内容发布到指定平台时，按 `publisher/WORKFLOW.md` 的最终发布分支：同 Job 重新 `--inspect-only`，核对账号、视频、标题、封面和可见性，在目标页面解除守卫，点击匹配的最终控件并读取平台发布证据。不得把 `Save`、`Publish`、`Schedule` 混用。没有成功证据就报告“发布结果未确认”，不能重按或另发。
- 制作交付仍保留 MP4、HTML、字幕、旁白、来源、QA 与成本记录；额外记录发布内容包、Job ID、所选平台、逐平台状态、缺项、阻塞和证据路径。
- 区分“本地封面已生成”“平台接受封面”“草稿 READY”“点击最终发布”“平台确认发布”。只检查了部分平台时，只报告这些平台的结论。
- `costs.json` 仍是制作阶段成本。Ego Lite、平台或模型的费用若无账单就保持未知，不能把发布阶段成本计为 0。

内置模块有历史四平台流程和单平台验收，但当前五平台同跑、Windows 全平台、YouTube 崩溃恢复及最终发布并非全部线上验收。来源提交、局部改动见 [上游记录](../publisher/UPSTREAM.md)，真实范围见 [验收历史](../publisher/references/acceptance-history.md)。离线测试通过不代表真实账号和当前页面已可用。
