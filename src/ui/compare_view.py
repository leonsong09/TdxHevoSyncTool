"""对比视图：左侧对比树 + 右侧说明/差异面板"""
from __future__ import annotations

from html import escape

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import (
    QGroupBox,
    QHBoxLayout,
    QPushButton,
    QSplitter,
    QTextBrowser,
    QVBoxLayout,
    QWidget,
)

from src.core.compare import CompareResult
from src.core.data_items import CAUTION_ITEMS, FORBIDDEN_ITEMS, SAFE_ITEMS, DataItem
from src.ui.compare_tree import CompareTree

_KB = 1024
_MB = _KB * _KB
_MAX_PREVIEW = 12
_RIGHT_PANEL_MIN_WIDTH = 380

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
        "advice": "导入前请确认来源可信；导入后如异常可使用回滚恢复。",
    },
    "forbidden": {
        "label": "禁止",
        "bg": "#FEE2E2",
        "fg": "#991B1B",
        "advice": "禁止直接复制/导入/导出；请使用 user.ini 定向同步，普通 section 仅替换同名键，extern_* 额外追加缺失键。",
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


def _list_preview(title: str, items: tuple[str, ...]) -> str:
    if not items:
        return ""
    shown = items[:_MAX_PREVIEW]
    lis = "".join(f"<li><code>{escape(x)}</code></li>" for x in shown)
    tail = ""
    if len(items) > _MAX_PREVIEW:
        tail = f"<p style='color:#64748B'>— 还有 {len(items) - _MAX_PREVIEW} 项未显示</p>"
    return f"<h4>{escape(title)}</h4><ul>{lis}</ul>{tail}"


def _welcome_html() -> str:
    return """
<h3>对比/导入（两版本）</h3>
<ol>
  <li>分别选择左右两侧路径（安装根目录或 T0002）。</li>
  <li>点击“开始对比”，查看差异。</li>
  <li>选择模式/策略，点击“执行导入/同步”。</li>
</ol>
<p style="color:#64748B">提示：导入前会自动备份被覆盖文件；如异常可在本窗口回滚。</p>
"""


class CompareView(QWidget):
    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self._compare: CompareResult | None = None
        self.tree = CompareTree()
        self._detail = QTextBrowser()
        self._detail.setOpenExternalLinks(False)
        self._detail.setMinimumWidth(_RIGHT_PANEL_MIN_WIDTH)
        self._detail.setHtml(_welcome_html())

        splitter = QSplitter(Qt.Orientation.Horizontal)
        splitter.addWidget(self._build_left())
        splitter.addWidget(self._detail)
        splitter.setStretchFactor(0, 3)
        splitter.setStretchFactor(1, 2)

        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.addWidget(splitter)

        self.tree.currentItemChanged.connect(self._on_current_item_changed)

    def set_compare_result(self, compare: CompareResult | None) -> None:
        self._compare = compare
        self.tree.set_compare_result(compare)
        self._detail.setHtml(_welcome_html())
        self._render_current()

    def selected_item_ids(self) -> list[str]:
        return self.tree.selected_item_ids()

    # ------------------------------------------------------------------ #
    # UI
    # ------------------------------------------------------------------ #

    def _build_left(self) -> QGroupBox:
        box = QGroupBox("数据项（勾选后参与导入）")
        layout = QVBoxLayout(box)
        layout.addWidget(self.tree)

        btn_row = QHBoxLayout()
        safe_btn = QPushButton("全选安全项")
        safe_btn.clicked.connect(self.tree.select_all_safe)
        btn_row.addWidget(safe_btn)

        clear_btn = QPushButton("清空选择")
        clear_btn.clicked.connect(self.tree.clear_all)
        btn_row.addWidget(clear_btn)

        btn_row.addStretch()
        layout.addLayout(btn_row)
        return box

    # ------------------------------------------------------------------ #
    # render
    # ------------------------------------------------------------------ #

    def _render_current(self) -> None:
        self._render_item(self.tree.currentItem())

    def _render_item(self, item) -> None:
        if item is None:
            self._detail.setHtml(_welcome_html())
            return

        item_id = item.data(0, Qt.ItemDataRole.UserRole)
        if not isinstance(item_id, str):
            self._detail.setHtml(_welcome_html())
            return

        if item_id.startswith("group:"):
            safety = item_id.split(":", 1)[1]
            self._detail.setHtml(self._group_html(safety))
            return

        data_item = self.tree.get_data_item(item_id)
        if data_item is None:
            self._detail.setHtml(_welcome_html())
            return

        self._detail.setHtml(self._item_html(data_item))

    def _group_html(self, safety: str) -> str:
        mapping = {
            "safe": ("安全项目", len(SAFE_ITEMS), "通常跨版本兼容，推荐优先迁移。"),
            "caution": ("谨慎项目", len(CAUTION_ITEMS), "不同版本/券商环境可能不兼容，建议先小范围验证。"),
            "forbidden": ("禁止项目", len(FORBIDDEN_ITEMS), "仅提示，不允许直接导入/导出。"),
        }
        title, count, hint = mapping.get(safety, ("分组", 0, ""))
        meta = _SAFETY_META.get(safety, _SAFETY_META["caution"])
        badge = _badge_html(meta["label"], meta["bg"], meta["fg"])
        return f"""
<h3>{escape(title)} {badge}</h3>
<p>共 <b>{count}</b> 项。{escape(hint)}</p>
"""

    def _item_html(self, data_item: DataItem) -> str:
        meta = _SAFETY_META[data_item.safety_level]
        badge = _badge_html(meta["label"], meta["bg"], meta["fg"])
        paths = "".join(f"<li><code>{escape(p)}</code></li>" for p in data_item.paths)

        diff_html = "<p style='color:#64748B'>（尚未对比）</p>"
        if self._compare is not None:
            item_cmp = self._compare.by_item_id.get(data_item.id)
            if item_cmp:
                diff_html = f"""
<h4>左右统计</h4>
<ul>
  <li>左侧：<b>{len(item_cmp.left_files)}</b> 文件 / {_format_size(item_cmp.left_total_size)}</li>
  <li>右侧：<b>{len(item_cmp.right_files)}</b> 文件 / {_format_size(item_cmp.right_total_size)}</li>
</ul>
{_list_preview("仅左侧存在", item_cmp.only_left)}
{_list_preview("仅右侧存在", item_cmp.only_right)}
{_list_preview("同名不同内容（冲突）", item_cmp.conflicts)}
"""

        extra = ""
        if data_item.id == "user_ini_forbidden":
            extra = "<p><b>提示：</b>请使用主界面的 <code>user.ini 定向同步</code>。</p>"

        return f"""
<h3>{escape(data_item.name)} {badge}</h3>
<h4>用途说明</h4>
<p>{escape(data_item.description)}</p>
{extra}
<h4>包含路径</h4>
<ul>{paths}</ul>
{diff_html}
<h4>操作建议</h4>
<p>{escape(meta["advice"])}</p>
"""

    # ------------------------------------------------------------------ #
    # slots
    # ------------------------------------------------------------------ #

    def _on_current_item_changed(self, current, _previous) -> None:
        self._render_item(current)
