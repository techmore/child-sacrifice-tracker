import hashlib
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from scripts import fetch_references


class ArchiveRestoreTest(unittest.TestCase):
    def test_repeated_failure_preserves_the_checksum_until_explicit_refresh(self):
        source = {"id": "report", "access": "private", "url": "https://example.invalid/report.pdf"}
        checksum = hashlib.sha256(b"original").hexdigest()
        previous = {"report": {**source, "status": "saved", "sha256": checksum}}

        def changed_download(source, folder, expected_sha256):
            if expected_sha256 == checksum:
                raise ValueError("Publisher changed the file")
            path = folder / "report.pdf"
            path.write_bytes(b"new version")
            return path

        with tempfile.TemporaryDirectory() as folder, patch.object(fetch_references, "ROOT", Path(folder)):
            with patch.object(fetch_references, "download", side_effect=changed_download):
                for _ in range(2):
                    failed = fetch_references.archive_source(source, previous, refresh=False)
                    self.assertEqual(failed["status"], "failed")
                    self.assertEqual(failed["expected_sha256"], checksum)
                    self.assertFalse(list((Path(folder) / "private").iterdir()))
                    previous = {"report": failed}
                refreshed = fetch_references.archive_source(source, previous, refresh=True)
                self.assertEqual(refreshed["status"], "saved")
                self.assertNotEqual(refreshed["sha256"], checksum)
