"""user.ini 定向同步对话框。"""
from __future__ import annotations

from pathlib import Path

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import (
    QFileDialog,
    QDialog,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QMessageBox,
    QPushButton,
    QSplitter,
    QTextEdit,
    QVBoxLayout,
)

from src.core.userini_handler import IniSection, MergePreview, apply_merge, parse_ini, preview_merge


class UserIniDialog(QDialog):
    def __init__(self, t0002_path: Path | None = None, parent=None) -> None:
        super().__init__(parent)
        self.setWindowTitle("user.ini 定向同步")
        self.setMinimumSize(860, 560)
        self._t0002_path = t0002_path
        self._src_path: Path | None = None
        self._dst_path: Path | None = None
        self._src_sections: list[IniSection] = []
        self._dst_sections: list[IniSection] = []
        self._dst_header: list[str] = []
        self._preview: MergePreview | None = None
        self._build_ui()

    def _build_ui(self) -> None:
        root = QVBoxLayout(self)

        path_layout = QHBoxLayout()
        self._src_label = QLabel("源 user.ini：未选择")
        self._src_label.setWordWrap(True)
        path_layout.addWidget(self._src_label, stretch=1)
        src_btn = QPushButton("选择源 user.ini…")
        src_btn.clicked.connect(self._pick_src)
        path_layout.addWidget(src_btn)

        self._dst_label = QLabel("目标 user.ini：未选择")
        self._dst_label.setWordWrap(True)
        path_layout.addWidget(self._dst_label, stretch=1)
        dst_btn = QPushButton("选择目标 user.ini…")
        dst_btn.clicked.connect(self._pick_dst)
        path_layout.addWidget(dst_btn)
        root.addLayout(path_layout)

        splitter = QSplitter(Qt.Orientation.Horizontal)

        src_box = QGroupBox("源 section")
        src_box_layout = QVBoxLayout(src_box)
        self._src_list = QListWidget()
        self._src_list.itemSelectionChanged.connect(self._on_selection_changed)
        src_box_layout.addWidget(self._src_list)
        splitter.addWidget(src_box)

        dst_box = QGroupBox("目标 section")
        dst_box_layout = QVBoxLayout(dst_box)
        self._dst_list = QListWidget()
        dst_box_layout.addWidget(self._dst_list)
        splitter.addWidget(dst_box)

        root.addWidget(splitter, stretch=1)

        preview_box = QGroupBox("同步预览")
        preview_layout = QVBoxLayout(preview_box)
        self._preview_edit = QTextEdit()
        self._preview_edit.setReadOnly(True)
        self._preview_edit.setFixedHeight(140)
        preview_layout.addWidget(self._preview_edit)
        root.addWidget(preview_box)

        btn_layout = QHBoxLayout()
        self._preview_btn = QPushButton("生成预览")
        self._preview_btn.setEnabled(False)
        self._preview_btn.clicked.connect(self._on_preview)
        btn_layout.addWidget(self._preview_btn)

        self._apply_btn = QPushButton("确认同步")
        self._apply_btn.setEnabled(False)
        self._apply_btn.clicked.connect(self._on_apply)
        btn_layout.addWidget(self._apply_btn)

        btn_layout.addStretch()
        cancel_btn = QPushButton("取消")
        cancel_btn.clicked.connect(self.reject)
        btn_layout.addWidget(cancel_btn)
        root.addLayout(btn_layout)

    def _pick_src(self) -> None:
        start = str(self._t0002_path) if self._t0002_path else ""
        path, _ = QFileDialog.getOpenFileName(self, "选择源 user.ini", start, "INI 文件 (*.ini)")
        if not path:
            return
        self._src_path = Path(path)
        self._src_label.setText(f"源：{path}")
        self._load_src()

    def _pick_dst(self) -> None:
        start = str(self._t0002_path) if self._t0002_path else ""
        path, _ = QFileDialog.getOpenFileName(self, "选择目标 user.ini", start, "INI 文件 (*.ini)")
        if not path:
            return
        self._dst_path = Path(path)
        self._dst_label.setText(f"目标：{path}")
        self._load_dst()

    def _populate_section_list(self, widget: QListWidget, sections: list[IniSection]) -> None:
        widget.clear()
        for section in sections:
            widget.addItem(QListWidgetItem(f"[{section.name}]"))

    def _load_src(self) -> None:
        try:
            self._src_sections, _ = parse_ini(self._src_path)
            self._populate_section_list(self._src_list, self._src_sections)
        except Exception as exc:
            QMessageBox.warning(self, "读取失败", str(exc))
        self._update_btn_states()

    def _load_dst(self) -> None:
        try:
            self._dst_sections, self._dst_header = parse_ini(self._dst_path)
            self._populate_section_list(self._dst_list, self._dst_sections)
        except Exception as exc:
            QMessageBox.warning(self, "读取失败", str(exc))
        self._update_btn_states()

    def _on_selection_changed(self) -> None:
        selected = self._src_list.selectedItems()
        if not selected:
            return
        index = self._src_list.row(selected[0])
        if 0 <= index < len(self._src_sections):
            self._preview_edit.setPlainText(self._src_sections[index].as_text())

    def _on_preview(self) -> None:
        try:
            self._preview = preview_merge(self._src_sections, self._dst_sections)
        except ValueError as exc:
            self._preview = None
            self._preview_edit.setPlainText(str(exc))
            self._apply_btn.setEnabled(False)
            QMessageBox.warning(self, "预览失败", str(exc))
            return

        lines: list[str] = []
        if self._preview.keys_to_replace:
            lines.append("【将替换键值】")
            for dst_section, replace_lines in self._preview.keys_to_replace:
                lines.append(f"  [{dst_section.name}]  ~{len(replace_lines)} 项")
        if self._preview.keys_to_add:
            lines.append("【将追加键值（仅 extern_*）】")
            for dst_section, add_lines in self._preview.keys_to_add:
                lines.append(f"  [{dst_section.name}]  +{len(add_lines)} 项")
        if self._preview.missing_target_sections:
            lines.append("【目标缺失段落，已跳过】")
            for section in self._preview.missing_target_sections:
                lines.append(f"  [{section.name}]")
        if self._preview.already_identical:
            lines.append("【无需变更】")
            for section in self._preview.already_identical:
                lines.append(f"  [{section.name}]")
        if not lines:
            lines.append("源与目标可同步配置一致，无需变更。")

        self._preview_edit.setPlainText("\n".join(lines))
        self._apply_btn.setEnabled(bool(
            self._preview.keys_to_replace or self._preview.keys_to_add
        ))

    def _on_apply(self) -> None:
        if self._preview is None:
            return
        try:
            apply_merge(self._dst_path, self._dst_sections, self._dst_header, self._preview)
            QMessageBox.information(self, "同步成功", "user.ini 定向同步完成。\n原文件已备份为 .ini.bak。")
            self.accept()
        except Exception as exc:
            QMessageBox.critical(self, "同步失败", str(exc))

    def _update_btn_states(self) -> None:
        ready = self._src_path is not None and self._dst_path is not None
        self._preview_btn.setEnabled(ready)
        self._apply_btn.setEnabled(False)
