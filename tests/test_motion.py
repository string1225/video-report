from pathlib import Path
import hashlib
import json
import sys
import tempfile
import unittest
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parents[1]/'skills/video-report/scripts'))
from report_core import validate_report
from report_render import browser_options, write_deck


def sample_report():
    return {'title': 'Motion', 'motion': {'enabled': True}, 'scenes': [
        {'id': 'one', 'kind': 'cards', 'title': 'Measured', 'narration': 'First. Second.',
         'columns': [{'title': 'First'}, {'title': 'Second'}], 'reveal_cues': [0, 1]}]}


class MediaAssetTests(unittest.TestCase):
    def test_removed_media_does_not_remain_without_credits(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root/'one.png').write_bytes(b'one')
            (root/'two.png').write_bytes(b'two')
            report = sample_report()
            report['media'] = [{'id': name, 'path': name+'.png', 'type': 'image'} for name in ('one', 'two')]
            path = write_deck(report, root/'out', [], [], report_dir=root)
            custom = path.parent/'media/user-kept.txt'
            custom.write_text('user content', encoding='utf-8')
            report['media'].pop()
            write_deck(report, root/'out', [], [], report_dir=root)
            registry = json.loads((root/'out/media-sources.json').read_text(encoding='utf-8'))
            actual = {p.name for p in (path.parent/'media').glob('*.png')}
            self.assertEqual(actual, {Path(registry[0]['path']).name})
            self.assertTrue(custom.exists(), 'Do not remove unrelated user files')

    def test_static_check_excludes_stale_motion_qa(self):
        from video_report import check_output
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            for name, value in {'timeline': [{'end_ms': 1000}], 'captions': [],
                                'encoding': {'render_mode': 'static_slides'},
                                'motion-qa': {'mode': 'deterministic_frames', 'frames': 30}}.items():
                (root/(name+'.json')).write_text(json.dumps(value), encoding='utf-8')
            with mock.patch('report_media.check_media', return_value={'passed': True, 'errors': []}):
                qa = check_output(root)
            self.assertNotIn('motion', qa, 'Do not carry a prior dynamic build QA into a static build')

    def test_schema_rejects_unknown_media_and_invalid_motion(self):
        report = sample_report()
        report['scenes'][0]['media'] = {'id': 'missing'}
        report['motion']['enabled'] = 'yes'
        report['scenes'][0]['reveal_cues'] = [0, -1]
        errors = '\n'.join(validate_report(report))
        self.assertIn('unknown media', errors)
        self.assertIn('motion', errors)
        self.assertIn('reveal_cues', errors)

    def test_packaged_asset_uses_relative_path_and_retains_provenance(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root/'photo.png').write_bytes(b'asset bytes')
            report = sample_report()
            asset = {'id': '../unsafe', 'path': 'photo.png', 'type': 'image', 'title': 'Photo',
                     'source_url': 'https://example.org/photo', 'creator': 'Photographer',
                     'license': 'CC BY 4.0', 'license_url': 'https://creativecommons.org/licenses/by/4.0/',
                     'attribution': 'Photographer, CC BY 4.0',
                     'sha256': hashlib.sha256(b'asset bytes').hexdigest()}
            report['media'] = [asset]
            report['scenes'][0]['media'] = {'id': asset['id'], 'caption': 'Illustration'}
            path = write_deck(report, root/'out', [], [], report_dir=root)
            manifest = json.loads((root/'out/media-sources.json').read_text(encoding='utf-8'))
            packaged = path.parent/manifest[0]['path']
            self.assertEqual(packaged.read_bytes(), b'asset bytes')
            self.assertEqual(packaged.parent, path.parent/'media')
            self.assertEqual(manifest[0]['creator'], 'Photographer')
            self.assertIn(manifest[0]['path'], path.read_text(encoding='utf-8'))
            self.assertEqual(report['media'][0]['path'], 'photo.png', 'Do not mutate caller input')

    def test_missing_and_checksum_mismatch_fail_before_deck_is_published(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            report = sample_report()
            report['media'] = [{'id': 'x', 'type': 'image', 'path': 'missing.png', 'sha256': '0'*64}]
            with self.assertRaisesRegex((ValueError, RuntimeError), 'missing|exist'):
                write_deck(report, root/'out', [], [], report_dir=root)
            (root/'missing.png').write_bytes(b'wrong')
            with self.assertRaisesRegex((ValueError, RuntimeError), 'checksum|SHA'):
                write_deck(report, root/'out', [], [], report_dir=root)
            self.assertFalse((root/'out/deck/index.html').exists())


class DeterministicMotionTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        from playwright.sync_api import sync_playwright
        cls.runtime = sync_playwright().start()
        cls.browser = cls.runtime.chromium.launch(**browser_options())

    @classmethod
    def tearDownClass(cls):
        cls.browser.close()
        cls.runtime.stop()

    def test_reveals_follow_cues_and_seeking_back_restores_state(self):
        with tempfile.TemporaryDirectory() as tmp:
            timeline = [{'start_ms': 0, 'end_ms': 5000}]
            captions = [{'start_ms': 300, 'end_ms': 1500, 'text': 'First.'},
                        {'start_ms': 2500, 'end_ms': 4800, 'text': 'Second.'}]
            path = write_deck(sample_report(), Path(tmp), timeline, captions)
            page = self.browser.new_page(viewport={'width': 960, 'height': 540})
            try:
                page.goto(path.as_uri()+'?export=1')
                def state(ms):
                    page.evaluate('ms => window.renderFrame(ms)', ms)
                    return page.evaluate("""() => ({cards:[...document.querySelectorAll('.card')].map(x=>Number(x.style.opacity)),
                        progress:document.querySelector('#progress-fill').style.transform})""")
                early = state(1200)
                late = state(3400)
                again = state(1200)
                self.assertEqual(early, again)
                self.assertEqual(early['cards'], [1, 0])
                self.assertEqual(late['cards'], [1, 1])
                self.assertNotEqual(early['progress'], late['progress'])
            finally:
                page.close()

    def test_closing_stays_inside_safe_area_during_delayed_reveal(self):
        report = sample_report()
        report['scenes'] = [{'id': 'end', 'kind': 'closing', 'kicker': '结论',
            'title': '按任务选形式，\n用结果验效果', 'subtitle': '分别看偏好、理解和任务完成情况。',
            'quote': '把内容讲清，\n比选文件格式更重要。',
            'footline': '内容可比 · 分开测量 · 给观众选择', 'narration': '结论。'}]
        with tempfile.TemporaryDirectory() as tmp:
            path = write_deck(report, Path(tmp), [{'start_ms': 0, 'end_ms': 12000}], [])
            page = self.browser.new_page(viewport={'width': 1920, 'height': 1080})
            try:
                page.goto(path.as_uri()+'?export=1')
                for ms in (50, 1200, 1700, 3000):
                    page.evaluate('ms=>window.renderFrame(ms)', ms)
                    self.assertEqual(page.evaluate('window.layoutIssues()'), [], f'Overflow at {ms}ms')
            finally:
                page.close()


if __name__ == '__main__':
    unittest.main()
