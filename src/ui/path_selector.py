"""路径选择组件 — 自动检测 + 手动浏览"""
from __future__ import annotations
from pathlib import Path

from PyQt6.QtWidgets import (
    QWidget, QHBoxLayout, QComboBox, QLineEdit, QPushButton, QFileDialog, QMessageBox,
)
from PyQt6.QtCore import pyqtSignal

from src.core.tdx_finder import TdxInstance, find_tdx_instances, validate_t0002_path


class PathSelector(QWidget):
    path_changed = pyqtSignal(Path)   # 有效路径变更时发射

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self._instances: list[TdxInstance] = []

        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)

        self._combo = QComboBox()
        self._combo.setMinimumWidth(180)
        self._combo.currentIndexChanged.connect(self._on_combo_changed)
        layout.addWidget(self._combo)

        self._path_edit = QLineEdit()
        self._path_edit.setPlaceholderText("T0002 目录路径…")
        self._path_edit.editingFinished.connect(self._on_edit_finished)
        layout.addWidget(self._path_edit, stretch=1)

        self._browse_btn = QPushButton("浏览…")
        self._browse_btn.clicked.connect(self._on_browse)
        layout.addWidget(self._browse_btn)

        self._detect_btn = QPushButton("自动检测")
        self._detect_btn.clicked.connect(self.refresh_instances)
        layout.addWidget(self._detect_btn)

    # ------------------------------------------------------------------ #
    # public API
    # ------------------------------------------------------------------ #

    def refresh_instances(self) -> None:
        """重新扫描通达信实例，填充下拉框。"""
        self._instances = find_tdx_instances()
        self._combo.blockSignals(True)
        self._combo.clear()
        if self._instances:
            self._combo.addItem("— 选择检测到的实例 —")
            for inst in self._instances:
                self._combo.addItem(str(inst))
        else:
            self._combo.addItem("— 未检测到通达信（请手动选择）—")
        self._combo.blockSignals(False)

    def current_path(self) -> Path | None:
        text = self._path_edit.text().strip()
        if text:
            p = Path(text)
            if validate_t0002_path(p):
                return p
        return None

    def set_path(self, path: Path) -> None:
        self._path_edit.setText(str(path))
        self.path_changed.emit(path)

    # ------------------------------------------------------------------ #
    # private slots
    # ------------------------------------------------------------------ #

    def _on_combo_changed(self, idx: int) -> None:
        # 索引 0 为占位提示
        real_idx = idx - 1
        if 0 <= real_idx < len(self._instances):
            inst = self._instances[real_idx]
            self._path_edit.setText(str(inst.t0002_path))
            self.path_changed.emit(inst.t0002_path)

    def _on_edit_finished(self) -> None:
        text = self._path_edit.text().strip()
        if not text:
            return
        p = Path(text)
        if validate_t0002_path(p):
            self.path_changed.emit(p)
        else:
            QMessageBox.warning(
                self,
                "路径无效",
                f"所选路径不是有效的 T0002 目录：\n{p}\n\n"
                "请确认路径正确，且目录下包含 blocknew 或 vipdoc 子目录。",
            )

    def _on_browse(self) -> None:
        folder = QFileDialog.getExistingDirectory(self, "选择 T0002 目录", "")
        if not folder:
            return
        p = Path(folder)
        if validate_t0002_path(p):
            self._path_edit.setText(str(p))
            self.path_changed.emit(p)
        else:
            QMessageBox.warning(
                self,
                "路径无效",
                f"所选路径不是有效的 T0002 目录：\n{p}",
            )
