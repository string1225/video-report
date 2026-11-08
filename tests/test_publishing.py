"""Check that the bundled publisher runs from an independent skill installation."""
from pathlib import Path
import json
import os
import shutil
import subprocess
import tempfile
import unittest


SKILL = Path(__file__).resolve().parents[1] / 'skills' / 'video-report'


@unittest.skipUnless(shutil.which('node'), 'Node.js is needed for publishing')
class PublishingInstallationTests(unittest.TestCase):
    def test_installed_publisher_onboards_without_browser_or_repository(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            installed = root / '独立技能 with spaces' / 'video-report'
            shutil.copytree(SKILL, installed, ignore=shutil.ignore_patterns('__pycache__'))
            publisher = installed / 'publisher'
            config_path = root / 'private' / 'config.json'
            env = {**os.environ, 'VIDEO_PUBLISHER_CONFIG': str(config_path),
                   'VIDEO_PUBLISHER_V2_EGO_COMMAND': 'browser-must-not-be-called'}

            def config(*args):
                result = subprocess.run(
                    ['node', str(publisher / 'scripts' / 'config.mjs'), *args],
                    cwd=root, env=env, capture_output=True, encoding='utf-8', timeout=30)
                self.assertEqual(result.returncode, 0, result.stderr)
                return json.loads(result.stdout)

            status = config('status')
            self.assertTrue(status['onboardingRequired'])
            self.assertFalse(config_path.exists(), 'Status must not write personal configuration')
            config('onboard', '--source-dir', str(root),
                   '--available-platform', 'bilibili', '--available-platform', 'xiaohongshu',
                   '--platform', 'bilibili', '--originality-policy', 'ask_each_run')
            status = config('status')
            self.assertFalse(status['onboardingRequired'])
            saved = json.loads(config_path.read_text(encoding='utf-8'))
            self.assertEqual(saved['availablePlatforms'], ['bilibili', 'xiaohongshu'])
            self.assertEqual(saved['defaultPlatforms'], ['bilibili'])

            result = subprocess.run(
                ['node', str(publisher / 'scripts' / 'v2' / 'publisher.mjs'),
                 '--package', str(root / 'missing-package.json'), '--platform', 'bilibili'],
                cwd=root, env=env, capture_output=True, encoding='utf-8', timeout=30)
            self.assertNotEqual(result.returncode, 0)
            self.assertIn('Package JSON not found', result.stderr)
            self.assertNotIn('browser-must-not-be-called', result.stderr)


if __name__ == '__main__':
    unittest.main()
