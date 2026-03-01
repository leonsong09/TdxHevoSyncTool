"""数据选择面板：左侧数据树 + 右侧说明"""
from __future__ import annotations

from html import escape
from pathlib import Path

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QTextBrowser,
    QSplitter,
    QPushButton,
    QTreeWidgetItem,
)

from src.core.data_items import CAUTION_ITEMS, FORBIDDEN_ITEMS, SAFE_ITEMS, DataItem
from src.ui.data_tree import DataTree
from src.utils.file_ops import collect_files, count_size

_KB = 1024
_MB = _KB * _KB
_MAX_FILE_PREVIEW = 12
_RIGHT_PANEL_MIN_WIDTH = 340

_SAFETY_META = {
    "safe": {
        "label": "安全",
        "bg": "#DCFCE7",
        "fg": "#166534",
        "advice": "建议迁移；跨版本兼容性通常较好。",
    },
    "caution": {
        "label": "谨慎",
        "bg": "#FEF3C7",
        "fg": "#92400E",
        "advice": "导入前请确认来源可信；导入后如出现异常可使用“回滚”恢复。",
    },
    "forbidden": {
        "label": "禁止",
        "bg": "#FEE2E2",
        "fg": "#991B1B",
        "advice": "禁止直接复制/导入导出；请使用“user.ini extern 合并”迁移 extern_* 段落。",
    },
}


def _format_size(size: int) -> str:
    if size < _KB:
        return f"{size} B"
    if size < _MB:
        return f"{size / _KB:.1f} KB"
    return f"{size / _MB:.1f} MB"


def _badge_html(label: str, bg: str, fg: str) -> str:
    safe_label = escape(label)
    return (
        f'<span style="background:{bg};color:{fg};padding:2px 8px;'
        'border-radius:999px;font-size:11px;">'
        f"{safe_label}</span>"
    )


def _welcome_html() -> str:
    return """
<h3>数据项说明</h3>
<p>点击左侧任意数据项，可在右侧查看：用途、包含路径、风险提示，以及当前 T0002 目录中的文件状态。</p>
<p><b>重要：</b>导入/回滚前请先完全关闭通达信主程序。</p>
"""


def _group_html(safety: str) -> str:
    mapping = {
        "safe": ("安全项目", len(SAFE_ITEMS), "通常跨版本兼容，默认全选。"),
        "caution": ("谨慎项目", len(CAUTION_ITEMS), "不同版本/不同券商环境可能不兼容，默认不选。"),
        "forbidden": ("禁止项目", len(FORBIDDEN_ITEMS), "仅提示，不允许直接复制。"),
    }
    title, count, hint = mapping.get(safety, ("分组", 0, ""))
    meta = _SAFETY_META.get(safety, _SAFETY_META["caution"])
    badge = _badge_html(meta["label"], meta["bg"], meta["fg"])
    return f"""
<h3>{escape(title)} {badge}</h3>
<p>共 <b>{count}</b> 个数据项。{escape(hint)}</p>
"""


def _files_preview_html(t0002_path: Path, files: list[Path]) -> str:
    rels = [str(p.relative_to(t0002_path)).replace("\\\\", "/") for p in files]
    rels.sort()
    shown = rels[:_MAX_FILE_PREVIEW]
    items = "".join(f"<li><code>{escape(x)}</code></li>" for x in shown)
    tail = ""
    if len(rels) > _MAX_FILE_PREVIEW:
        tail = f"<p style='color:#64748B'>… 还有 {len(rels) - _MAX_FILE_PREVIEW} 个文件未显示</p>"
    return f"<ul>{items}</ul>{tail}"


class DataPanel(QWidget):
    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self._t0002_path: Path | None = None
        self._tree = DataTree()
        self._desc = QTextBrowser()
        self._desc.setOpenExternalLinks(False)
        self._desc.setMinimumWidth(_RIGHT_PANEL_MIN_WIDTH)
        self._desc.setHtml(_welcome_html())

        splitter = QSplitter(Qt.Orientation.Horizontal)
        splitter.addWidget(self._build_left())
        splitter.addWidget(self._desc)
        splitter.setStretchFactor(0, 3)
        splitter.setStretchFactor(1, 2)

        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.addWidget(splitter)

        self._tree.currentItemChanged.connect(self._on_current_item_changed)
        self._tree.itemChanged.connect(self._on_item_changed)

    # ------------------------------------------------------------------ #
    # public API
    # ------------------------------------------------------------------ #

    def set_t0002_path(self, path: Path | None) -> None:
        self._t0002_path = path
        self._tree.set_t0002_path(path)
        self._render_current()

    def selected_items(self) -> list[DataItem]:
        return self._tree.selected_items()

    # ------------------------------------------------------------------ #
    # UI
    # ------------------------------------------------------------------ #

    def _build_left(self) -> QWidget:
        left = QWidget()
        layout = QVBoxLayout(left)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(self._tree)

        btn_row = QHBoxLayout()
        safe_btn = QPushButton("全选安全项")
        safe_btn.clicked.connect(self._tree.select_all_safe)
        btn_row.addWidget(safe_btn)

        clear_btn = QPushButton("清空选择")
        clear_btn.clicked.connect(self._tree.clear_all)
        btn_row.addWidget(clear_btn)

        btn_row.addStretch()
        layout.addLayout(btn_row)
        return left

    # ------------------------------------------------------------------ #
    # render
    # ------------------------------------------------------------------ #

    def _render_current(self) -> None:
        self._render_item(self._tree.currentItem())

    def _render_item(self, item: QTreeWidgetItem | None) -> None:
        if item is None:
            self._desc.setHtml(_welcome_html())
            return

        item_id = item.data(0, Qt.ItemDataRole.UserRole)
        if not isinstance(item_id, str):
            self._desc.setHtml(_welcome_html())
            return

        if item_id.startswith("group:"):
            self._desc.setHtml(_group_html(item_id.split(":", 1)[1]))
            return

        data_item = self._tree.get_data_item(item_id)
        if data_item is None:
            self._desc.setHtml(_welcome_html())
            return

        self._desc.setHtml(self._data_item_html(data_item, item))

    def _data_item_html(self, data_item: DataItem, item: QTreeWidgetItem) -> str:
        meta = _SAFETY_META[data_item.safety_level]
        badge = _badge_html(meta["label"], meta["bg"], meta["fg"])
        checked = (
            (item.flags() & Qt.ItemFlag.ItemIsUserCheckable)
            and item.checkState(0) == Qt.CheckState.Checked
        )
        checked_text = "已勾选" if checked else "未勾选"

        paths = "".join(f"<li><code>{escape(p)}</code></li>" for p in data_item.paths)
        status_html = self._status_html(data_item)

        extra = ""
        if data_item.id == "user_ini_forbidden":
            extra = "<p><b>提示：</b>请在主界面点击“user.ini extern 合并”。</p>"

        return f"""
<h3>{escape(data_item.name)} {badge}</h3>
<p style="color:#64748B">{escape(checked_text)}</p>
<h4>用途说明</h4>
<p>{escape(data_item.description)}</p>
{extra}
<h4>包含路径</h4>
<ul>{paths}</ul>
<h4>文件状态</h4>
{status_html}
<h4>操作建议</h4>
<p>{escape(meta["advice"])}</p>
"""

    def _status_html(self, data_item: DataItem) -> str:
        if self._t0002_path is None:
            return "<p style='color:#64748B'>未选择 T0002 目录，无法统计文件状态。</p>"

        files = collect_files(self._t0002_path, data_item.paths)
        if not files:
            return "<p style='color:#64748B'>（未找到匹配文件）</p>"

        total_size = count_size(files)
        summary = f"{len(files)} 个文件 / {_format_size(total_size)}"
        preview = _files_preview_html(self._t0002_path, files)
        return f"<p><b>{escape(summary)}</b></p>{preview}"

    # ------------------------------------------------------------------ #
    # slots
    # ------------------------------------------------------------------ #

    def _on_current_item_changed(self, current, _previous) -> None:
        self._render_item(current)

    def _on_item_changed(self, item: QTreeWidgetItem, column: int) -> None:
        if column != 0:
            return
        if item is self._tree.currentItem():
            self._render_item(item)
