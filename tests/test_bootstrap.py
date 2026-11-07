import io
from pathlib import Path
import sys
import tempfile
import unittest
import zipfile

sys.path.insert(0, str(Path(__file__).resolve().parents[1]/'skills/video-report/scripts'))
import bootstrap


class BootstrapTests(unittest.TestCase):
    def test_browser_archive_cannot_write_outside_destination(self):
        self.assertTrue(hasattr(bootstrap, 'extract_browser_archive'), 'Portable browser extractor is missing')
        stream = io.BytesIO()
        with zipfile.ZipFile(stream, 'w') as archive:
            archive.writestr('../outside.txt', 'unsafe')
        with tempfile.TemporaryDirectory() as tmp:
            with self.assertRaisesRegex(ValueError, 'outside'):
                bootstrap.extract_browser_archive(stream.getvalue(), Path(tmp)/'browser')
            self.assertFalse((Path(tmp)/'outside.txt').exists())


if __name__ == '__main__':
    unittest.main()
