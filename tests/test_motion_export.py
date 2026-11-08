import json
import math
from pathlib import Path
import struct
import sys
import tempfile
import unittest
import wave

sys.path.insert(0, str(Path(__file__).resolve().parents[1]/'skills/video-report/scripts'))
import report_media as media
from report_render import write_deck


class MotionExportTests(unittest.TestCase):
    def test_real_clip_changes_in_browser_and_encoded_frames(self):
        from playwright.sync_api import sync_playwright
        from report_render import browser_options
        tools = media.resolve_tools()
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            clip = root/'clip.webm'
            media._run([tools['ffmpeg'], '-v', 'error', '-y', '-f', 'lavfi', '-i',
                        'testsrc2=size=320x180:rate=10:duration=2', '-an', '-c:v', 'libvpx-vp9', clip])
            report = {'title': 'Real motion', 'width': 640, 'height': 360, 'fps': 10,
                      'motion': {'enabled': True}, 'media': [{'id': 'clip', 'path': str(clip), 'type': 'video',
                          'title': 'Test pattern', 'creator': 'FFmpeg', 'license': 'test fixture',
                          'source_url': 'generated:testsrc2', 'attribution': 'Locally generated test pattern'}],
                      'scenes': [{'id': 'one', 'kind': 'cards', 'title': 'Motion', 'narration': 'Motion.',
                                  'columns': [{'title': 'Steps', 'text': 'An actual moving source.'}],
                                  'media': {'id': 'clip'}}]}
            output = root/'output'
            output.mkdir()
            with wave.open(str(output/'voice.wav'), 'wb') as stream:
                stream.setparams((1, 2, 48000, 0, 'NONE', 'not compressed'))
                stream.writeframes(b''.join(struct.pack('<h', int(8000*math.sin(i*.05))) for i in range(96000)))
            (output/'subtitles.ass').write_text('[Script Info]\nScriptType: v4.00+\nPlayResX: 640\nPlayResY: 360\n[V4+ Styles]\n[Events]\n', encoding='utf-8')
            timeline = [{'id': 'one', 'start_ms': 0, 'end_ms': 2000, 'start_frame': 0, 'end_frame': 20}]
            path = write_deck(report, output, timeline, [])
            with sync_playwright() as p:
                browser = p.chromium.launch(**browser_options())
                page = browser.new_page(viewport={'width': 640, 'height': 360})
                try:
                    page.goto(path.as_uri()+'?export=1')
                    def source_pixel(ms):
                        state = page.evaluate('ms => window.renderFrame(ms)', ms)
                        self.assertAlmostEqual(state['video_times'][0], ms/1000, places=3)
                        return page.locator('video').screenshot()
                    first = source_pixel(600)
                    second = source_pixel(1400)
                    self.assertNotEqual(first, second, 'Seeking must decode different actual source frames')
                    self.assertEqual(first, source_pixel(600), 'Video seeking back must be deterministic')
                finally:
                    browser.close()
            encoded = media.encode_video(output, report, timeline, [clip])
            self.assertEqual(encoded.get('render_mode'), 'deterministic_frames')
            self.assertEqual(encoded['frames'], 20)
            frames = []
            for timestamp in ('0.6', '1.4'):
                result = media._run([tools['ffmpeg'], '-v', 'error', '-ss', timestamp, '-i', output/'video.mp4',
                                     '-frames:v', '1', '-f', 'framemd5', '-'])
                frames.append(result.stdout.strip().splitlines()[-1].split(',')[-1])
            self.assertNotEqual(*frames, 'MP4 must contain motion, not a held scene screenshot')
            qa = media.check_media(output)
            self.assertTrue(qa['passed'], qa)
            motion_qa = json.loads((output/'motion-qa.json').read_text(encoding='utf-8'))
            self.assertEqual(motion_qa['frames'], 20)
            self.assertTrue(motion_qa['media_seek_verified'])


if __name__ == '__main__':
    unittest.main()
