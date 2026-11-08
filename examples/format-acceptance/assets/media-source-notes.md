# 本轮真实素材与使用边界

核对日期：2026-11-08。最终交付3张真实来源图片与1段6秒动态实拍片段；不使用AI生成图片、占位图、电影或无关景物。下载和编辑仅发生在本目录以及仓库忽略目录 `output/source-downloads/`。报告JSON、代码和Git由主任务处理。

## 建议插入位置

| ID | 最终文件 | 建议场景 | 内容与边界 |
|---|---|---|---|
| M1 | presentation-lecture.jpg | slides-design | 真实活动讲解照片，1200×800。可说明PPT配合现场讲解；不是Garner & Alley实验现场，也不呈现该研究的幻灯片。 |
| M2 | reading-document.jpg | choose-by-task | 真实读纸质资料的照片，450×470，已将大部分城市景物裁掉。仅为文档阅读情境；不推断人物身份、阅读内容或阅读效果。 |
| M3 | donkor-performance-table.png | practical-vs-theory 的原文证据备选 | 1000×375，官方论文印刷页105的Table 2原图。保留表名、表头、两组数据、显著性脚注；不是重绘图。若每页只能放单一媒体，则动作页优先使用M4，不为放此图增加页面或重复文案。 |
| M4 | bowline-steps.webm | practical-vs-theory | 652×424方形像素，30fps，6.000秒，无音轨。原片13–19秒的手部打绳结步骤，可循环。必须保留“绳结步骤示意，非研究现场”标识；不声称是Donkor研究中的砌筑、抹灰或参与者记录。 |

M3仍需配合报告中原有69人、35/34分组与职业教育情境解释，不能把这一个表推广为所有媒介的通用排名。原表实操满分50分，均值31.84和35.20是得分；其差值与p值都不是接受度比例。选择M4是为了让观众看见动态动作，不能把示意片段当作研究数据。

## 原始来源与许可证据

1. **M1 — Ralf Rebmann / Wikimedia Deutschland, Freies Wissen Fellow Presentation**
   - 原始文件说明页：<https://commons.wikimedia.org/wiki/File:Freies_Wissen_Fellow_Presentation.jpg>
   - Commons说明和浏览器核对均明确列出“Ralf Rebmann”及“Creative Commons Attribution-Share Alike 4.0 International”。
   - 许可：<https://creativecommons.org/licenses/by-sa/4.0/>。
   - 最终JPEG逐字节复制官方原图，未裁切、改色或重压缩。画面署名建议：`现场讲解示意｜Ralf Rebmann / Wikimedia Deutschland · CC BY-SA 4.0`。
   - API留档：`output/source-downloads/photo-candidates-metadata.json`。

2. **M2 — Ștefan Jurcă, The fantastic world of reading ... a document**
   - 原始说明页：<https://commons.wikimedia.org/wiki/File:The_fantastic_world_of_reading_..._a_document_(27184970803).jpg>
   - Flickr原页：<https://www.flickr.com/photos/stefanjurca/27184970803/>。Commons记录FlickreviewR在2016-07-29核验为CC BY 2.0，浏览器核对亦显示该记录。
   - 许可：<https://creativecommons.org/licenses/by/2.0/>。
   - 从2048×1360原图裁切(1550,690,2000,1160)，输出450×470，JPEG重压缩；没有合成人物、修改纸张或替换阅读内容。
   - 画面署名建议：`纸质资料阅读示意｜Ștefan Jurcă · CC BY 2.0 · 已裁切`。
   - API及浏览器留档：`output/source-downloads/reading-document-metadata.json`、`reading-document-browser-evidence.txt`。

3. **M3 — Francis Donkor (2010), Table 2**
   - 文章原页：<https://www.irrodl.org/index.php/irrodl/article/view/792>。
   - 官方PDF：<https://www.irrodl.org/index.php/irrodl/article/download/792/1506>；DOI：<https://doi.org/10.19173/irrodl.v11i1.792>。
   - 当前文章原页明确写明：`This work is licensed under a Creative Commons Attribution 4.0 International License. The copyright for all content published in IRRODL remains with the authors.` 浏览器亦核对到CC BY 4.0页脚。许可：<https://creativecommons.org/licenses/by/4.0/>。
   - 原PDF共21页；第10页对应印刷页105，以Poppler 160dpi渲染后裁切表2区域(180,145,1180,520)，保留完整表格和脚注。未改变数字、显著性符号、统计名称或比较方向。
   - 原PDF及许可HTML留档：`output/source-downloads/donkor-2010.pdf`、`donkor-2010-article.html`。
   - 画面署名建议：`原文表2｜Donkor，2010，p.105 · CC BY 4.0 · 已裁切`。

4. **M4 — Zybukin, Palstek Bowline**
   - 原始说明页：<https://commons.wikimedia.org/wiki/File:Palstek_Bowline.ogv>。
   - 原OGV：<https://upload.wikimedia.org/wikipedia/commons/6/6c/Palstek_Bowline.ogv>。
   - 原页说明“How to create a Bowline”，作者Zybukin，own work，2010-08-25。原文件说明为38秒；ffprobe实测37.957726秒。
   - 原页可选CC BY-SA 3.0或GFDL；本交付选择CC BY-SA 3.0：<https://creativecommons.org/licenses/by-sa/3.0/>。不是使用Commons网站页脚的通用文字许可。
   - 取原片13–19秒，保留原速，无音轨，VP9/WebM转码。原编码640×424像素、SAR163:160，转换为652×424、SAR1:1，保留显示比例。最终6.000秒、30fps。
   - 此剪辑改编文件以CC BY-SA 3.0分发。应保留作者、原片链接、许可链接，以及节选/转码/像素规范化的改动说明。视频旁标识建议：`绳结步骤示意，非研究现场｜Zybukin · CC BY-SA 3.0 · 节选/静音`。
   - API留档：`output/source-downloads/bowline-metadata.json`；原片留档：`bowline-original.ogv`。

## 许可随交付保留

外部素材分别保留上面的许可，不能由代码仓库的MIT许可覆盖。M1原图保留CC BY-SA 4.0；M4节选改编保留CC BY-SA 3.0，继续改编时须遵守对应的相同方式共享条款。报告的署名区或媒体来源页应提供完整`attribution`与链接，画面内可使用较短`usage_caption`。不得写成摄影师、示意人物或原作者为本报告结论背书。

## 核验

- 三张最终图片已逐张打开检查：人物和纸张可见，原表数字/脚注完整，JPEG与PNG可读。
- 最终WebM已用FFmpeg完整解码，共180帧，180个不同的解码帧哈希，确认为真实动态片段。
- Ego Lite Chromium已确认VP9可解码、载入并定位到第2秒，三张图片均完成载入。浏览器验证截图位于`output/source-downloads/media-browser-verification.png`。
- 每个最终资产的尺寸、字节数和SHA-256在`sources.json`记录，供打包后复核。
- 曾评估第二张讲座观众照片，最终未采用；未下载不相关建筑/风景搜索命中。正式保留4个来源条目，符合3–4份素材的小规模选择。
