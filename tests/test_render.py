import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest import mock

SCRIPTS = Path(__file__).resolve().parents[1] / 'skills/video-report/scripts'
sys.path.insert(0, str(SCRIPTS))


class RenderContractTests(unittest.TestCase):
    def test_template_tokens_inside_report_text_are_not_replaced(self):
        from report_render import write_deck
        report = {'title': '__TIMELINE__ __CAPTIONS__', 'scenes': [
            {'id': 'one', 'kind': 'title', 'title': 'Sample', 'narration': 'Sample.'}]}
        with tempfile.TemporaryDirectory() as tmp:
            path = write_deck(report, Path(tmp), [{'id': 'one', 'start_ms': 0, 'end_ms': 1000}], [])
            self.assertTrue('"__TIMELINE__ __CAPTIONS__"' in path.read_text(encoding='utf-8'),
                            'Literal template tokens inside report text were replaced')

    def test_browser_override_is_respected(self):
        import report_render
        self.assertTrue(hasattr(report_render, 'browser_options'), 'Browser resolution helper is missing')
        with mock.patch.dict('os.environ', {'VIDEO_REPORT_CHROMIUM': 'C:/custom/chrome.exe'}):
            self.assertEqual(report_render.browser_options()['executable_path'], 'C:/custom/chrome.exe')

    def test_deck_keeps_editable_data_and_safe_embedded_text(self):
        self.assertTrue((SCRIPTS / 'report_render.py').exists(), 'Renderer entrypoint is missing')
        from report_render import write_deck
        report = {'title': '研究 </script> 中文', 'scenes': [
            {'id': 'one', 'kind': 'title', 'title': '先看结论', 'narration': '中文旁白。'}]}
        with tempfile.TemporaryDirectory() as tmp:
            path = write_deck(report, Path(tmp), [], [])
            text = path.read_text(encoding='utf-8')
            self.assertIn('renderAt', text)
            self.assertIn('\\u003c/script>', text)
            self.assertNotIn('研究 </script>', text)
            self.assertEqual(json.loads((Path(tmp)/'report.json').read_text(encoding='utf-8')), report)
            self.assertTrue((path.parent/'theme.css').exists())


if __name__ == '__main__':
    unittest.main()
