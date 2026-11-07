from pathlib import Path
import sys
import tempfile
import unittest
import wave

sys.path.insert(0, str(Path(__file__).resolve().parents[1]/'skills/video-report/scripts'))
from report_render import browser_options, capture_slides, write_deck


class BrowserRegressionTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        try:
            from playwright.sync_api import sync_playwright
        except ImportError:
            raise unittest.SkipTest('Playwright is not installed')
        cls.runtime = sync_playwright().start()
        cls.browser = cls.runtime.chromium.launch(**browser_options())

    @classmethod
    def tearDownClass(cls):
        cls.browser.close()
        cls.runtime.stop()

    def check_scene(self, scene):
        report = {'title': 'Regression', 'scenes': [dict(
            id='one', kind='evidence', title='Research', narration='Text.', **scene)]}
        with tempfile.TemporaryDirectory() as tmp:
            path = write_deck(report, Path(tmp), [], [])
            page = self.browser.new_page(viewport={'width': 1920, 'height': 1080})
            try:
                page.goto(path.as_uri()+'?export=1')
                page.evaluate('document.fonts.ready')
                return page.evaluate('window.layoutIssues()')
            finally:
                page.close()

    def test_bar_text_overflow_is_reported(self):
        issues = self.check_scene({'bars': [{'label': 'Result', 'value': 0.5,
                                          'display': '123,456,789 / 1,000,000'}]})
        self.assertTrue(issues, 'Text overflowing its grid cell was not detected')

    def test_footer_text_overflow_is_reported(self):
        self.assertTrue(self.check_scene({'footer': '文献来源说明' * 300}),
                        'Footer overflowing into the subtitle area was not detected')

class PlaybackRegressionTests(unittest.TestCase):
    def test_capture_records_measured_seek_and_pause(self):
        report = {'title': 'Player', 'width': 960, 'height': 540, 'scenes': [
            {'id': str(i), 'kind': 'cards', 'title': f'Scene {i}', 'narration': 'Text.',
             'bullets': ['A simple playback check']} for i in range(2)]}
        timeline = [{'start_ms': 0, 'end_ms': 1000}, {'start_ms': 1000, 'end_ms': 2000}]
        with tempfile.TemporaryDirectory() as tmp:
            output = Path(tmp)
            with wave.open(str(output/'voice.wav'), 'wb') as audio:
                audio.setparams((1, 2, 48000, 0, 'NONE', 'not compressed'))
                audio.writeframes(b'\x00\x10' * 96000)
            write_deck(report, output, timeline, [])
            _, qa = capture_slides(report, output)
            self.assertIsInstance(qa['seek'], dict, 'Seek must include actual measured state')
            self.assertTrue(qa.get('pause_confirmed'), 'Paused state must be checked')


if __name__ == '__main__':
    unittest.main()
