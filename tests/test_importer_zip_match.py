import unittest

from src.core.data_items import DataItem
from src.core.importer import _collect_zip_targets


class TestImporterZipMatch(unittest.TestCase):
    def test_collect_zip_targets_supports_wildcards(self) -> None:
        zip_names = [
            "manifest.json",
            "blocknew/ZXG.blk",
            "a.czs",
            "sub/a.czs",
            "clid_银河证券.dat",
            "pad/layout.dat",
            "a.czs",
        ]

        items = [
            DataItem(
                id="blocknew",
                name="blocknew",
                description="",
                safety_level="safe",
                paths=("blocknew",),
                is_directory=True,
            ),
            DataItem(
                id="profiles",
                name="profiles",
                description="",
                safety_level="safe",
                paths=("*.czs", "*.cos"),
            ),
            DataItem(
                id="clid",
                name="clid",
                description="",
                safety_level="caution",
                paths=("clid_*.dat",),
            ),
        ]

        targets = _collect_zip_targets(zip_names, items)
        rel_paths = [t.rel_path for t in targets]
        self.assertEqual(rel_paths, ["blocknew/ZXG.blk", "a.czs", "clid_银河证券.dat"])

