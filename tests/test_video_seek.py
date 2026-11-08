import functools
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
import re
import sys
import tempfile
import threading
import unittest
import wave

sys.path.insert(0, str(Path(__file__).resolve().parents[1]/'skills/video-report/scripts'))
from report_render import browser_options, write_deck
from report_media import _run, resolve_tools


class QuietHandler(SimpleHTTPRequestHandler):
    def log_message(self, *args):
        pass

    def do_GET(self):
        path = Path(self.translate_path(self.path))
        if not path.is_file():
            return super().do_GET()
        data = path.read_bytes()
        start, end = 0, len(data)-1
        requested = re.fullmatch(r'bytes=(\d+)-(\d*)', self.headers.get('Range', ''))
        if requested:
            start = int(requested[1])
            end = min(end, int(requested[2])) if requested[2] else end
        self.send_response(206 if requested else 200)
        self.send_header('Content-Type', self.guess_type(str(path)))
        self.send_header('Accept-Ranges', 'bytes')
        self.send_header('Content-Length', str(end-start+1))
        if requested:
            self.send_header('Content-Range', f'bytes {start}-{end}/{len(data)}')
        self.end_headers()
        self.wfile.write(data[start:end+1])


class VideoSeekTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        from playwright.sync_api import sync_playwright
        cls.temp = tempfile.TemporaryDirectory()
        cls.root = Path(cls.temp.name)
        cls.clip = cls.root/'clip.webm'
        _run([resolve_tools()['ffmpeg'], '-v', 'error', '-y', '-f', 'lavfi', '-i',
              'testsrc2=size=320x180:rate=10:duration=2', '-an', '-c:v', 'libvpx-vp9', cls.clip])
        from PIL import Image
        Image.new('RGB', (320, 180), '#456234').save(cls.root/'still.png')
        cls.runtime = sync_playwright().start()
        cls.browser = cls.runtime.chromium.launch(**browser_options())

    @classmethod
    def tearDownClass(cls):
        cls.browser.close()
        cls.runtime.stop()
        cls.temp.cleanup()

    def report(self):
        return {'title': 'Seek', 'fps': 10, 'motion': {'enabled': True},
                'media': [{'id': 'clip', 'type': 'video', 'path': str(self.clip)},
                          {'id': 'still', 'type': 'image', 'path': str(self.root/'still.png')}],
                'scenes': [{'id': 'one', 'kind': 'cards', 'title': 'Seek', 'narration': 'Seek.',
                            'media': {'id': 'clip'}, 'columns': [{'title': 'Action'}]}]}

    def test_switch_into_late_video_starts_at_switch_and_can_loop_or_seek_back(self):
        with tempfile.TemporaryDirectory() as tmp:
            report = self.report()
            report['scenes'][0]['media'] = {'id': 'still', 'switches': [{'id': 'clip', 'cue': 1, 'loop': True}]}
            path = write_deck(report, Path(tmp), [{'start_ms': 0, 'end_ms': 12000}],
                              [{'start_ms': 100, 'end_ms': 2000}, {'start_ms': 7000, 'end_ms': 11000}])
            page = self.browser.new_page()
            try:
                page.goto(path.as_uri()+'?export=1')
                for ms in (7500, 9500):
                    state = page.evaluate('ms=>window.renderFrame(ms)', ms)
                    self.assertAlmostEqual(state['video_times'][0], .5, places=3)
                page.evaluate('()=>window.renderFrame(1000)')
                self.assertEqual(page.locator('video').count(), 0)
                state = page.evaluate('()=>window.renderFrame(7500)')
                self.assertAlmostEqual(state['video_times'][0], .5, places=3)
            finally:
                page.close()

    def test_paused_seek_is_synchronized_after_delayed_video_load(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            report = self.report()
            report['scenes'].insert(0, {'id': 'start', 'kind': 'title', 'title': 'Start', 'narration': 'Start.'})
            write_deck(report, root, [{'start_ms': 0, 'end_ms': 2000}, {'start_ms': 2000, 'end_ms': 8000}], [])
            with wave.open(str(root/'voice.wav'), 'wb') as audio:
                audio.setparams((1, 2, 48000, 0, 'NONE', 'not compressed'))
                audio.writeframes(b'\0\x10'*48000*8)
            server = ThreadingHTTPServer(('127.0.0.1', 0), functools.partial(QuietHandler, directory=str(root)))
            thread = threading.Thread(target=server.serve_forever, daemon=True)
            thread.start()
            page = self.browser.new_page()
            pending = []
            page.route('**/*.webm', lambda route: pending.append(route), times=1)
            try:
                page.goto(f'http://127.0.0.1:{server.server_port}/deck/index.html')
                page.wait_for_function('document.querySelector("audio").readyState>=1')
                page.evaluate('() => { audio.currentTime=3.5; window.renderAt(3500); }')
                page.wait_for_timeout(200)
                self.assertTrue(pending)
                self.assertEqual(page.locator('video').evaluate('v=>v.readyState'), 0)
                pending[0].continue_()
                page.wait_for_function('document.querySelector("video").readyState>=2')
                page.wait_for_function('Math.abs(document.querySelector("video").currentTime-1.5)<.02', timeout=5000)
                state = page.evaluate('() => ({audio:audio.currentTime, video:document.querySelector("video").currentTime, scene:window.currentScene, error:window.mediaPlaybackError})')
                self.assertAlmostEqual(state['video'], 1.5, places=2, msg=str(state))
                self.assertTrue(page.locator('audio').evaluate('a=>a.paused'))
            finally:
                page.close()
                server.shutdown()
                server.server_close()
                thread.join(timeout=2)


if __name__ == '__main__':
    unittest.main()
