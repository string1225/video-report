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

使用 `narration_segments` 时替代普通 `narration` 合成。每段实际合成、解码并测量；`text != spoken` 使用段级时间，不假定字符一一对应。过多短段可能使声音断续，先试短样片。

已有录音设置 `scene.audio`（相对report.json或绝对路径），配 `scene.captions: [{start_ms,end_ms,text}]`；时间相对该段原始录音，不包含脚本添加的头尾停顿。无字幕时只能显示整段文本，不会自动获得精确词边界；长文本必须提供分段字幕或进行另行对齐。

当前不直接解析外部SRT文件；先将SRT转换为上述 `scene.captions` 记录。输出的SRT可直接用于其他编辑器。

## 不累计误差

音频统一为48kHz、单声道PCM16。默认每场景头150ms、尾350ms，可用报告级 `lead_ms` / `tail_ms` 调整。时间轴保存实际样本范围，字幕加上场景起点与头停顿。

第k个边界帧为 `ceil(累计样本数 × fps / 48000)`；场景帧数是相邻累计边界之差。不能对每页单独向上取整后累加。

TTS保存原始WordBoundary/SentenceBoundary。词事件按真实边界组合，只有精确匹配原文时恢复标点；句／段时间保留其精度。SRT为毫秒，ASS为百分之一秒，其量化不能用于宣称超出输入精度的同步。

长字幕优先改稿或短分段，不在未知词边界内制造逐词时间。`max_caption_chars` 默认22，字幕样式默认46px、底边距72px，均需在真实视频帧检查。

当前编码用硬切。若扩展重叠淡化，需在统一时间轴内计算重叠、音频和字幕偏移，不能只在最终FFmpeg命令里追加转场。
