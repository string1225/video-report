# Video Report Skill Implementation Plan

> **For agentic workers:** Use superpowers:subagent-driven-development for independent implementation tasks and review. Execute continuously; the user requested direct creation of the research video.

**Goal:** Deliver an installed, reusable video-report skill and its first real Chinese research video comparing acceptance of PPT, documents and explanatory video.

**Architecture:** Python orchestrates segmented TTS, sample-based audio timing, HTML screenshots, subtitles and FFmpeg encoding. All outputs share one timeline. Research inputs and derived recommendations retain separate evidence labels.

**Tech Stack:** Python 3.12+ in a project venv, Playwright/Chromium, edge-tts, Pillow, FFmpeg/ffprobe; local Chinese fonts.

## Files and responsibilities

- `skills/video-report/SKILL.md`, `agents/openai.yaml`: discovery and concise workflow.
- `skills/video-report/references/`: content SOP, data contract, design and environment troubleshooting.
- `skills/video-report/scripts/bootstrap.py`, `doctor.py`: isolated setup and diagnostics.
- `skills/video-report/scripts/video_report.py`: public CLI and stage orchestration.
- `skills/video-report/scripts/report_core.py`: validation, timeline, captions and cache keys.
- `skills/video-report/scripts/report_media.py`: TTS, audio preparation, media encoding/checks.
- `skills/video-report/scripts/report_render.py`: HTML generation, screenshots and contact sheets.
- `skills/video-report/assets/`: deterministic HTML/CSS and small runnable example.
- `tests/test_core.py`, `tests/test_pipeline.py`: timing, captions, invalid input and real media integration.
- `docs/research/`: evidence register, research synthesis and skill evaluation notes.
- `examples/format-acceptance/`: report input, storyboard and sources; generated media in ignored `output/`.

## Task 1 — Evidence and baseline

- [x] Run no-skill application scenarios covering timing drift, unavailable word alignment, edge-tts SSML, unsupported acceptance claims and partial failures.
- [x] Retrieve primary studies/reviews. Record population, outcome, effect size and comparison; label preference, engagement and learning separately.
- [x] Reject universal three-format rankings unless directly supported by comparable evidence.
- [x] Draft a 3–5 minute narration with per-scene source IDs and an explicit distinction between research findings and practical recommendations.

## Task 2 — Environment

- [x] Create `.venv` and install exact tested versions. Locate existing FFmpeg/ffprobe and Chromium first; install missing dependencies locally.
- [x] Add `.gitignore` for venv, tools, caches and generated media.
- [x] Implement bootstrap and doctor; bootstrap invokes `sys.executable`, venv pip and `python -m playwright install chromium` using argument arrays.
- [x] Doctor checks actual Chinese rendering and required encoders/filters, not executable existence alone.

## Task 3 — Timing and captions, test first

- [x] Add failing unit cases before implementing `report_core.py`.

```python
def test_cumulative_quantization_does_not_accumulate():
    durations = [19987] * 30
    timeline = make_timeline(durations, fps=30)
    assert timeline[-1]['end_frame'] == round(sum(durations) * 30 / 1000)

def test_sentence_boundary_does_not_claim_word_alignment():
    cues = make_captions([{'start_ms': 0, 'end_ms': 6000,
                           'text': '这是一句需要显示的研究说明。'}])
    assert cues[0]['timing'] == 'sentence'
```

- [x] Run `python -m unittest discover -s tests -v`; confirm the new tests fail because the implementation is missing.
- [x] Implement input validation, bounded subtitle segmentation, global offsets, cumulative frame quantization and stable cache keys. Include version identifiers in the cache keys.
- [x] Repeat tests; add cases for negative/overlapping/out-of-range captions, duplicate scene IDs, unknown source IDs and missing required input.

## Task 4 — Media pipeline

- [x] Write integration tests that use a short generated PCM waveform and externally supplied timed captions; verify frame count, audible output, subtitle timing and failure on missing audio.
- [x] Implement segmented edge-tts using service boundaries, bounded retries, atomic cache writes and resumability. Split long narration at punctuation; retain exact segment start/end timing where no usable word event exists.
- [x] Decode segments to fixed-rate WAV and derive offsets from sample counts. Concatenate PCM, create timeline and SRT/ASS from the same offsets.
- [x] Encode H.264/AAC/yuv420p at fixed fps, burn captions, inspect metadata with ffprobe, decode the full output and check non-silent audio.
- [x] On network failure stop with actionable diagnostics; never fill missing narration with silence.

## Task 5 — Editable presentation

- [x] Build a restrained editorial template with distinct layouts for conclusion, evidence, comparison, process and recommendation. Keep key typography and diagrams native HTML/SVG.
- [x] Provide `renderAt(timeMs)`, scene navigation, audio playback and progress controls. All preview timing follows the master audio.
- [x] Export cue states with Playwright after fonts/images are ready; reject missing assets, page errors and overflow.
- [x] Generate contact sheet/poster and inspect every scene at actual 1920×1080. Exercise next/previous, seek and play/pause.
- [x] Browser plugin is absent; use regular Playwright and record this fallback in the QA record.

## Task 6 — Skill package and actual video

- [x] Write the concise skill after the baseline identifies the useful guidance; keep schemas and operational detail in references.
- [x] Expose `init`, `validate`, `tts`, `render`, `build`, `check`; document exact working commands, dependencies and tested platform versions.
- [x] Run a short sample first, then render the complete research video. Save report, sources, storyboard, HTML, subtitles, voice, timeline, manifest and QA.
- [x] Test resume/caching, a Chinese-and-space output path, network/asset failure and changed narration invalidation.
- [x] Run the same skill application scenarios with the skill; record observed improvements and residual limitations.
- [x] Review spec compliance before code quality. Fix material findings and rerun relevant checks.
- [x] Install the validated skill in the personal skill directory without overwriting an existing unrelated skill.
- [x] Commit intended source/research/example files, push the feature branch, and deliver the local video and editable source links.

## Verification commands

Use the actual venv executable in PowerShell:

```powershell
.venv/Scripts/python.exe -m unittest discover -s tests -v
.venv/Scripts/python.exe skills/video-report/scripts/doctor.py
.venv/Scripts/python.exe skills/video-report/scripts/video_report.py validate examples/format-acceptance/report.json
.venv/Scripts/python.exe skills/video-report/scripts/video_report.py build examples/format-acceptance/report.json --output output/format-acceptance
.venv/Scripts/python.exe skills/video-report/scripts/video_report.py check output/format-acceptance
git diff --check
```

Expected: tests pass; doctor confirms working dependencies; validation preserves evidence links; full build produces a playable Chinese narrated, subtitled video; QA distinguishes automated checks from human visual/audio review.


## Execution record

All tasks completed. The runtime, 36-test result, installed skill and full media QA are recorded in `examples/format-acceptance/qa-summary.json`. The short TTS probe and real media integration preceded the full video; the standalone 42.70-second Chinese-path smoke video was completed afterward. Azure, ASR, continuous animation and native external SRT parsing remain outside the implemented scope.
