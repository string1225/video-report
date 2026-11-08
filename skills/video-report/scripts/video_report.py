"""Turn a source-backed report into editable HTML, narration, subtitles and MP4."""
from __future__ import annotations

import argparse
import importlib.metadata
import json
from pathlib import Path
import sys
import time

from report_core import cache_key, validate_report


def read_json(path):
    return json.loads(Path(path).read_text(encoding='utf-8-sig'))


def save_json(path, value):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix+'.tmp')
    temporary.write_text(json.dumps(value, ensure_ascii=False, indent=2, allow_nan=False), encoding='utf-8')
    temporary.replace(path)


def audio_input_key(report, report_dir):
    payload = {key: report.get(key) for key in ['voice', 'lead_ms', 'tail_ms', 'fps', 'max_caption_chars']}
    payload['scenes'] = []
    for scene in report['scenes']:
        entry = {key: scene.get(key) for key in ['id', 'narration', 'narration_segments', 'audio', 'captions']}
        if scene.get('audio'):
            path = Path(scene['audio'])
            if not path.is_absolute():
                path = report_dir / path
            if not path.exists():
                raise ValueError(f'External audio does not exist: {path}')
            import hashlib
            entry['file_sha256'] = hashlib.sha256(path.read_bytes()).hexdigest()
        payload['scenes'].append(entry)
    return cache_key(payload)


def load_report(path):
    report = read_json(path)
    errors = validate_report(report)
    if errors:
        raise ValueError('Invalid report:\n'+'\n'.join(errors))
    return report


def check_output(output):
    from report_media import check_media
    qa = check_media(output)
    timeline, captions = read_json(output/'timeline.json'), read_json(output/'captions.json')
    last_end = 0
    for cue in captions:
        if cue['start_ms'] < 0 or cue['end_ms'] <= cue['start_ms'] or cue['end_ms'] > timeline[-1]['end_ms']+1:
            qa['errors'].append('Caption lies outside the prepared audio')
        if cue['start_ms'] < last_end-1:
            qa['errors'].append('Unexpected overlapping captions')
        if max(map(len, cue['text'].splitlines()), default=0) > 44:
            qa['errors'].append('Caption line exceeds 44 characters; simplify the complete sentence or adjust subtitle layout')
        if len(cue['text'].splitlines()) > 2:
            qa['errors'].append('Caption exceeds two lines')
        last_end = cue['end_ms']
    qa['captions'] = {'count': len(captions), 'timing_types': sorted({c['timing'] for c in captions})}
    if (output/'render-qa.json').exists():
        qa['presentation'] = read_json(output/'render-qa.json')
    encoding = read_json(output/'encoding.json') if (output/'encoding.json').exists() else {}
    if encoding.get('render_mode') == 'deterministic_frames':
        if not (output/'motion-qa.json').exists():
            qa['errors'].append('Current animated video is missing motion QA')
        else:
            qa['motion'] = read_json(output/'motion-qa.json')
            if qa['motion'].get('frames') != encoding.get('frames'):
                qa['errors'].append('Motion QA frame count does not match the current video')
    if (output/'human-review.json').exists():
        qa['human_review'] = read_json(output/'human-review.json')
    qa['passed'] = not qa['errors']
    save_json(output/'qa.json', qa)
    return qa


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest='command', required=True)
    init = sub.add_parser('init', help='Copy a runnable example report')
    init.add_argument('path', type=Path)
    for name in ['validate', 'tts', 'render', 'build']:
        command = sub.add_parser(name, help={'validate':'Validate report and source references', 'tts':'Prepare resumable audio and timeline', 'render':'Generate editable HTML and slide screenshots', 'build':'Run the complete pipeline'}[name])
        command.add_argument('report', type=Path)
        if name != 'validate':
            command.add_argument('--output', type=Path, required=True)
    check = sub.add_parser('check', help='Decode and validate an existing build')
    check.add_argument('output', type=Path)
    args = parser.parse_args(argv)
    if args.command == 'init':
        import shutil
        if args.path.exists():
            raise ValueError(f'Refusing to overwrite existing file: {args.path}')
        args.path.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(Path(__file__).resolve().parents[1]/'assets/demo-report.json', args.path)
        print(args.path.resolve())
        return 0
    if args.command == 'check':
        qa = check_output(args.output.resolve())
        print(json.dumps(qa, ensure_ascii=False, indent=2))
        return 0 if qa['passed'] else 1
    report_path = args.report.resolve()
    report = load_report(report_path)
    if args.command == 'validate':
        print(f'Valid: {len(report["scenes"])} scenes, {len(report.get("sources", []))} sources')
        return 0
    output = args.output.resolve()
    output.mkdir(parents=True, exist_ok=True)
    manifest = {'schema': 1, 'report_path': str(report_path), 'report_hash': cache_key(report),
                'python': sys.version.split()[0], 'stages': {}}
    if (output/'manifest.json').exists():
        old = read_json(output/'manifest.json')
        manifest['stages'] = old.get('stages', {})
    started = time.monotonic()
    stage_seconds = {}
    current = 'audio'
    try:
        key = audio_input_key(report, report_path.parent)
        if args.command in ('tts', 'build'):
            from report_media import prepare_audio
            print('Preparing narration and sample-based timeline...', flush=True)
            stage_started = time.monotonic()
            timeline, captions, audio_manifest = prepare_audio(report, output, report_path.parent)
            stage_seconds['audio'] = time.monotonic()-stage_started
            audio_manifest['input_key'] = key
            save_json(output/'audio-manifest.json', audio_manifest)
            manifest['stages']['audio'] = {'status': 'passed', 'input_key': key, 'duration_ms': timeline[-1]['end_ms'],
                                         'elapsed_seconds': round(stage_seconds['audio'], 2)}
            save_json(output/'manifest.json', manifest)
        else:
            audio_manifest = read_json(output/'audio-manifest.json')
            if audio_manifest.get('input_key') != key:
                raise ValueError('Narration input changed: run tts or build before render')
            timeline, captions = read_json(output/'timeline.json'), read_json(output/'captions.json')
        if args.command == 'tts':
            print(f'Audio ready: {timeline[-1]["end_ms"]/1000:.2f}s', flush=True)
            return 0
        current = 'render'
        from report_render import write_deck, capture_slides
        stage_started = time.monotonic()
        write_deck(report, output, timeline, captions, report_dir=report_path.parent)
        print('Rendering editable HTML and checking every slide...', flush=True)
        images, render_qa = capture_slides(report, output)
        stage_seconds['render'] = time.monotonic()-stage_started
        manifest['stages']['render'] = {'status': 'passed', **render_qa,
                                      'elapsed_seconds': round(stage_seconds['render'], 2)}
        save_json(output/'manifest.json', manifest)
        if args.command == 'render':
            print(output/'deck/index.html')
            return 0
        current = 'encode'
        from report_media import encode_video
        print('Encoding H.264 video with narration and burned captions...', flush=True)
        stage_started = time.monotonic()
        manifest['stages']['encode'] = {'status': 'passed', **encode_video(output, report, timeline, images)}
        stage_seconds['encode'] = time.monotonic()-stage_started
        manifest['stages']['encode']['elapsed_seconds'] = round(stage_seconds['encode'], 2)
        save_json(output/'manifest.json', manifest)
        current = 'check'
        print('Decoding the full video and validating media/subtitles...', flush=True)
        stage_started = time.monotonic()
        qa = check_output(output)
        stage_seconds['check'] = time.monotonic()-stage_started
        manifest['stages']['check'] = {'status': 'passed' if qa['passed'] else 'failed', 'errors': qa['errors'],
                                     'elapsed_seconds': round(stage_seconds['check'], 2)}
        manifest['elapsed_seconds'] = round(time.monotonic()-started, 2)
        from report_costs import summarize_run_costs
        costs = summarize_run_costs(audio_manifest, manifest['elapsed_seconds'], stage_seconds,
                                    (output/'video.mp4').stat().st_size)
        save_json(output/'costs.json', costs)
        manifest['costs_file'] = 'costs.json'
        save_json(output/'manifest.json', manifest)
        if not qa['passed']:
            raise RuntimeError('Media QA failed: '+'; '.join(qa['errors']))
        print(f'Complete: {output/"video.mp4"} ({qa["video"]["duration_seconds"]:.2f}s)', flush=True)
        return 0
    except Exception as e:
        manifest['stages'][current] = {'status': 'failed', 'error': str(e)}
        save_json(output/'manifest.json', manifest)
        raise


if __name__ == '__main__':
    for stream in [sys.stdout, sys.stderr]:
        if hasattr(stream, 'reconfigure'):
            stream.reconfigure(encoding='utf-8')
    try:
        raise SystemExit(main())
    except (ValueError, RuntimeError, OSError, KeyError) as error:
        print(str(error), file=sys.stderr)
        raise SystemExit(1)
