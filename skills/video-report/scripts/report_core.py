"""Portable report validation, timing, and subtitle utilities (standard library only)."""

from __future__ import annotations

from decimal import Decimal, ROUND_CEILING
import hashlib
import json
import math
from pathlib import Path
import re


def _number(value):
    return isinstance(value, (int, float)) and not isinstance(value, bool) and math.isfinite(value)


def validate_report(report: dict) -> list[str]:
    errors = []
    if not isinstance(report, dict):
        return ['report must be an object']
    if not isinstance(report.get('title'), str) or not report['title'].strip():
        errors.append('title must be a nonempty string')
    for key, default in [('width', 1920), ('height', 1080)]:
        value = report.get(key, default)
        if not isinstance(value, int) or isinstance(value, bool) or value <= 0 or value % 2:
            errors.append(f'{key} must be a positive even integer')
    fps = report.get('fps', 30)
    if not _number(fps) or not 1 <= fps <= 120:
        errors.append('fps must be a finite number between 1 and 120')
    source_ids = set()
    sources = report.get('sources', [])
    if not isinstance(sources, list):
        errors.append('sources must be a list')
        sources = []
    for index, source in enumerate(sources):
        if not isinstance(source, dict) or not isinstance(source.get('id'), str) or not source['id'].strip():
            errors.append(f'sources[{index}].id must be a nonempty string')
            continue
        if source['id'] in source_ids:
            errors.append(f'duplicate source id: {source["id"]}')
        source_ids.add(source['id'])
    scenes = report.get('scenes')
    if not isinstance(scenes, list) or not scenes:
        errors.append('scenes must be a nonempty list')
        return errors
    ids = set()
    for index, scene in enumerate(scenes):
        prefix = f'scenes[{index}]'
        if not isinstance(scene, dict):
            errors.append(f'{prefix} must be an object')
            continue
        for field in ('id', 'kind', 'title'):
            if not isinstance(scene.get(field), str) or not scene[field].strip():
                errors.append(f'{prefix}.{field} must be a nonempty string')
        scene_id = scene.get('id')
        if isinstance(scene_id, str):
            if scene_id in ids:
                errors.append(f'duplicate scene id: {scene_id}')
            ids.add(scene_id)
        segments = scene.get('narration_segments')
        if segments is not None:
            valid = isinstance(segments, list) and len(segments) > 0
            if valid:
                valid = all(isinstance(s, dict) and isinstance(s.get('text'), str)
                            and s['text'].strip() and isinstance(s.get('spoken', s['text']), str)
                            and s.get('spoken', s['text']).strip() for s in segments)
            if not valid:
                errors.append(f'{prefix}.narration_segments must contain nonempty text and spoken strings')
        elif not isinstance(scene.get('narration'), str) or not scene['narration'].strip():
            errors.append(f'{prefix}.narration must be nonempty')
        refs = scene.get('source_ids', [])
        if not isinstance(refs, list):
            errors.append(f'{prefix}.source_ids must be a list')
        else:
            for ref in refs:
                if not isinstance(ref, str) or ref not in source_ids:
                    errors.append(f'{prefix} references unknown source: {ref}')
    for key, default in [('lead_ms', 150), ('tail_ms', 350)]:
        value = report.get(key, default)
        if not _number(value) or value < 0:
            errors.append(f'{key} must be a finite nonnegative number')
    return errors


def cache_key(payload) -> str:
    canonical = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(',', ':'), allow_nan=False)
    return hashlib.sha256(canonical.encode('utf-8')).hexdigest()


def make_timeline(durations_ms: list[float], fps=30) -> list[dict]:
    if not _number(fps) or fps <= 0:
        raise ValueError('fps must be finite and positive')
    elapsed = Decimal(0)
    frames_per_ms = Decimal(str(fps)) / 1000
    result = []
    for duration in durations_ms:
        if not _number(duration) or duration < 0:
            raise ValueError('durations must be finite and nonnegative')
        end = elapsed + Decimal(str(duration))
        result.append({'start_ms': float(elapsed), 'end_ms': float(end), 'duration_ms': float(end - elapsed),
                       'start_frame': int((elapsed * frames_per_ms).to_integral_value(rounding=ROUND_CEILING)),
                       'end_frame': int((end * frames_per_ms).to_integral_value(rounding=ROUND_CEILING))})
        elapsed = end
    return result


def _two_lines(text: str, max_chars: int = 36) -> str:
    text = text.replace('\r', '')
    if text.count('\n') == 1:
        return text
    text = text.replace('\n', '')
    if len(text) <= max_chars:
        return text
    # A line break affects layout only; it never fabricates a timing boundary.
    midpoint = len(text) // 2
    # Prefer an existing clause boundary only when both lines remain balanced.
    # A length limit controls line layout, never a new timed subtitle cue.
    limit = max(max_chars, math.ceil(len(text) / 2))
    candidates = [m.end() for m in re.finditer(r'[，。！？；、,.;!? ]', text)
                  if 0 < m.end() < len(text) and max(m.end(), len(text)-m.end()) <= limit]
    if not candidates:
        candidates = [p for p in range(1, len(text))
                      if max(p, len(text)-p) <= limit and text[p] not in '，。！？；：、,.!?;:）】》」』”’']
    split = min(candidates, key=lambda p: abs(p - midpoint)) if candidates else midpoint
    return text[:split] + '\n' + text[split:]


def _join_words(left, right):
    if left and right and re.search(r'[A-Za-z0-9]$', left) and re.match(r'[A-Za-z0-9]', right):
        return left + ' ' + right
    return left + right


def make_captions(events: list[dict], max_chars=36) -> list[dict]:
    if not isinstance(max_chars, int) or max_chars < 1:
        raise ValueError('max_chars must be positive')
    result = []
    pending = None
    previous_end = 0

    def flush():
        nonlocal pending
        if pending:
            pending['text'] = _two_lines(pending['text'], max_chars)
            result.append(pending)
            pending = None

    for event in sorted(events, key=lambda e: e['start_ms']):
        start, end, text = event['start_ms'], event['end_ms'], event['text']
        if not _number(start) or not _number(end) or start < 0 or end <= start:
            raise ValueError('caption events require finite, positive time intervals')
        if not isinstance(text, str) or not text.strip():
            continue
        # Allow only sub-nanosecond floating-point conversion noise. Reject
        # overlaps before grouping words, which otherwise hides invalid input.
        if start < previous_end - 1e-6:
            raise ValueError('caption events overlap')
        previous_end = end
        timing = event.get('type', 'sentence').lower()
        if timing != 'word':
            flush()
            result.append({'start_ms': start, 'end_ms': end, 'text': _two_lines(text, max_chars),
                           'timing': 'segment' if timing == 'segment' else 'sentence'})
            continue
        joined = _join_words(pending['text'], text) if pending else text
        if pending:
            pending.update(text=joined, end_ms=end)
        else:
            pending = {'start_ms': start, 'end_ms': end, 'text': text, 'timing': 'word'}
        # Semicolons and long pauses may be inside one sentence. Preserve the
        # whole sentence, including a closing quote, on one (possibly 2-line) cue.
        if re.search(r'[。！？!?][”’"\'）)\]】」』]*\s*$', text):
            flush()
    flush()
    return result


def _stamp(milliseconds, ass=False):
    unit = 10 if ass else 1
    total = max(0, int(round(float(milliseconds) / unit)))
    per_second = 100 if ass else 1000
    hours, rem = divmod(total, 3600 * per_second)
    minutes, rem = divmod(rem, 60 * per_second)
    seconds, fraction = divmod(rem, per_second)
    return f'{hours}:{minutes:02}:{seconds:02}.{fraction:02}' if ass else f'{hours:02}:{minutes:02}:{seconds:02},{fraction:03}'


def write_srt(captions: list[dict], path: Path):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    blocks = [f'{i}\n{_stamp(c["start_ms"])} --> {_stamp(c["end_ms"])}\n{c["text"]}\n'
              for i, c in enumerate(captions, 1)]
    path.write_text('\n'.join(blocks), encoding='utf-8')


def _ass_escape(text):
    return text.replace('\\', '\\\\').replace('{', r'\{').replace('}', r'\}').replace('\r', '').replace('\n', r'\N')


def write_ass(captions: list[dict], path: Path, width=1920, height=1080,
              font='Microsoft YaHei', font_size=46):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    font = str(font).replace(',', '').replace('\n', '')
    header = f'''[Script Info]
ScriptType: v4.00+
PlayResX: {width}
PlayResY: {height}
WrapStyle: 2
ScaledBorderAndShadow: yes

[V4+ Styles]
Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding
Style: Default,{font},{font_size},&H00FFFFFF,&H000000FF,&H00101010,&H90000000,0,0,0,0,100,100,0,0,1,2.5,0,2,100,100,72,1

[Events]
Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text
'''
    lines = []
    for caption in captions:
        text = _ass_escape(_two_lines(caption['text']))
        lines.append(f'Dialogue: 0,{_stamp(caption["start_ms"], True)},{_stamp(caption["end_ms"], True)},Default,,0,0,72,,{text}')
    path.write_text(header + '\n'.join(lines) + '\n', encoding='utf-8-sig')
