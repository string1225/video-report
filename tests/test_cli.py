from pathlib import Path
import json
import subprocess
import sys
import tempfile
import unittest

CLI = Path(__file__).resolve().parents[1]/'skills/video-report/scripts/video_report.py'


class CliTests(unittest.TestCase):
    def test_help_is_available_without_media_dependencies(self):
        self.assertTrue(CLI.exists(), 'Public CLI is missing')
        result = subprocess.run([sys.executable, str(CLI), '--help'], capture_output=True)
        self.assertEqual(result.returncode, 0, result.stderr.decode('utf-8', 'replace'))
        self.assertIn(b'build', result.stdout)

    def test_validate_rejects_unsupported_claim_source(self):
        self.assertTrue(CLI.exists(), 'Public CLI is missing')
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp)/'report.json'
            path.write_text(json.dumps({'title': 'Research', 'scenes': [
                {'id': 's1', 'kind': 'cards', 'title': 'Claim', 'narration': 'Text', 'source_ids': ['missing']}]}), encoding='utf-8')
            result = subprocess.run([sys.executable, str(CLI), 'validate', str(path)], capture_output=True)
            self.assertNotEqual(result.returncode, 0)
            self.assertIn(b'unknown source', result.stderr)


if __name__ == '__main__':
    unittest.main()
