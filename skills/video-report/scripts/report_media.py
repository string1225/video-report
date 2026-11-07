"""Real audio synthesis, sample-based assembly, FFmpeg encoding, and media QA.

edge-tts is imported only when synthesis is needed. External WAV/MP3 recordings
and all timing helpers remain usable without that optional Python dependency.
"""

from __future__ import annotations

import asyncio
from fractions import Fraction
import hashlib
import importlib.metadata
import inspect
import json
import math
import os
from pathlib import Path
import re
import shutil
import subprocess
import tempfile
import time
import unicodedata
import uuid
import wave

from report_core import cache_key, make_captions, validate_report, write_ass, write_srt

SAMPLE_RATE = 48000
CACHE_SCHEMA = 2


def _atomic_json(path: Path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(path.name + '.' + uuid.uuid4().hex + '.tmp')
    try:
        temporary.write_text(json.dumps(data, ensure_ascii=False, indent=2, allow_nan=False), encoding='utf-8')
        os.replace(temporary, path)
    finally:
        temporary.unlink(missing_ok=True)


def resolve_tools() -> dict:
    """Resolve explicit overrides, PATH, then portable project tool directories.

    VIDEO_REPORT_DEPENDENCIES may point to a JSON object containing ffmpeg and
    ffprobe executable paths, for environments that publish a dependency manifest.
    """
    declared = {}
    declaration = os.environ.get('VIDEO_REPORT_DEPENDENCIES')
    ancestors = list(Path(__file__).resolve().parents) + [Path.cwd(), *Path.cwd().parents]
    result = {}
    for name in ('ffmpeg', 'ffprobe'):
        override = os.environ.get('VIDEO_REPORT_' + name.upper())
        if override:
            candidate = Path(override).expanduser()
            resolved = str(candidate.resolve()) if candidate.is_file() else shutil.which(override)
            if not resolved:
                raise RuntimeError(f'VIDEO_REPORT_{name.upper()} does not identify an executable: {override}')
            result[name] = resolved
            continue
        on_path = shutil.which(name)
        if on_path:
            result[name] = on_path
            continue
        candidates = []
        for root in ancestors:
            for sub in ('.tools/ffmpeg/bin', '.tools/bin'):
                candidates.extend((root / sub / (name + '.exe'), root / sub / name))
        if not any(p.is_file() for p in candidates) and declaration:
            try:
                declared = json.loads(Path(declaration).read_text(encoding='utf-8-sig'))
            except (OSError, ValueError) as exc:
                raise RuntimeError(f'Cannot read VIDEO_REPORT_DEPENDENCIES: {exc}') from exc
            if isinstance(declared, dict) and declared.get(name):
                declared_path = Path(declared[name]).expanduser()
                if not declared_path.is_absolute():
                    declared_path = Path(declaration).resolve().parent / declared_path
                candidates.append(declared_path)
        other_override = os.environ.get(name.upper() + '_BINARY')
        if other_override:
            candidates.append(Path(other_override).expanduser())
        match = next((p.resolve() for p in candidates if p.is_file()), None)
        if match is None:
            raise RuntimeError(f'{name} was not found. Install FFmpeg or set VIDEO_REPORT_{name.upper()}.')
        result[name] = str(match)
    return result


def _run(command, timeout=180, cwd=None):
    try:
        completed = subprocess.run([str(arg) for arg in command], cwd=cwd, timeout=timeout,
                                   stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                                   text=True, encoding='utf-8', errors='replace',
                                   creationflags=subprocess.CREATE_NO_WINDOW if os.name == 'nt' else 0)
    except subprocess.TimeoutExpired as exc:
        stderr = exc.stderr or ''
        if isinstance(stderr, bytes):
            stderr = stderr.decode('utf-8', errors='replace')
        raise RuntimeError(f'{Path(str(command[0])).name} timed out after {timeout}s\n{stderr[-5000:]}') from exc
    except OSError as exc:
        raise RuntimeError(f'Cannot execute {command[0]}: {exc}') from exc
    if completed.returncode:
        raise RuntimeError(f'{Path(str(command[0])).name} failed (exit {completed.returncode})\n{completed.stderr[-5000:]}')
    return completed


def _read_pcm(path):
    try:
        with wave.open(str(path), 'rb') as audio:
            if (audio.getnchannels(), audio.getsampwidth(), audio.getframerate(), audio.getcomptype()) != (1, 2, SAMPLE_RATE, 'NONE'):
                raise RuntimeError(f'Expected 48 kHz mono PCM16 audio: {path}')
            samples = audio.getnframes()
            data = audio.readframes(samples)
        if samples <= 0 or len(data) != samples * 2:
            raise RuntimeError(f'Incomplete or empty audio: {path}')
        return data
    except (wave.Error, EOFError, OSError) as exc:
        raise RuntimeError(f'Cannot read complete PCM audio {path}: {exc}') from exc


def _write_pcm(path, data):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(path.stem + '.' + uuid.uuid4().hex + '.tmp.wav')
    try:
        with wave.open(str(temporary), 'wb') as audio:
            audio.setparams((1, 2, SAMPLE_RATE, 0, 'NONE', 'not compressed'))
            audio.writeframes(data)
        os.replace(temporary, path)
    finally:
        temporary.unlink(missing_ok=True)


def _speech_pcm(path):
    data = _read_pcm(path)
    if not any(data):
        raise RuntimeError(f'Speech audio is silent: {path}')
    return data


def _normalize_audio(source, target, tools):
    target = Path(target)
    target.parent.mkdir(parents=True, exist_ok=True)
    temporary = target.with_name(target.stem + '.' + uuid.uuid4().hex + '.tmp.wav')
    try:
        _run([tools['ffmpeg'], '-hide_banner', '-v', 'error', '-y', '-i', source,
              '-vn', '-ac', '1', '-ar', SAMPLE_RATE, '-c:a', 'pcm_s16le', temporary], timeout=180)
        _read_pcm(temporary)
        os.replace(temporary, target)
    finally:
        temporary.unlink(missing_ok=True)


def _provider_version():
    try:
        return importlib.metadata.version('edge-tts')
    except importlib.metadata.PackageNotFoundError:
        return 'not-installed'


async def _edge_stream(text, voice, audio_path):
    try:
        import edge_tts
    except ImportError as exc:
        raise RuntimeError('Speech synthesis requires edge-tts. Install the skill requirements first.') from exc
    kwargs = {'voice': voice.get('name', 'zh-CN-XiaoxiaoNeural'), 'rate': voice.get('rate', '+0%')}
    for field, default in [('pitch', '+0Hz'), ('volume', '+0%')]:
        kwargs[field] = voice.get(field, default)
    if 'boundary' in inspect.signature(edge_tts.Communicate).parameters:
        kwargs['boundary'] = 'WordBoundary'
    communicator = edge_tts.Communicate(text, **kwargs)
    events = []
    count = 0
    with audio_path.open('wb') as audio:
        async for chunk in communicator.stream():
            if chunk['type'] == 'audio':
                audio.write(chunk['data'])
                count += len(chunk['data'])
            else:
                events.append({k: v for k, v in chunk.items() if k != 'data'})
    if count == 0:
        raise RuntimeError('TTS provider returned no audio bytes')
    return events


def _tts_audio(text, voice, cache_root, tools):
    """Synthesize one measured unit; publish cache metadata only after conversion."""
    cache_root = Path(cache_root)
    cache_root.mkdir(parents=True, exist_ok=True)
    settings = {'name': 'zh-CN-XiaoxiaoNeural', 'rate': '+0%', 'pitch': '+0Hz', 'volume': '+0%', **voice}
    payload = {'schema': CACHE_SCHEMA, 'provider': 'edge-tts', 'provider_version': _provider_version(),
               'text': text, 'voice': settings, 'sample_rate': SAMPLE_RATE}
    key = cache_key(payload)
    destination = cache_root / key
    try:
        meta = json.loads((destination / 'meta.json').read_text(encoding='utf-8'))
        events = json.loads((destination / 'events.json').read_text(encoding='utf-8'))
        pcm = _speech_pcm(destination / 'wave.wav')
        if (meta.get('complete') and meta.get('cache_key') == key
                and meta.get('samples') == len(pcm) // 2 and (destination / 'audio.mp3').stat().st_size > 0):
            return {'wave': destination / 'wave.wav', 'events': events, 'cache_key': key, 'cache_hit': True}
    except (OSError, ValueError, RuntimeError):
        pass
    last_error = None
    for attempt in range(3):
        with tempfile.TemporaryDirectory(prefix='.' + key[:12] + '-', dir=cache_root) as scratch:
            temporary = Path(scratch)
            try:
                events = asyncio.run(asyncio.wait_for(_edge_stream(text, settings, temporary / 'audio.mp3'), timeout=60))
                if not (temporary / 'audio.mp3').is_file() or (temporary / 'audio.mp3').stat().st_size == 0:
                    raise RuntimeError('TTS provider returned empty audio')
                _normalize_audio(temporary / 'audio.mp3', temporary / 'wave.wav', tools)
                samples = len(_speech_pcm(temporary / 'wave.wav')) // 2
                _atomic_json(temporary / 'events.json', events)
                _atomic_json(temporary / 'meta.json', {**payload, 'cache_key': key, 'complete': True, 'samples': samples})
                destination.mkdir(parents=True, exist_ok=True)
                # meta.json is the commit marker and is always published last.
                for name in ('audio.mp3', 'wave.wav', 'events.json', 'meta.json'):
                    os.replace(temporary / name, destination / name)
                return {'wave': destination / 'wave.wav', 'events': events, 'cache_key': key, 'cache_hit': False}
            except (Exception, asyncio.TimeoutError) as exc:
                last_error = exc
        if attempt < 2:
            time.sleep(0.25 * (attempt + 1))
    raise RuntimeError(f'TTS failed after 3 attempts for {text[:60]!r}: {last_error}') from last_error


def _event_captions(events, text, duration_ms, max_chars):
    words = [e for e in events if e.get('type') == 'WordBoundary']
    if words:
        # Provider word tokens often omit punctuation. Restore only characters
        # between exact token matches; never align a normalized pronunciation by
        # guessing where its characters belong on the audio timeline.
        decorated = []
        cursor = 0
        def punctuation(value):
            return all(c.isspace() or unicodedata.category(c).startswith('P') for c in value)
        for word in words:
            token = str(word.get('text', ''))
            position = text.find(token, cursor) if token else -1
            gap = text[cursor:position] if position >= 0 else ''
            if position < 0 or not punctuation(gap):
                decorated = []
                break
            if decorated:
                decorated[-1]['text'] += gap
                gap = ''
            decorated.append({**word, 'text': gap + token})
            cursor = position + len(token)
        if decorated and punctuation(text[cursor:]):
            decorated[-1]['text'] += text[cursor:]
            words = decorated
    selected = words or [e for e in events if e.get('type') == 'SentenceBoundary']
    converted = []
    for event in selected:
        start = max(0.0, float(event.get('offset', 0)) / 10000)
        end = min(duration_ms, start + float(event.get('duration', 0)) / 10000)
        if end > start and str(event.get('text', '')).strip():
            converted.append({'start_ms': start, 'end_ms': end, 'text': event['text'],
                              'type': 'word' if words else 'sentence'})
    if not converted:
        converted = [{'start_ms': 0, 'end_ms': duration_ms, 'text': text, 'type': 'segment'}]
    return make_captions(converted, max_chars=max_chars)


def _external_captions(scene, duration_ms, max_chars):
    provided = scene.get('captions')
    if provided is None:
        text = scene.get('narration') or ''.join(s['text'] for s in scene['narration_segments'])
        return make_captions([{'start_ms': 0, 'end_ms': duration_ms, 'text': text, 'type': 'segment'}], max_chars)
    if not isinstance(provided, list):
        raise ValueError('external audio captions must be a list')
    events = []
    for caption in provided:
        try:
            start, end = float(caption['start_ms']), float(caption['end_ms'])
            text = caption['text']
        except (KeyError, TypeError, ValueError) as exc:
            raise ValueError('external audio captions need start_ms, end_ms, and text') from exc
        if not math.isfinite(start) or not math.isfinite(end) or start < 0 or end <= start or end > duration_ms + 1e-6:
            raise ValueError(f'external audio caption is outside recording duration ({duration_ms:.3f}ms)')
        if not isinstance(text, str) or not text.strip():
            raise ValueError('external audio caption text must be nonempty')
        events.append({'start_ms': start, 'end_ms': end, 'text': text, 'type': 'segment'})
    return make_captions(events, max_chars)


def _ceil_fraction(value):
    return -(-value.numerator // value.denominator)


def prepare_audio(report: dict, output: Path, report_dir: Path) -> tuple[list, list, dict]:
    errors = validate_report(report)
    if errors:
        raise ValueError('Invalid report:\n' + '\n'.join(errors))
    tools = resolve_tools()
    output, report_dir = Path(output).resolve(), Path(report_dir).resolve()
    output.mkdir(parents=True, exist_ok=True)
    (output / 'audio').mkdir(exist_ok=True)
    cache_root = output / 'cache' / 'audio'
    fps = Fraction(str(report.get('fps', 30)))
    voice = report.get('voice', {})
    if not isinstance(voice, dict):
        raise ValueError('voice must be an object')
    lead = round(report.get('lead_ms', 150) * SAMPLE_RATE / 1000)
    tail = round(report.get('tail_ms', 350) * SAMPLE_RATE / 1000)
    max_chars = report.get('max_caption_chars', 22)
    timeline, captions, scene_manifests, all_audio = [], [], [], []
    cursor = 0
    for index, scene in enumerate(report['scenes']):
        safe_id = re.sub(r'[^A-Za-z0-9_.-]', '_', scene['id'])[:60] or str(index)
        scene_path = output / 'audio' / f'{index + 1:03}-{safe_id}.wav'
        local_captions, cache_entries = [], []
        if scene.get('audio'):
            external = Path(scene['audio']).expanduser()
            source = external if external.is_absolute() else report_dir / external
            if not source.is_file():
                raise RuntimeError(f'External scene audio does not exist: {source}')
            normalized = output / 'audio' / f'{index + 1:03}-{safe_id}-source.wav'
            _normalize_audio(source, normalized, tools)
            pcm = _speech_pcm(normalized)
            local_captions = _external_captions(scene, len(pcm) / 2 / SAMPLE_RATE * 1000, max_chars)
            source_kind = 'external'
        else:
            segments = scene.get('narration_segments') or [{'text': scene['narration']}]
            chunks = []
            offset_samples = 0
            for segment in segments:
                display = segment['text']
                spoken = segment.get('spoken', display)
                cached = _tts_audio(spoken, voice, cache_root, tools)
                data = _speech_pcm(cached['wave'])
                samples = len(data) // 2
                duration_ms = samples * 1000 / SAMPLE_RATE
                if display != spoken:
                    unit_captions = make_captions([{'start_ms': 0, 'end_ms': duration_ms, 'text': display, 'type': 'segment'}], max_chars)
                else:
                    unit_captions = _event_captions(cached['events'], display, duration_ms, max_chars)
                for caption in unit_captions:
                    local_captions.append({**caption, 'start_ms': caption['start_ms'] + offset_samples * 1000 / SAMPLE_RATE,
                                           'end_ms': caption['end_ms'] + offset_samples * 1000 / SAMPLE_RATE})
                chunks.append(data)
                offset_samples += samples
                cache_entries.append({'key': cached['cache_key'], 'hit': cached['cache_hit'], 'text': display,
                                      'spoken': spoken, 'duration_samples': samples})
            pcm = b''.join(chunks)
            source_kind = 'edge-tts'
        scene_data = b'\0\0' * lead + pcm + b'\0\0' * tail
        _write_pcm(scene_path, scene_data)
        count = len(scene_data) // 2
        end = cursor + count
        timeline.append({'id': scene['id'], 'start_ms': cursor * 1000 / SAMPLE_RATE,
                         'end_ms': end * 1000 / SAMPLE_RATE, 'duration_ms': count * 1000 / SAMPLE_RATE,
                         'start_frame': _ceil_fraction(Fraction(cursor, SAMPLE_RATE) * fps),
                         'end_frame': _ceil_fraction(Fraction(end, SAMPLE_RATE) * fps),
                         'start_sample': cursor, 'end_sample': end,
                         'duration_samples': count, 'sample_rate': SAMPLE_RATE})
        for caption in local_captions:
            offset_ms = (cursor + lead) * 1000 / SAMPLE_RATE
            captions.append({**caption, 'scene_id': scene['id'], 'start_ms': caption['start_ms'] + offset_ms,
                             'end_ms': caption['end_ms'] + offset_ms})
        scene_manifests.append({'id': scene['id'], 'provider': source_kind, 'audio': str(scene_path),
                                'duration_samples': count, 'lead_samples': lead, 'tail_samples': tail, 'cache': cache_entries})
        all_audio.append(scene_data)
        cursor = end
    _write_pcm(output / 'voice.wav', b''.join(all_audio))
    manifest = {'schema': CACHE_SCHEMA, 'sample_rate': SAMPLE_RATE, 'channels': 1, 'sample_format': 'pcm_s16le',
                'duration_samples': cursor, 'duration_ms': cursor * 1000 / SAMPLE_RATE,
                'voice': voice, 'provider_version': _provider_version(), 'scenes': scene_manifests}
    _atomic_json(output / 'timeline.json', timeline)
    _atomic_json(output / 'captions.json', captions)
    _atomic_json(output / 'audio-manifest.json', manifest)
    write_srt(captions, output / 'subtitles.srt')
    write_ass(captions, output / 'subtitles.ass', width=report.get('width', 1920), height=report.get('height', 1080),
              font=report.get('font', 'Microsoft YaHei'), font_size=report.get('font_size', 46))
    return timeline, captions, manifest


def _probe(path, tools, count_frames=False):
    command = [tools['ffprobe'], '-v', 'error']
    if count_frames:
        command.append('-count_frames')
    command.extend(['-show_streams', '-show_format', '-of', 'json', path])
    try:
        return json.loads(_run(command, timeout=180).stdout)
    except ValueError as exc:
        raise RuntimeError(f'ffprobe returned invalid JSON for {path}') from exc


def _ffconcat_quote(path):
    return "'" + str(Path(path).resolve()).replace('\\', '/').replace("'", "'\\''") + "'"


def encode_video(output: Path, report: dict, timeline: list, images: list[Path]) -> dict:
    output = Path(output).resolve()
    tools = resolve_tools()
    if not timeline or len(images) != len(timeline):
        raise ValueError('One image is required for every timeline scene')
    for file in ('voice.wav', 'subtitles.ass'):
        if not (output / file).is_file():
            raise RuntimeError(f'Audio preparation must create {file} before encoding')
    width, height, fps = report.get('width', 1920), report.get('height', 1080), report.get('fps', 30)
    fps_string = str(fps)
    cache = output / 'cache' / 'video'
    cache.mkdir(parents=True, exist_ok=True)
    segments = []
    for entry, image in zip(timeline, images):
        image = Path(image).resolve()
        if not image.is_file():
            raise RuntimeError(f'Scene screenshot does not exist: {image}')
        frames = entry['end_frame'] - entry['start_frame']
        if frames <= 0:
            raise ValueError(f'Scene {entry.get("id")} has no complete output frames')
        digest = hashlib.sha256(image.read_bytes()).hexdigest()
        key = cache_key({'schema': CACHE_SCHEMA, 'image': digest, 'frames': frames, 'width': width,
                         'height': height, 'fps': fps, 'codec': 'libx264', 'crf': 18, 'preset': 'veryfast'})
        segment = cache / (key + '.mp4')
        if not segment.is_file() or segment.stat().st_size == 0:
            temporary = cache / (key + '.' + uuid.uuid4().hex + '.tmp.mp4')
            scale = f'scale={width}:{height}:force_original_aspect_ratio=decrease,pad={width}:{height}:(ow-iw)/2:(oh-ih)/2,setsar=1'
            try:
                _run([tools['ffmpeg'], '-hide_banner', '-v', 'error', '-y', '-loop', '1', '-framerate', fps_string,
                      '-i', image, '-an', '-vf', scale, '-r', fps_string, '-frames:v', frames,
                      '-c:v', 'libx264', '-preset', 'veryfast', '-crf', '18', '-pix_fmt', 'yuv420p',
                      '-video_track_timescale', '90000', temporary], timeout=max(180, frames / fps * 6))
                _probe(temporary, tools)
                os.replace(temporary, segment)
            finally:
                temporary.unlink(missing_ok=True)
        segments.append(segment)
    concat = cache / 'segments.ffconcat'
    concat.write_text('ffconcat version 1.0\n' + '\n'.join('file ' + _ffconcat_quote(p) for p in segments) + '\n', encoding='utf-8')
    joined = cache / 'joined.mp4'
    _run([tools['ffmpeg'], '-hide_banner', '-v', 'error', '-y', '-f', 'concat', '-safe', '0', '-i', concat,
          '-an', '-c:v', 'copy', joined], timeout=180)
    frames = timeline[-1]['end_frame']
    duration = frames / fps
    temporary = output / ('video.' + uuid.uuid4().hex + '.tmp.mp4')
    try:
        _run([tools['ffmpeg'], '-hide_banner', '-v', 'error', '-y', '-i', joined, '-i', output / 'voice.wav',
              '-map', '0:v:0', '-map', '1:a:0', '-vf', 'ass=subtitles.ass', '-r', fps_string, '-frames:v', frames,
              '-c:v', 'libx264', '-preset', 'fast', '-crf', '18', '-pix_fmt', 'yuv420p',
              '-c:a', 'aac', '-b:a', '192k', '-ar', SAMPLE_RATE, '-ac', '1',
              '-movflags', '+faststart', temporary], cwd=output, timeout=max(300, duration * 8))
        os.replace(temporary, output / 'video.mp4')
    finally:
        temporary.unlink(missing_ok=True)
    result = {'path': str(output / 'video.mp4'), 'width': width, 'height': height, 'fps': fps,
              'frames': frames, 'duration_seconds': duration, 'video_codec': 'h264', 'audio_codec': 'aac',
              'subtitle_burned': True, 'scenes': len(timeline)}
    _atomic_json(output / 'encoding.json', result)
    return result


def check_media(output: Path) -> dict:
    output = Path(output).resolve()
    tools = resolve_tools()
    video_path = output / 'video.mp4'
    if not video_path.is_file():
        raise RuntimeError(f'Encoded video is missing: {video_path}')
    data = _probe(video_path, tools, count_frames=True)
    videos = [s for s in data['streams'] if s.get('codec_type') == 'video']
    audios = [s for s in data['streams'] if s.get('codec_type') == 'audio']
    errors = []
    if len(videos) != 1 or len(audios) != 1:
        return {'passed': False, 'errors': ['Expected exactly one video and one audio stream'], 'probe': data}
    v, a = videos[0], audios[0]
    fps = float(Fraction(v.get('avg_frame_rate', '0/1')))
    video_frames = int(v.get('nb_read_frames') or v.get('nb_frames') or 0)
    video_seconds = float(v.get('duration', data['format']['duration']))
    audio_seconds = float(a.get('duration', data['format']['duration']))
    expected = {}
    if (output / 'encoding.json').is_file():
        expected = json.loads((output / 'encoding.json').read_text(encoding='utf-8'))
    for actual, desired, label in [(v.get('codec_name'), 'h264', 'video codec'), (a.get('codec_name'), 'aac', 'audio codec'),
                                   (v.get('pix_fmt'), 'yuv420p', 'pixel format')]:
        if actual != desired:
            errors.append(f'Unexpected {label}: {actual}')
    for field in ('width', 'height'):
        if field in expected and v.get(field) != expected[field]:
            errors.append(f'{field} does not match report')
    if expected and abs(fps - expected['fps']) > 0.001:
        errors.append('Video frame rate does not match report')
    if expected and video_frames != expected['frames']:
        errors.append(f'Video has {video_frames} frames; expected {expected["frames"]}')
    nominal_fps = float(Fraction(v.get('r_frame_rate', '0/1')))
    if abs(nominal_fps - fps) > 0.001:
        errors.append('Video is not constant frame rate')
    tolerance = 1 / fps + 0.04 if fps > 0 else 0.08
    if abs(video_seconds - audio_seconds) > tolerance:
        errors.append('Video and audio durations differ by more than the frame/AAC tolerance')
    if int(a.get('sample_rate', 0)) != SAMPLE_RATE or a.get('channels') != 1:
        errors.append('Audio is not 48 kHz mono')
    if (output / 'voice.wav').is_file():
        source_seconds = len(_read_pcm(output / 'voice.wav')) / 2 / SAMPLE_RATE
        if abs(source_seconds - audio_seconds) > tolerance:
            errors.append('Encoded audio duration does not match the prepared voice track')
    decoded = _run([tools['ffmpeg'], '-hide_banner', '-nostats', '-xerror', '-err_detect', 'explode',
                    '-i', video_path, '-af', 'volumedetect', '-f', 'null', '-'], timeout=max(180, video_seconds * 4))
    def volume(name):
        found = re.search(name + r':\s*(-?inf|[-\d.]+)\s*dB', decoded.stderr)
        return float(found.group(1)) if found else None
    mean, peak = volume('mean_volume'), volume('max_volume')
    audible = peak is not None and peak > -60 and mean is not None and mean > -70
    if not audible:
        errors.append('Decoded audio is silent or below the audibility threshold')
    result = {'passed': not errors, 'errors': errors, 'full_decode': True,
              'video': {'codec': v.get('codec_name'), 'width': v['width'], 'height': v['height'],
                        'pixel_format': v.get('pix_fmt'), 'fps': fps, 'frames': video_frames, 'duration_seconds': video_seconds},
              'audio': {'codec': a.get('codec_name'), 'sample_rate': int(a.get('sample_rate', 0)),
                        'channels': a.get('channels'), 'duration_seconds': audio_seconds, 'non_silent': audible,
                        'mean_volume_db': mean if mean is not None and math.isfinite(mean) else None,
                        'peak_volume_db': peak if peak is not None and math.isfinite(peak) else None},
              'manual_listening': 'not_performed', 'manual_visual_review': 'not_performed'}
    _atomic_json(output / 'qa.json', result)
    return result
