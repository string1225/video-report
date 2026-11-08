"""Deterministic browser frames streamed to FFmpeg; no wall-clock recording."""
from __future__ import annotations

import hashlib
from contextlib import suppress
import json
import os
from pathlib import Path
import subprocess
import uuid

from report_core import cache_key
from report_render import browser_options


def render_motion(output: Path, report: dict, timeline: list, tools: dict) -> tuple[Path, dict]:
    from playwright.sync_api import sync_playwright
    from report_media import _atomic_json, _probe
    output = Path(output).resolve()
    width, height, fps = report.get('width', 1920), report.get('height', 1080), report.get('fps', 30)
    frames = timeline[-1]['end_frame']
    key = cache_key({'schema': 1, 'renderer': hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
                     'frames': frames, 'width': width, 'height': height, 'fps': fps,
                     'files': {name: hashlib.sha256((output/'deck'/name).read_bytes()).hexdigest()
                               for name in ('index.html', 'theme.css', 'motion-runtime.js')}})
    cache = output/'cache/motion'
    cache.mkdir(parents=True, exist_ok=True)
    target, metadata = cache/(key+'.mp4'), cache/(key+'.json')
    if target.is_file() and metadata.is_file():
        probe = _probe(target, tools)
        if int(probe['streams'][0].get('nb_frames', -1)) == frames:
            qa = json.loads(metadata.read_text(encoding='utf-8'))
            qa['cache_hit'] = True
            _atomic_json(output/'motion-qa.json', qa)
            return target, qa
    temporary = cache/(key+'.'+uuid.uuid4().hex+'.tmp.mp4')
    log = cache/(key+'.stderr.log')
    errors, samples = [], []
    video_frames = 0
    # Test bounds at multiple states, including intermediate movement.
    checkpoints = {min(frames-1, max(0, entry['start_frame']+round((entry['end_frame']-entry['start_frame'])*fraction)))
                   for entry in timeline for fraction in (0.1, 0.5, 0.95)}
    qa = {'mode': 'deterministic_frames', 'frames': frames, 'fps': fps, 'cache_hit': False,
          'clock': 'frame_index / fps; narration sample timeline', 'samples': samples}
    command = [tools['ffmpeg'], '-hide_banner', '-v', 'error', '-y', '-f', 'image2pipe',
               '-vcodec', 'mjpeg', '-framerate', str(fps), '-i', 'pipe:0', '-an', '-frames:v', str(frames),
               '-vf', 'scale=in_range=full:out_range=tv,format=yuv420p', '-color_range', 'tv',
               '-c:v', 'libx264', '-threads', '4', '-preset', 'veryfast', '-crf', '18',
               '-pix_fmt', 'yuv420p', '-video_track_timescale', '90000', str(temporary)]
    process = None
    try:
        with log.open('wb') as stderr, sync_playwright() as p:
            browser = p.chromium.launch(**browser_options())
            try:
                page = browser.new_page(viewport={'width': width, 'height': height}, device_scale_factor=1)
                page.on('pageerror', lambda error: errors.append(str(error)))
                page.on('console', lambda message: errors.append(message.text) if message.type == 'error' else None)
                page.goto((output/'deck/index.html').as_uri()+'?export=1', wait_until='load')
                process = subprocess.Popen(command, stdin=subprocess.PIPE, stdout=subprocess.DEVNULL, stderr=stderr)
                for frame in range(frames):
                    state = page.evaluate('ms => window.renderFrame(ms)', frame*1000/fps)
                    video_frames += bool(state['video_times'])
                    if frame in checkpoints:
                        issues = page.evaluate('window.layoutIssues()')
                        if issues:
                            raise RuntimeError(f'Animated frame {frame} overflows: {issues}')
                        samples.append({'frame': frame, **state})
                    if errors:
                        raise RuntimeError('Animated browser errors: '+'; '.join(errors))
                    process.stdin.write(page.screenshot(type='jpeg', quality=94, animations='disabled'))
                    if frame % max(1, round(fps*10)) == 0:
                        print(f'  Motion frames: {frame}/{frames} ({frame/fps:.1f}s)', flush=True)
                process.stdin.close()
                if process.wait(timeout=180) != 0:
                    raise RuntimeError('Motion encoder failed: '+log.read_text(encoding='utf-8', errors='replace')[-4000:])
            finally:
                browser.close()
        probe = _probe(temporary, tools)
        if int(probe['streams'][0].get('nb_frames', -1)) != frames:
            raise RuntimeError('Motion encoder did not preserve the exact frame count')
        qa.update(video_frames_rendered=video_frames, media_seek_verified=True, page_errors=errors, overflow=False)
        os.replace(temporary, target)
        _atomic_json(metadata, qa)
        _atomic_json(output/'motion-qa.json', qa)
        return target, qa
    except BrokenPipeError as error:
        raise RuntimeError('Motion encoder stopped: '+log.read_text(encoding='utf-8', errors='replace')[-4000:]) from error
    finally:
        if process is not None and process.poll() is None:
            process.kill()
            process.wait(timeout=15)
        if process is not None and process.stdin is not None:
            # Killing FFmpeg can make a buffered Windows pipe flush raise EINVAL.
            # Preserve the original browser/layout/encoding error during cleanup.
            with suppress(OSError):
                process.stdin.close()
        temporary.unlink(missing_ok=True)
