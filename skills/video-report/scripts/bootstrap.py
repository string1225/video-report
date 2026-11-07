"""Create an isolated runtime; optionally install portable Windows media tools."""
from __future__ import annotations

import argparse
import base64
import hashlib
import importlib.util
import io
import json
from pathlib import Path
import shutil
import subprocess
import sys
import tarfile
import time
from urllib.request import urlopen
import venv
import zipfile


def extract_browser_archive(blob: bytes, destination: Path):
    destination = destination.resolve()
    with zipfile.ZipFile(io.BytesIO(blob)) as archive:
        for info in archive.infolist():
            target = (destination/info.filename).resolve()
            if not target.is_relative_to(destination):
                raise ValueError('Browser archive entry points outside its destination')
        if archive.testzip() is not None:
            raise ValueError('Browser archive CRC validation failed')
        archive.extractall(destination)


def install_mirror_browser(workspace: Path, mirror: str):
    if sys.platform != 'win32':
        raise RuntimeError('This portable browser mirror mode supports Windows x64 only.')
    import importlib.metadata
    package = importlib.metadata.distribution('playwright')
    browsers = json.loads(Path(package.locate_file('playwright/driver/package/browsers.json')).read_text(encoding='utf-8'))
    version = next(b['browserVersion'] for b in browsers['browsers'] if b['name'] == 'chromium-headless-shell')
    destination = workspace/'.tools/chromium'
    binary = destination/'chrome-headless-shell-win64/chrome-headless-shell.exe'
    source = destination/'source.json'
    if binary.is_file() and source.is_file() and version in json.loads(source.read_text(encoding='utf-8')).get('url', ''):
        print(f'Reusing portable Chromium {version}: {binary}', flush=True)
        return
    url = mirror.rstrip('/')+f'/{version}/win64/chrome-headless-shell-win64.zip'
    print(f'Downloading Chromium {version} from {url}', flush=True)
    deadline, pieces = time.monotonic()+180, []
    with urlopen(url, timeout=30) as response:
        while chunk := response.read(1024*1024):
            if time.monotonic() > deadline:
                raise RuntimeError('Browser mirror download exceeded 180 seconds')
            pieces.append(chunk)
    blob = b''.join(pieces)
    extract_browser_archive(blob, destination)
    if not binary.is_file():
        raise RuntimeError('Downloaded archive did not contain the expected Chromium executable')
    source.write_text(json.dumps({'url': url, 'browser_version': version, 'bytes': len(blob),
                                 'sha256': hashlib.sha256(blob).hexdigest()}, indent=2), encoding='utf-8')


def install_portable_tools(workspace: Path):
    destination = workspace / '.tools' / 'bin'
    destination.mkdir(parents=True, exist_ok=True)
    if sys.platform != 'win32':
        raise RuntimeError('Portable tool installation currently supports Windows. Install ffmpeg/ffprobe with your system package manager, or set VIDEO_REPORT_FFMPEG and VIDEO_REPORT_FFPROBE.')
    import imageio_ffmpeg
    target = destination / 'ffmpeg.exe'
    shutil.copy2(imageio_ffmpeg.get_ffmpeg_exe(), target)
    probe = destination / 'ffprobe.exe'
    if not probe.exists():
        registry = 'https://registry.npmjs.org/@ffprobe-installer/win32-x64/5.1.0'
        with urlopen(registry, timeout=30) as response:
            meta = json.load(response)
        distribution = meta['dist']
        with urlopen(distribution['tarball'], timeout=120) as response:
            blob = response.read()
        actual = base64.b64encode(hashlib.sha512(blob).digest()).decode()
        if distribution['integrity'] != 'sha512-' + actual:
            raise RuntimeError('ffprobe package SHA-512 mismatch')
        with tarfile.open(fileobj=io.BytesIO(blob), mode='r:gz') as archive:
            member = next(m for m in archive.getmembers() if m.name == 'package/ffprobe.exe')
            file = archive.extractfile(member)
            if file is None:
                raise RuntimeError('ffprobe executable missing from distribution')
            temporary = probe.with_suffix('.download')
            temporary.write_bytes(file.read())
            temporary.replace(probe)
        (destination / 'ffprobe-source.json').write_text(json.dumps({
            'package': meta['name'], 'version': meta['version'],
            'url': distribution['tarball'], 'integrity': distribution['integrity']}, indent=2), encoding='utf-8')
    print(f'Portable tools: {destination}', flush=True)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--workspace', type=Path, default=Path.cwd())
    parser.add_argument('--portable-tools', action='store_true', help='Download/copy verified Windows ffmpeg and ffprobe into the workspace .tools/bin')
    parser.add_argument('--skip-browser', action='store_true', help='Reuse an already installed Chromium')
    parser.add_argument('--browser-mirror', help='Optional Chrome-for-Testing mirror base URL for portable Windows x64 Chromium')
    parser.add_argument('--tools-only', action='store_true', help=argparse.SUPPRESS)
    parser.add_argument('--browser-only', action='store_true', help=argparse.SUPPRESS)
    args = parser.parse_args()
    workspace = args.workspace.resolve()
    workspace.mkdir(parents=True, exist_ok=True)
    if args.tools_only:
        install_portable_tools(workspace)
        return
    if args.browser_only:
        install_mirror_browser(workspace, args.browser_mirror)
        return
    directory = workspace / '.venv'
    interpreter = directory / ('Scripts/python.exe' if sys.platform == 'win32' else 'bin/python')
    if not interpreter.exists():
        venv.EnvBuilder(with_pip=True).create(directory)
    lock = Path(__file__).with_name('requirements.lock')
    subprocess.run([str(interpreter), '-m', 'pip', 'install', '--disable-pip-version-check', '-r', str(lock)], check=True)
    if not args.skip_browser:
        if args.browser_mirror:
            subprocess.run([str(interpreter), str(Path(__file__).resolve()), '--workspace', str(workspace),
                            '--browser-only', '--browser-mirror', args.browser_mirror], check=True)
        else:
            subprocess.run([str(interpreter), '-m', 'playwright', 'install', 'chromium', '--only-shell'], check=True)
    if args.portable_tools:
        subprocess.run([str(interpreter), str(Path(__file__).resolve()), '--workspace', str(workspace), '--tools-only'], check=True)
    print(f'Runtime ready: {interpreter}', flush=True)


if __name__ == '__main__':
    if hasattr(sys.stdout, 'reconfigure'):
        sys.stdout.reconfigure(encoding='utf-8')
    main()
