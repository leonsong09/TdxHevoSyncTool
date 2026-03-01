import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

from src.utils.file_ops import collect_files


class TestCollectFilesDedup(unittest.TestCase):
    def test_case_insensitive_paths_are_deduped(self) -> None:
        with TemporaryDirectory() as td:
            base = Path(td)
            (base / "Scheme.dat").write_text("x", encoding="utf-8")
            files = collect_files(base, ("Scheme.dat", "scheme.dat"))
            self.assertEqual(len(files), 1)

