"""Check the runtime and actual rendering/encoding capabilities."""
from __future__ import annotations
import argparse
import importlib.metadata
import json
import os
from pathlib import Path
import platform
import subprocess
import sys


def diagnose():
    from report_media import resolve_tools
    checks, errors = {}, []
    checks['python'] = sys.version.split()[0]
    checks['platform'] = platform.platform()
    for name in ['edge-tts', 'playwright', 'pillow', 'imageio-ffmpeg']:
        try:
            checks[name] = importlib.metadata.version(name)
        except importlib.metadata.PackageNotFoundError:
            errors.append(f'Missing Python package: {name}')
    try:
        media = resolve_tools()
        checks['tools'] = media
        for name, path in media.items():
            result = subprocess.run([str(path), '-version'], capture_output=True, text=True, encoding='utf-8', errors='replace', timeout=20, check=True)
            checks[name+'_version'] = result.stdout.splitlines()[0]
        encoders = subprocess.run([str(media['ffmpeg']), '-hide_banner', '-encoders'], capture_output=True, text=True, encoding='utf-8', errors='replace', timeout=20, check=True).stdout
        filters = subprocess.run([str(media['ffmpeg']), '-hide_banner', '-filters'], capture_output=True, text=True, encoding='utf-8', errors='replace', timeout=20, check=True).stdout
        for feature, available in [('libx264', 'libx264' in encoders), ('aac', ' aac ' in encoders), ('subtitles/libass', 'subtitles' in filters), ('loudnorm', 'loudnorm' in filters)]:
            checks[feature] = available
            if not available:
                errors.append('FFmpeg capability missing: '+feature)
    except Exception as e:
        errors.append(str(e))
    try:
        from playwright.sync_api import sync_playwright
        from report_render import browser_options
        with sync_playwright() as p:
            browser = p.chromium.launch(**browser_options())
            try:
                page = browser.new_page(viewport={'width': 640, 'height': 360})
                page.set_content('<div style="font:32px Microsoft YaHei,sans-serif">中文字体检查 2026</div>')
                page.evaluate('document.fonts.ready')
                checks['chromium'] = browser.version
                checks['font'] = 'Microsoft YaHei' if sys.platform == 'win32' else 'system CJK font (visually verify)'
                checks['chinese_font_layout'] = page.locator('div').bounding_box()
            finally:
                browser.close()
    except Exception as e:
        errors.append('Chromium rendering: '+str(e))
    return {'ok': not errors, 'checks': checks, 'errors': errors,
            'note': 'Font layout check does not replace visual inspection of rendered Chinese glyphs.'}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path)
    args = parser.parse_args()
    result = diagnose()
    text = json.dumps(result, ensure_ascii=False, indent=2)
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(text, encoding='utf-8')
    print(text)
    return 0 if result['ok'] else 1


if __name__ == '__main__':
    if hasattr(sys.stdout, 'reconfigure'):
        sys.stdout.reconfigure(encoding='utf-8')
    raise SystemExit(main())
