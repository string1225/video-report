# 输入与时间轴

## 最小输入

```json
{
  "title": "研究简报",
  "width": 1920,
  "height": 1080,
  "fps": 30,
  "voice": {"name": "zh-CN-XiaoxiaoNeural", "rate": "+0%"},
  "sources": [{"id": "S1", "title": "原始研究标题", "url": "https://example.org/study"}],
  "scenes": [{
    "id": "intro", "kind": "cards", "title": "先给出可验证的结论",
    "subtitle": "写清适用情境。", "narration": "这是用来演示输入结构的旁白。",
    "bullets": ["主论点", "支持证据"], "source_ids": ["S1"]
  }]
}
```

示例 URL 只说明结构，实际研究任务需替换成核对过的来源；来源可增加作者、年份、核对状态与限制。无外部事实的流程演示可以 `sources: []`。

## 页面字段

通用字段：`id`（唯一）、`kind`、`title`、`kicker`、`subtitle`、`narration`、`source_ids`、`footer`。画布推荐维持16:9；模板在1920×1080设计基准上排版。

| kind | 特有内容 |
| --- | --- |
| `title` | `tags`；可选 `formats: [{title,text,icon}]`，icon为slide/doc/play |
| `cards` | `columns: [{label,title,text,value,highlight}]`，最多四列；或 `bullets` / `quote` |
| `evidence` | `big_number`、`number_label`、`number_note`、`bars: [{label,value,display}]`、`bar_max`、`note` |
| `flow` | `steps: [{title,text}]`，推荐三步 |
| `decision` | `rows: [{goal,format}]`，推荐三行 |
| `closing` | `quote`、`footline` |

显示字符串支持换行。输入使用普通文本，模板会转义HTML。需要重新导出视频的自定义画面，应修改 skill 的 `assets/deck-template.html` / `theme.css` 后重新构建；输出HTML可独立编辑预览，但再次执行 `render` 或 `build` 会覆盖输出HTML/CSS。图表不得用虚构数值表现“强弱”。

## 发音、分段与录音

```json
"narration_segments": [
  {"text": "PPT适合组织讲解。", "spoken": "幻灯片适合组织讲解。"},
  {"text": "文档便于检索。"}
]
```

使用 `narration_segments` 时替代普通 `narration` 合成。每段优先包含完整句子，实际合成、解码并测量；`text != spoken` 使用段级时间，不假定字符一一对应。不要为了字幕字数上限拆断句子。过多短段可能使声音断续，先试短样片。

语速分两层：`voice.rate` 是TTS的基准语速，`voice.speed` 是此基础上的保音高倍率，默认1，支持0.5～2。例如原配音为 `rate: "+5%"`，用户要求“加到当前1.25倍”，保留rate并设置 `speed: 1.25`。音频通过FFmpeg `atempo`处理，词／句边界按相同倍率缩放，最终时长仍按处理后的实际PCM采样数计算，场景头尾停顿保持原配置。只改speed可复用原始合成缓存；改稿则重做受影响的配音。

已有录音设置 `scene.audio`（相对report.json或绝对路径），配 `scene.captions: [{start_ms,end_ms,text}]`；时间相对该段原始录音，不包含脚本添加的头尾停顿。无字幕时只能显示整段文本，不会自动获得精确词边界；长文本必须提供分段字幕或进行另行对齐。

当前不直接解析外部SRT文件；先将SRT转换为上述 `scene.captions` 记录。输出的SRT可直接用于其他编辑器。

## 不累计误差

音频统一为48kHz、单声道PCM16。默认每场景头150ms、尾350ms，可用报告级 `lead_ms` / `tail_ms` 调整。时间轴保存实际样本范围，字幕加上场景起点与头停顿。

第k个边界帧为 `ceil(累计样本数 × fps / 48000)`；场景帧数是相邻累计边界之差。不能对每页单独向上取整后累加。

TTS保存原始WordBoundary/SentenceBoundary。词事件按真实边界组合，只有精确匹配原文时恢复标点；句／段时间保留其精度。中文词事件在句号、问号、叹号及其闭引号处组成完整句cue；分号、逗号、长停顿和字数上限都不能直接截断一句话。SRT为毫秒，ASS为百分之一秒，其量化不能用于宣称超出输入精度的同步。

`max_caption_chars` 默认36，表示每行排版目标，不是单条cue的截断上限。长句保留在同一cue内，用第二行承接；优先选择能兼顾两行长度的句内标点，避免只因最近有逗号就排成一短一超长。完整句超出两行可读范围时，优先简化稿件或调整字幕布局，不在未知时间边界内制造精确分段。字幕样式默认46px、底边距72px，需在最终视频中检查两行与来源区的间距。

当前编码用硬切。若扩展重叠淡化，需在统一时间轴内计算重叠、音频和字幕偏移，不能只在最终FFmpeg命令里追加转场。
