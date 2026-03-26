"""user.ini extern 段落合并对话框"""
from __future__ import annotations
from pathlib import Path

from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QGroupBox, QListWidget,
    QListWidgetItem, QTextEdit, QPushButton, QLabel, QFileDialog,
    QMessageBox, QSplitter,
)
from PyQt6.QtCore import Qt

from src.core.userini_handler import (
    IniSection, MergePreview, apply_merge, get_extern_sections,
    parse_ini, preview_merge,
)


class UserIniDialog(QDialog):
    def __init__(self, t0002_path: Path | None = None, parent=None) -> None:
        super().__init__(parent)
        self.setWindowTitle("user.ini extern 段落合并")
        self.setMinimumSize(800, 560)
        self._t0002_path = t0002_path
        self._src_path: Path | None = None
        self._dst_path: Path | None = None
        self._src_externs: list[IniSection] = []
        self._dst_externs: list[IniSection] = []
        self._dst_sections: list[IniSection] = []
        self._dst_header: list[str] = []
        self._preview: MergePreview | None = None
        self._build_ui()

    def _build_ui(self) -> None:
        root = QVBoxLayout(self)

        # 路径选择行
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

        # 段落对比视图
        splitter = QSplitter(Qt.Orientation.Horizontal)

        src_box = QGroupBox("源 extern 段落")
        src_box_layout = QVBoxLayout(src_box)
        self._src_list = QListWidget()
        self._src_list.itemSelectionChanged.connect(self._on_selection_changed)
        src_box_layout.addWidget(self._src_list)
        splitter.addWidget(src_box)

        dst_box = QGroupBox("目标 extern 段落")
        dst_box_layout = QVBoxLayout(dst_box)
        self._dst_list = QListWidget()
        dst_box_layout.addWidget(self._dst_list)
        splitter.addWidget(dst_box)

        root.addWidget(splitter, stretch=1)

        # 预览
        preview_box = QGroupBox("合并预览")
        preview_layout = QVBoxLayout(preview_box)
        self._preview_edit = QTextEdit()
        self._preview_edit.setReadOnly(True)
        self._preview_edit.setFixedHeight(120)
        preview_layout.addWidget(self._preview_edit)
        root.addWidget(preview_box)

        # 按钮行
        btn_layout = QHBoxLayout()
        self._preview_btn = QPushButton("生成预览")
        self._preview_btn.setEnabled(False)
        self._preview_btn.clicked.connect(self._on_preview)
        btn_layout.addWidget(self._preview_btn)

        self._apply_btn = QPushButton("确认合并")
        self._apply_btn.setEnabled(False)
        self._apply_btn.clicked.connect(self._on_apply)
        btn_layout.addWidget(self._apply_btn)

        btn_layout.addStretch()
        cancel_btn = QPushButton("取消")
        cancel_btn.clicked.connect(self.reject)
        btn_layout.addWidget(cancel_btn)
        root.addLayout(btn_layout)

    # ------------------------------------------------------------------ #
    # slots
    # ------------------------------------------------------------------ #

    def _pick_src(self) -> None:
        start = str(self._t0002_path) if self._t0002_path else ""
        path, _ = QFileDialog.getOpenFileName(self, "选择源 user.ini", start, "INI 文件 (*.ini)")
        if path:
            self._src_path = Path(path)
            self._src_label.setText(f"源：{path}")
            self._load_src()

    def _pick_dst(self) -> None:
        start = str(self._t0002_path) if self._t0002_path else ""
        path, _ = QFileDialog.getOpenFileName(self, "选择目标 user.ini", start, "INI 文件 (*.ini)")
        if path:
            self._dst_path = Path(path)
            self._dst_label.setText(f"目标：{path}")
            self._load_dst()

    def _load_src(self) -> None:
        try:
            sections, _ = parse_ini(self._src_path)
            self._src_externs = get_extern_sections(sections)
            self._src_list.clear()
            for sec in self._src_externs:
                self._src_list.addItem(QListWidgetItem(f"[{sec.name}]"))
        except Exception as exc:
            QMessageBox.warning(self, "读取失败", str(exc))
        self._update_btn_states()

    def _load_dst(self) -> None:
        try:
            self._dst_sections, self._dst_header = parse_ini(self._dst_path)
            self._dst_externs = get_extern_sections(self._dst_sections)
            self._dst_list.clear()
            for sec in self._dst_externs:
                self._dst_list.addItem(QListWidgetItem(f"[{sec.name}]"))
        except Exception as exc:
            QMessageBox.warning(self, "读取失败", str(exc))
        self._update_btn_states()

    def _on_selection_changed(self) -> None:
        sel = self._src_list.selectedItems()
        if sel:
            idx = self._src_list.row(sel[0])
            if 0 <= idx < len(self._src_externs):
                self._preview_edit.setPlainText(self._src_externs[idx].as_text())

    def _on_preview(self) -> None:
        try:
            self._preview = preview_merge(self._src_externs, self._dst_externs)
        except ValueError as exc:
            self._preview = None
            self._preview_edit.setPlainText(str(exc))
            self._apply_btn.setEnabled(False)
            QMessageBox.warning(self, "预览失败", str(exc))
            return
        lines: list[str] = []
        if self._preview.sections_to_add:
            lines.append("【将新增段落】")
            for s in self._preview.sections_to_add:
                lines.append(f"  [{s.name}]  ({len(s.lines)} 行)")
        if self._preview.keys_to_add:
            lines.append("【将追加键值】")
            for dst_sec, new_lines in self._preview.keys_to_add:
                lines.append(f"  [{dst_sec.name}]  +{len(new_lines)} 行")
        if self._preview.already_identical:
            lines.append("【目标已包含全部键，跳过】")
            for s in self._preview.already_identical:
                lines.append(f"  [{s.name}]")
        if not lines:
            lines.append("源与目标 extern 段落完全相同，无需合并。")
        self._preview_edit.setPlainText("\n".join(lines))
        self._apply_btn.setEnabled(bool(
            self._preview.sections_to_add or self._preview.keys_to_add
        ))

    def _on_apply(self) -> None:
        if self._preview is None:
            return
        try:
            apply_merge(self._dst_path, self._dst_sections, self._dst_header, self._preview)
            QMessageBox.information(self, "合并成功", "extern 段落合并完成。\n原文件已备份为 .ini.bak。")
            self.accept()
        except Exception as exc:
            QMessageBox.critical(self, "合并失败", str(exc))

    def _update_btn_states(self) -> None:
        ready = self._src_path is not None and self._dst_path is not None
        self._preview_btn.setEnabled(ready)
        self._apply_btn.setEnabled(False)
