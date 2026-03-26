import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

from src.core.userini_handler import (
    IniSection,
    apply_merge,
    get_extern_sections,
    parse_ini,
    preview_merge,
)


class TestUserIniHandler(unittest.TestCase):
    def test_parse_ini_preserves_utf8_without_bom_content(self) -> None:
        with TemporaryDirectory() as td:
            path = Path(td) / "user.ini"
            path.write_text("[extern_1]\n名称=同步到第二个\n", encoding="utf-8")

            sections, _ = parse_ini(path)

            self.assertEqual(len(sections), 1)
            self.assertEqual(sections[0].lines[0].strip(), "名称=同步到第二个")

    def test_parse_ini_supports_utf8_bom_first_section(self) -> None:
        with TemporaryDirectory() as td:
            path = Path(td) / "user.ini"
            text = "\ufeff[extern_1]\nA=1\n[extern_2]\nB=2\n"
            path.write_bytes(text.encode("utf-8"))

            sections, header = parse_ini(path)
            externs = get_extern_sections(sections)

            self.assertEqual([section.name for section in sections], ["extern_1", "extern_2"])
            self.assertEqual([section.name for section in externs], ["extern_1", "extern_2"])
            self.assertEqual(header, [])

    def test_preview_merge_rejects_duplicate_extern_sections_in_target(self) -> None:
        src_sections = [IniSection("extern_1", ["A=1\n"])]
        dst_sections = [
            IniSection("extern_1", ["A=2\n"]),
            IniSection("extern_1", ["B=3\n"]),
        ]

        with self.assertRaisesRegex(ValueError, "extern_1"):
            preview_merge(src_sections, dst_sections)

    def test_preview_merge_rejects_duplicate_extern_sections_in_source(self) -> None:
        src_sections = [
            IniSection("extern_1", ["A=1\n"]),
            IniSection("extern_1", ["B=2\n"]),
        ]
        dst_sections = [IniSection("extern_1", ["C=3\n"])]

        with self.assertRaisesRegex(ValueError, "extern_1"):
            preview_merge(src_sections, dst_sections)

    def test_apply_merge_inserts_newline_before_appended_keys(self) -> None:
        with TemporaryDirectory() as td:
            dst_path = Path(td) / "user.ini"
            dst_path.write_text("[extern_1]\nA=1", encoding="utf-8")
            dst_sections = [IniSection("extern_1", ["A=1"])]
            preview = preview_merge(
                [IniSection("extern_1", ["B=2\n"])],
                dst_sections,
            )

            apply_merge(dst_path, dst_sections, [], preview)

            self.assertEqual(dst_path.read_text(encoding="utf-8"), "[extern_1]\nA=1\nB=2\n")

    def test_apply_merge_preserves_utf8_target_encoding(self) -> None:
        with TemporaryDirectory() as td:
            dst_path = Path(td) / "user.ini"
            dst_path.write_text("[extern_1]\n名称=同步到第二个\n", encoding="utf-8")
            dst_sections = [IniSection("extern_1", ["名称=同步到第二个\n"])]
            preview = preview_merge(
                [IniSection("extern_1", ["B=2\n"])],
                dst_sections,
            )

            apply_merge(dst_path, dst_sections, [], preview)

            expected = "[extern_1]\n名称=同步到第二个\nB=2\n"
            self.assertEqual(dst_path.read_text(encoding="utf-8"), expected)
            raw_bytes = dst_path.read_bytes()
            self.assertFalse(raw_bytes.startswith(b"\xef\xbb\xbf"))
            self.assertEqual(raw_bytes.decode("utf-8").replace("\r\n", "\n"), expected)

    def test_preview_merge_dedupes_duplicate_keys_from_source_section(self) -> None:
        preview = preview_merge(
            [IniSection("extern_1", ["A=1\n", "A=2\n", "B=3\n"])],
            [IniSection("extern_1", [])],
        )

        self.assertEqual(len(preview.keys_to_add), 1)
        dst_section, new_lines = preview.keys_to_add[0]
        self.assertEqual(dst_section.name, "extern_1")
        self.assertEqual(new_lines, ["A=1\n", "B=3\n"])

    def test_preview_merge_keeps_existing_target_value(self) -> None:
        preview = preview_merge(
            [IniSection("extern_1", ["A=1\n", "B=2\n"])],
            [IniSection("extern_1", ["A=9\n"])],
        )

        self.assertEqual(preview.sections_to_add, [])
        self.assertEqual(len(preview.keys_to_add), 1)
        _, new_lines = preview.keys_to_add[0]
        self.assertEqual(new_lines, ["B=2\n"])
        self.assertEqual(preview.already_identical, [])
