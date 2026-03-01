import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

from src.core.importer import _collect_folder_files


class TestImporterFolderForbidden(unittest.TestCase):
    def test_forbidden_item_is_skipped(self) -> None:
        with TemporaryDirectory() as td:
            base = Path(td)
            (base / "user.ini").write_text("[Other]\nX=1\n", encoding="utf-8")

            imported_items, all_src_files = _collect_folder_files(base, {"user_ini_forbidden"})
            self.assertEqual(imported_items, [])
            self.assertEqual(all_src_files, [])

