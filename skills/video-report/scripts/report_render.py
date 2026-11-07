"""Editable local HTML and deterministic 1080p slide export."""
from __future__ import annotations

import json
import os
from pathlib import Path
import re
import shutil


ASSETS = Path(__file__).resolve().parents[1] / 'assets'


def browser_options():
    options = {'headless': True}
    if os.environ.get('VIDEO_REPORT_CHROMIUM'):
        options['executable_path'] = os.environ['VIDEO_REPORT_CHROMIUM']
    else:
        for root in [Path.cwd(), *Path.cwd().parents, *Path(__file__).resolve().parents]:
            portable = root/'.tools/chromium/chrome-headless-shell-win64/chrome-headless-shell.exe'
            if portable.is_file():
                options['executable_path'] = str(portable)
                break
    return options


def _json_script(value):
    return json.dumps(value, ensure_ascii=False).replace('<', '\\u003c').replace('\u2028', '\\u2028').replace('\u2029', '\\u2029')


def write_deck(report: dict, output: Path, timeline=None, captions=None) -> Path:
    output = Path(output)
    deck = output / 'deck'
    deck.mkdir(parents=True, exist_ok=True)
    template = (ASSETS / 'deck-template.html').read_text(encoding='utf-8')
    values = {'REPORT': _json_script(report), 'TIMELINE': _json_script(timeline or []),
              'CAPTIONS': _json_script(captions or [])}
    template = re.sub(r'__(REPORT|TIMELINE|CAPTIONS)__', lambda match: values[match[1]], template)
    (deck / 'index.html').write_text(template, encoding='utf-8')
    shutil.copy2(ASSETS / 'theme.css', deck / 'theme.css')
    (output / 'report.json').write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding='utf-8')
    (output / 'sources.json').write_text(json.dumps(report.get('sources', []), ensure_ascii=False, indent=2), encoding='utf-8')
    lines = [f"# {report['title']}", '']
    for i, scene in enumerate(report['scenes'], 1):
        lines.extend([f"## {i}. {scene['title']}", '',
                      scene.get('narration') or '\n'.join(x['text'] for x in scene.get('narration_segments', [])), '',
                      '来源：' + ', '.join(scene.get('source_ids', [])), ''])
    (output / 'storyboard.md').write_text('\n'.join(lines), encoding='utf-8')
    return deck / 'index.html'


def capture_slides(report: dict, output: Path) -> tuple[list[Path], dict]:
    from playwright.sync_api import sync_playwright
    output = Path(output).resolve()
    frames = output / 'frames'
    frames.mkdir(parents=True, exist_ok=True)
    errors = []
    images = []
    width, height = report.get('width', 1920), report.get('height', 1080)
    with sync_playwright() as p:
        browser = p.chromium.launch(**browser_options())
        try:
            page = browser.new_page(viewport={'width': width, 'height': height}, device_scale_factor=1)
            page.on('pageerror', lambda e: errors.append(str(e)))
            page.on('console', lambda m: errors.append(m.text) if m.type == 'error' else None)
            page.goto((output/'deck/index.html').as_uri()+'?export=1', wait_until='load')
            page.evaluate('document.fonts.ready')
            if not page.title() or page.locator('#stage').count() != 1:
                raise RuntimeError('Presentation did not initialize')
            for i, scene in enumerate(report['scenes']):
                page.evaluate('(index) => window.showScene(index)', i)
                page.evaluate("async () => { await document.fonts.ready; await Promise.all([...document.images].map(i => i.decode())); }")
                issues = page.evaluate('window.layoutIssues()')
                if issues:
                    raise RuntimeError(f"Scene {scene['id']} overflows: {issues}")
                safe_id = re.sub(r'[^A-Za-z0-9_-]', '_', scene['id'])[:60]
                path = frames / f'{i+1:03d}-{safe_id}.png'
                page.screenshot(path=str(path), animations='disabled')
                images.append(path)
            # Exercise actual navigation and timeline seek in the editable preview.
            page.goto((output/'deck/index.html').as_uri(), wait_until='load')
            page.locator('#next').click()
            expected = min(1, len(report['scenes'])-1)
            if page.evaluate('window.currentScene') != expected:
                raise RuntimeError('Next-slide control did not navigate')
            page.locator('#previous').click()
            if page.evaluate('window.currentScene') != 0:
                raise RuntimeError('Previous-slide control did not navigate')
            page.locator('#seek').evaluate("el => { el.value = '800'; el.dispatchEvent(new Event('input', {bubbles:true})); }")
            seek = page.evaluate("""() => {
                const target=timeline.length?timeline.at(-1).end_ms*0.8:audio.duration*800;
                return {target_ms:target, audio_ms:audio.currentTime*1000, actual_scene:window.currentScene,
                        expected_scene:timeline.findIndex(s=>target>=s.start_ms&&target<s.end_ms)};
            }""")
            if abs(seek['audio_ms']-seek['target_ms']) > 100 or seek['actual_scene'] != seek['expected_scene']:
                raise RuntimeError(f'Preview seek did not synchronize audio and scene: {seek}')
            page.locator('#seek').press('Home')
            if page.evaluate('window.currentScene') != 0:
                raise RuntimeError('Seeking to the start did not restore the first scene')
            page.locator('#play').click()
            page.wait_for_function('!document.querySelector("audio").paused')
            playing = page.evaluate('!document.querySelector("audio").paused')
            page.locator('#play').click()
            page.wait_for_function('document.querySelector("audio").paused')
            paused = page.evaluate('document.querySelector("audio").paused')
            if (output/'voice.wav').exists() and not playing:
                raise RuntimeError('Preview audio play control did not start audio')
            if errors:
                raise RuntimeError('Browser errors: '+'; '.join(errors))
        finally:
            browser.close()
    make_contact_sheet(images, output)
    qa = {'browser': 'Playwright Chromium', 'browser_plugin': 'Browser plugin not available',
          'viewport': [width, height], 'scene_count': len(images), 'page_errors': errors,
          'overflow': False, 'navigation': 'passed', 'play_pause': 'passed', 'pause_confirmed': paused, 'seek': seek}
    (output/'render-qa.json').write_text(json.dumps(qa, ensure_ascii=False, indent=2), encoding='utf-8')
    return images, qa


def make_contact_sheet(images, output):
    from PIL import Image, ImageDraw
    thumb_w, thumb_h, gap = 640, 360, 24
    cols = 3
    rows = (len(images)+cols-1)//cols
    sheet = Image.new('RGB', (cols*thumb_w+(cols+1)*gap, rows*(thumb_h+30)+(rows+1)*gap), '#ddd9d0')
    draw = ImageDraw.Draw(sheet)
    for i, path in enumerate(images):
        with Image.open(path) as frame:
            thumb = frame.convert('RGB').resize((thumb_w, thumb_h))
        x, y = gap+(i%cols)*(thumb_w+gap), gap+(i//cols)*(thumb_h+30+gap)
        sheet.paste(thumb, (x, y))
        draw.text((x, y+thumb_h+5), f'{i+1:02d}', fill='#243b34')
    sheet.save(Path(output)/'contact-sheet.png')
    shutil.copy2(images[0], Path(output)/'poster.png')
