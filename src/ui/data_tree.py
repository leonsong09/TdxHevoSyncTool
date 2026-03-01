"""数据分类树形选择组件"""
from __future__ import annotations
from pathlib import Path

from PyQt6.QtWidgets import QTreeWidget, QTreeWidgetItem, QAbstractItemView
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QColor, QBrush, QFont

from src.core.data_items import CAUTION_ITEMS, FORBIDDEN_ITEMS, SAFE_ITEMS, DataItem
from src.utils.file_ops import collect_files, count_size

_SAFETY_COLORS = {
    "safe": QColor("#16A34A"),
    "caution": QColor("#D97706"),
    "forbidden": QColor("#DC2626"),
}

_SAFETY_LABELS = {
    "safe": "安全项目（默认全选）",
    "caution": "谨慎项目（默认不选）",
    "forbidden": "禁止直接复制（仅提示）",
}


class DataTree(QTreeWidget):
    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.setHeaderLabels(["数据项", "包含路径", "文件状态"])
        self.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self.setColumnWidth(0, 220)
        self.setColumnWidth(1, 200)
        self.setAlternatingRowColors(False)
        self._item_map: dict[str, QTreeWidgetItem] = {}
        self._data_items: dict[str, DataItem] = {}
        self._t0002_path: Path | None = None
        self._build_tree()

    # ------------------------------------------------------------------ #
    # public API
    # ------------------------------------------------------------------ #

    def set_t0002_path(self, path: Path | None) -> None:
        self._t0002_path = path
        self._refresh_sizes()

    def selected_items(self) -> list[DataItem]:
        result: list[DataItem] = []
        for item_id, widget_item in self._item_map.items():
            if widget_item.checkState(0) == Qt.CheckState.Checked:
                result.append(self._data_items[item_id])
        return result

    def select_all_safe(self) -> None:
        for item_id, widget_item in self._item_map.items():
            data = self._data_items[item_id]
            state = Qt.CheckState.Checked if data.safety_level == "safe" else Qt.CheckState.Unchecked
            if widget_item.flags() & Qt.ItemFlag.ItemIsUserCheckable:
                widget_item.setCheckState(0, state)

    def clear_all(self) -> None:
        for widget_item in self._item_map.values():
            if widget_item.flags() & Qt.ItemFlag.ItemIsUserCheckable:
                widget_item.setCheckState(0, Qt.CheckState.Unchecked)

    def get_data_item(self, item_id: str) -> DataItem | None:
        return self._data_items.get(item_id)

    # ------------------------------------------------------------------ #
    # private helpers
    # ------------------------------------------------------------------ #

    @staticmethod
    def _make_group_item(parent, safety: str) -> QTreeWidgetItem:
        group_item = QTreeWidgetItem(parent, [_SAFETY_LABELS[safety]])
        group_item.setExpanded(True)
        group_item.setFlags(group_item.flags() & ~Qt.ItemFlag.ItemIsUserCheckable)
        group_item.setData(0, Qt.ItemDataRole.UserRole, f"group:{safety}")
        font = QFont()
        font.setBold(True)
        group_item.setFont(0, font)
        group_item.setForeground(0, QBrush(_SAFETY_COLORS[safety]))
        return group_item

    def _make_child_item(self, group_item: QTreeWidgetItem, data_item: DataItem) -> None:
        paths_display = ", ".join(data_item.paths[:2])
        if len(data_item.paths) > 2:
            paths_display += f" …+{len(data_item.paths) - 2}"

        child = QTreeWidgetItem(group_item, [data_item.name, paths_display, "—"])
        child.setData(0, Qt.ItemDataRole.UserRole, data_item.id)
        child.setToolTip(0, data_item.description)
        child.setToolTip(1, "\n".join(data_item.paths))
        child.setForeground(0, QBrush(_SAFETY_COLORS[data_item.safety_level]))

        if data_item.safety_level == "forbidden":
            child.setFlags(child.flags() & ~Qt.ItemFlag.ItemIsUserCheckable)
            child.setCheckState(0, Qt.CheckState.Unchecked)
        else:
            child.setCheckState(
                0,
                Qt.CheckState.Checked if data_item.safety_level == "safe" else Qt.CheckState.Unchecked,
            )

        self._item_map[data_item.id] = child
        self._data_items[data_item.id] = data_item

    def _build_tree(self) -> None:
        self.clear()
        self._item_map.clear()
        self._data_items.clear()

        groups = [
            ("safe", SAFE_ITEMS),
            ("caution", CAUTION_ITEMS),
            ("forbidden", FORBIDDEN_ITEMS),
        ]

        for safety, items in groups:
            group_item = self._make_group_item(self, safety)
            for data_item in items:
                self._make_child_item(group_item, data_item)

        self.expandAll()

    def _refresh_sizes(self) -> None:
        if self._t0002_path is None:
            return
        for item_id, widget_item in self._item_map.items():
            data = self._data_items[item_id]
            files = collect_files(self._t0002_path, data.paths)
            if not files:
                widget_item.setText(2, "（文件不存在）")
                widget_item.setForeground(2, QBrush(QColor("#999")))
            else:
                size = count_size(files)
                size_str = self._format_size(size)
                widget_item.setText(2, f"{len(files)} 个文件 / {size_str}")

    @staticmethod
    def _format_size(size: int) -> str:
        if size < 1024:
            return f"{size} B"
        elif size < 1024 ** 2:
            return f"{size / 1024:.1f} KB"
        else:
            return f"{size / 1024 / 1024:.1f} MB"
