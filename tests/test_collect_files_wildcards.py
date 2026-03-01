import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

from src.utils.file_ops import collect_files


class TestCollectFilesWildcards(unittest.TestCase):
    def test_wildcards_match_only_root(self) -> None:
        with TemporaryDirectory() as td:
            base = Path(td)
            (base / "a.czs").write_text("a", encoding="utf-8")
            (base / "b.cos").write_text("b", encoding="utf-8")
            (base / "clid_foo.dat").write_text("c", encoding="utf-8")

            sub = base / "sub"
            sub.mkdir()
            (sub / "c.czs").write_text("sub", encoding="utf-8")

            files = collect_files(base, ("*.czs", "*.cos", "clid_*.dat"))
            names = {p.name for p in files}
            self.assertEqual(names, {"a.czs", "b.cos", "clid_foo.dat"})

