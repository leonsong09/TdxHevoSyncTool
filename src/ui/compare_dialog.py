"""两套通达信 T0002 对比/导入对话框"""
from __future__ import annotations

from pathlib import Path

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import (
    QComboBox,
    QDialog,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QMessageBox,
    QPushButton,
    QVBoxLayout,
)

from src.core.compare import (
    CONFLICT_LEFT,
    CONFLICT_MTIME,
    CONFLICT_RIGHT,
    MODE_BI_MISSING,
    MODE_BI_SYNC,
    MODE_LEFT_TO_RIGHT,
    MODE_RIGHT_TO_LEFT,
    STRATEGY_DIFF,
    STRATEGY_FULL,
    STRATEGY_MISSING,
    CompareResult,
    TransferPlan,
    build_transfer_plan,
)
from src.core.tdx_process import assert_tdx_not_running
from src.ui.compare_view import CompareView
from src.ui.compare_workers import CompareWorker, TransferOutcome, TransferWorker
from src.ui.path_selector import PathSelector
from src.ui.progress_dialog import ProgressDialog
from src.ui.rollback_panel import RollbackPanel


class CompareDialog(QDialog):
    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.setWindowTitle("对比/导入（两版本）")
        self.setMinimumSize(980, 720)
        self.setWindowFlags(self.windowFlags() & ~Qt.WindowType.WindowContextHelpButtonHint)

        self._left_t0002: Path | None = None
        self._right_t0002: Path | None = None
        self._compare: CompareResult | None = None

        self._compare_worker: CompareWorker | None = None
        self._transfer_worker: TransferWorker | None = None
        self._progress_dlg: ProgressDialog | None = None

        self._build_ui()

    # ------------------------------------------------------------------ #
    # UI
    # ------------------------------------------------------------------ #

    def _build_ui(self) -> None:
        root = QVBoxLayout(self)
        root.setSpacing(8)
        root.addWidget(self._build_path_group())
        root.addWidget(self._build_options_group())
        self._view = CompareView()
        root.addWidget(self._view, stretch=1)
        self._rollback_panel = RollbackPanel()
        root.addWidget(self._rollback_panel)
        self._update_option_states()

    def _build_path_group(self) -> QGroupBox:
        box = QGroupBox("左右两侧路径")
        layout = QVBoxLayout(box)

        left_row = QHBoxLayout()
        left_row.addWidget(QLabel("左侧："))
        self._left_selector = PathSelector(allow_root=True)
        self._left_selector.path_changed.connect(self._on_left_changed)
        left_row.addWidget(self._left_selector, stretch=1)
        layout.addLayout(left_row)

        right_row = QHBoxLayout()
        right_row.addWidget(QLabel("右侧："))
        self._right_selector = PathSelector(allow_root=True)
        self._right_selector.path_changed.connect(self._on_right_changed)
        right_row.addWidget(self._right_selector, stretch=1)
        layout.addLayout(right_row)

        btn_row = QHBoxLayout()
        swap_btn = QPushButton("交换左右")
        swap_btn.setToolTip("交换左右两侧路径")
        swap_btn.clicked.connect(self._on_swap)
        btn_row.addWidget(swap_btn)
        btn_row.addStretch()
        layout.addLayout(btn_row)
        return box

    def _build_options_group(self) -> QGroupBox:
        box = QGroupBox("模式与策略")
        layout = QVBoxLayout(box)

        row1 = QHBoxLayout()
        row1.addWidget(QLabel("模式："))
        self._mode_combo = QComboBox()
        self._mode_combo.addItem("左 → 右（单向导入）", MODE_LEFT_TO_RIGHT)
        self._mode_combo.addItem("右 → 左（单向导入）", MODE_RIGHT_TO_LEFT)
        self._mode_combo.addItem("双向：仅补齐缺失", MODE_BI_MISSING)
        self._mode_combo.addItem("双向：覆盖同步（含冲突）", MODE_BI_SYNC)
        self._mode_combo.currentIndexChanged.connect(self._update_option_states)
        row1.addWidget(self._mode_combo, stretch=1)

        self._compare_btn = QPushButton("开始对比")
        self._compare_btn.setObjectName("primaryButton")
        self._compare_btn.clicked.connect(self._on_compare)
        row1.addWidget(self._compare_btn)
        layout.addLayout(row1)

        row2 = QHBoxLayout()
        row2.addWidget(QLabel("单向策略："))
        self._strategy_combo = QComboBox()
        self._strategy_combo.addItem("仅导入差异（缺失+冲突）", STRATEGY_DIFF)
        self._strategy_combo.addItem("仅补齐缺失", STRATEGY_MISSING)
        self._strategy_combo.addItem("全量覆盖", STRATEGY_FULL)
        row2.addWidget(self._strategy_combo, stretch=1)

        row2.addWidget(QLabel("冲突规则："))
        self._conflict_combo = QComboBox()
        self._conflict_combo.addItem("按修改时间较新", CONFLICT_MTIME)
        self._conflict_combo.addItem("以左为准", CONFLICT_LEFT)
        self._conflict_combo.addItem("以右为准", CONFLICT_RIGHT)
        row2.addWidget(self._conflict_combo, stretch=1)

        self._transfer_btn = QPushButton("执行导入/同步")
        self._transfer_btn.setObjectName("warningButton")
        self._transfer_btn.setEnabled(False)
        self._transfer_btn.clicked.connect(self._on_transfer)
        row2.addWidget(self._transfer_btn)
        layout.addLayout(row2)

        return box

    # ------------------------------------------------------------------ #
    # state helpers
    # ------------------------------------------------------------------ #

    def _invalidate_compare(self) -> None:
        self._compare = None
        self._view.set_compare_result(None)
        self._transfer_btn.setEnabled(False)
        self._rollback_panel.clear()

    def _update_option_states(self) -> None:
        mode = self._current_mode()
        self._strategy_combo.setEnabled(mode in {MODE_LEFT_TO_RIGHT, MODE_RIGHT_TO_LEFT})
        self._conflict_combo.setEnabled(mode == MODE_BI_SYNC)

    def _current_mode(self) -> str:
        return str(self._mode_combo.currentData())

    def _current_strategy(self) -> str:
        return str(self._strategy_combo.currentData())

    def _current_conflict_policy(self) -> str:
        return str(self._conflict_combo.currentData())

    # ------------------------------------------------------------------ #
    # slots
    # ------------------------------------------------------------------ #

    def _on_left_changed(self, path: Path) -> None:
        self._left_t0002 = path
        self._rollback_panel.set_targets(self._left_t0002, self._right_t0002)
        self._invalidate_compare()

    def _on_right_changed(self, path: Path) -> None:
        self._right_t0002 = path
        self._rollback_panel.set_targets(self._left_t0002, self._right_t0002)
        self._invalidate_compare()

    def _on_swap(self) -> None:
        if not self._left_t0002 or not self._right_t0002:
            return
        left = self._left_t0002
        right = self._right_t0002
        self._left_selector.set_path(right)
        self._right_selector.set_path(left)

    def _on_compare(self) -> None:
        if self._left_t0002 is None or self._right_t0002 is None:
            QMessageBox.warning(self, "路径未设置", "请先选择左右两侧路径。")
            return

        warn = self._tdx_running_warning()
        if warn and QMessageBox.question(self, "通达信正在运行", warn + "\n\n仍要继续对比吗？") != QMessageBox.StandardButton.Yes:
            return

        self._progress_dlg = ProgressDialog("对比中", self)
        self._compare_worker = CompareWorker(self._left_t0002, self._right_t0002)
        self._compare_worker.progress.connect(self._progress_dlg.update_progress)
        self._compare_worker.finished.connect(self._on_compare_done)
        self._compare_worker.error.connect(self._on_worker_error)
        self._compare_worker.start()
        self._progress_dlg.exec()

    def _on_compare_done(self, result: object) -> None:
        if not isinstance(result, CompareResult):
            self._on_worker_error("对比结果类型错误。")
            return
        self._compare = result
        self._view.set_compare_result(result)
        self._transfer_btn.setEnabled(True)
        if self._progress_dlg:
            self._progress_dlg.set_finished("对比完成")

    def _on_transfer(self) -> None:
        if self._compare is None or self._left_t0002 is None or self._right_t0002 is None:
            QMessageBox.warning(self, "未对比", "请先点击“开始对比”。")
            return

        warn = self._tdx_running_warning()
        if warn:
            QMessageBox.warning(self, "通达信正在运行", "导入/同步前请先关闭对应通达信实例。\n\n" + warn)
            return

        selected_ids = self._view.selected_item_ids()
        plan = self._build_plan(selected_ids)
        if plan.total_files() == 0:
            QMessageBox.information(self, "无需导入", "当前选择下没有需要导入的文件。")
            return

        confirm = QMessageBox.question(
            self,
            "确认导入/同步",
            self._plan_summary_text(plan),
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
        )
        if confirm != QMessageBox.StandardButton.Yes:
            return

        self._progress_dlg = ProgressDialog("导入/同步中", self)
        self._transfer_worker = TransferWorker(plan, self._left_t0002, self._right_t0002, selected_ids)
        self._transfer_worker.progress.connect(self._progress_dlg.update_progress)
        self._transfer_worker.finished.connect(self._on_transfer_done)
        self._transfer_worker.error.connect(self._on_worker_error)
        self._transfer_worker.start()
        self._progress_dlg.exec()

    def _on_transfer_done(self, outcome: object) -> None:
        if not isinstance(outcome, TransferOutcome):
            self._on_worker_error("导入结果类型错误。")
            return
        left_backup = Path(outcome.left_backup_dir) if outcome.left_backup_dir else None
        right_backup = Path(outcome.right_backup_dir) if outcome.right_backup_dir else None
        self._rollback_panel.set_backups(left_backup, right_backup)

        if self._progress_dlg:
            self._progress_dlg.set_finished(outcome.summary)

    def _on_worker_error(self, msg: str) -> None:
        if self._progress_dlg:
            self._progress_dlg.set_error(msg)
        else:
            QMessageBox.critical(self, "错误", msg)

    # ------------------------------------------------------------------ #
    # import helpers
    # ------------------------------------------------------------------ #

    def _build_plan(self, selected_ids: list[str]) -> TransferPlan:
        mode = self._current_mode()
        strategy = self._current_strategy()
        conflict_policy = self._current_conflict_policy()
        return build_transfer_plan(self._compare, selected_ids, mode, strategy, conflict_policy)

    def _plan_summary_text(self, plan: TransferPlan) -> str:
        parts = []
        if plan.left_to_right:
            parts.append(f"写入右侧：{len(plan.left_to_right)} 个文件")
        if plan.right_to_left:
            parts.append(f"写入左侧：{len(plan.right_to_left)} 个文件")
        return (
            "即将执行导入/同步：\n\n"
            + "\n".join(parts)
            + "\n\n导入前会自动备份被覆盖文件，可在窗口底部回滚。\n确认继续吗？"
        )

    def _tdx_running_warning(self) -> str:
        lines: list[str] = []
        for label, path in (("左侧", self._left_t0002), ("右侧", self._right_t0002)):
            if path is None:
                continue
            status = assert_tdx_not_running(path)
            if status.is_running:
                lines.append(f"{label}：{status.process_name} (PID {status.pid})")
        return "\n".join(lines)
