import os
import unittest
from unittest.mock import patch
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
if Path("C:/Windows/Fonts").exists():
    os.environ.setdefault("QT_QPA_FONTDIR", "C:/Windows/Fonts")

from PyQt6.QtCore import qInstallMessageHandler
from PyQt6.QtWidgets import QApplication, QMessageBox

from src.core.userini_handler import IniSection
from src.ui.userini_dialog import UserIniDialog


class TestUserIniDialog(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls._previous_qt_handler = qInstallMessageHandler(lambda *_args: None)
        cls._app = QApplication.instance() or QApplication([])

    @classmethod
    def tearDownClass(cls) -> None:
        qInstallMessageHandler(cls._previous_qt_handler)

    def test_preview_populates_summary_and_enables_apply(self) -> None:
        dialog = UserIniDialog()
        dialog._src_sections = [IniSection("common", ["A=1\n"]), IniSection("extern_1", ["B=2\n"])]
        dialog._dst_sections = [IniSection("common", ["A=9\n"]), IniSection("extern_1", ["A=8\n"])]

        dialog._on_preview()

        self.assertIn("【将替换键值】", dialog._preview_edit.toPlainText())
        self.assertIn("【将追加键值（仅 extern_*）】", dialog._preview_edit.toPlainText())
        self.assertTrue(dialog._apply_btn.isEnabled())

    def test_preview_shows_warning_when_target_has_duplicate_sections(self) -> None:
        dialog = UserIniDialog()
        dialog._src_sections = [IniSection("common", ["A=1\n"])]
        dialog._dst_sections = [
            IniSection("common", ["A=2\n"]),
            IniSection("common", ["B=3\n"]),
        ]

        with patch.object(QMessageBox, "warning") as warning:
            dialog._on_preview()

        self.assertIsNone(dialog._preview)
        self.assertFalse(dialog._apply_btn.isEnabled())
        self.assertIn("重复的段", dialog._preview_edit.toPlainText())
        warning.assert_called_once()
