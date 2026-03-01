"""对比树：按安全等级分组，展示左右两侧文件统计与差异"""
from __future__ import annotations

from PyQt6.QtCore import Qt
from PyQt6.QtGui import QColor, QBrush, QFont
from PyQt6.QtWidgets import QAbstractItemView, QTreeWidget, QTreeWidgetItem

from src.core.compare import CompareResult
from src.core.data_items import CAUTION_ITEMS, FORBIDDEN_ITEMS, SAFE_ITEMS, DataItem

_KB = 1024
_MB = _KB * _KB

_SAFETY_COLORS = {
    "safe": QColor("#16A34A"),
    "caution": QColor("#D97706"),
    "forbidden": QColor("#DC2626"),
}

_SAFETY_LABELS = {
    "safe": "安全项目（默认全选）",
    "caution": "谨慎项目（默认不选）",
    "forbidden": "禁止项（仅提示）",
}


def _format_size(size: int) -> str:
    if size < _KB:
        return f"{size} B"
    if size < _MB:
        return f"{size / _KB:.1f} KB"
    return f"{size / _MB:.1f} MB"


class CompareTree(QTreeWidget):
    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.setHeaderLabels(["数据项", "左侧", "右侧", "差异"])
        self.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self.setColumnWidth(0, 250)
        self.setColumnWidth(1, 160)
        self.setColumnWidth(2, 160)
        self._item_map: dict[str, QTreeWidgetItem] = {}
        self._data_items: dict[str, DataItem] = {}
        self._compare: CompareResult | None = None
        self._build_tree()

    def set_compare_result(self, compare: CompareResult | None) -> None:
        self._compare = compare
        for item_id, widget_item in self._item_map.items():
            self._update_row(item_id, widget_item)

    def selected_item_ids(self) -> list[str]:
        result: list[str] = []
        for item_id, widget_item in self._item_map.items():
            if widget_item.checkState(0) == Qt.CheckState.Checked:
                result.append(item_id)
        return result

    def select_all_safe(self) -> None:
        for item_id, widget_item in self._item_map.items():
            data = self._data_items[item_id]
            if data.safety_level == "safe":
                widget_item.setCheckState(0, Qt.CheckState.Checked)

    def clear_all(self) -> None:
        for widget_item in self._item_map.values():
            if widget_item.flags() & Qt.ItemFlag.ItemIsUserCheckable:
                widget_item.setCheckState(0, Qt.CheckState.Unchecked)

    def get_data_item(self, item_id: str) -> DataItem | None:
        return self._data_items.get(item_id)

    # ------------------------------------------------------------------ #
    # tree build
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
        child = QTreeWidgetItem(group_item, [data_item.name, "—", "—", "—"])
        child.setData(0, Qt.ItemDataRole.UserRole, data_item.id)
        child.setToolTip(0, data_item.description)
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

    # ------------------------------------------------------------------ #
    # update
    # ------------------------------------------------------------------ #

    def _update_row(self, item_id: str, widget_item: QTreeWidgetItem) -> None:
        if self._compare is None:
            widget_item.setText(1, "—")
            widget_item.setText(2, "—")
            widget_item.setText(3, "—")
            return

        item_cmp = self._compare.by_item_id.get(item_id)
        if item_cmp is None:
            widget_item.setText(1, "—")
            widget_item.setText(2, "—")
            widget_item.setText(3, "—")
            return

        left_summary = f"{len(item_cmp.left_files)} 文件 / {_format_size(item_cmp.left_total_size)}"
        right_summary = f"{len(item_cmp.right_files)} 文件 / {_format_size(item_cmp.right_total_size)}"
        widget_item.setText(1, left_summary)
        widget_item.setText(2, right_summary)

        if not item_cmp.has_diff():
            widget_item.setText(3, "一致")
            return

        diff = f"缺失L:{len(item_cmp.only_left)} 缺失R:{len(item_cmp.only_right)} 冲突:{len(item_cmp.conflicts)}"
        widget_item.setText(3, diff)
