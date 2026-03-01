"""回滚面板：展示左右备份并支持一键回滚"""
from __future__ import annotations

from pathlib import Path

from PyQt6.QtWidgets import QGroupBox, QHBoxLayout, QLabel, QMessageBox, QPushButton

from src.core.importer import rollback
from src.core.tdx_process import assert_tdx_not_running


class RollbackPanel(QGroupBox):
    def __init__(self, parent=None) -> None:
        super().__init__("回滚（仅对本次导入有效）", parent)
        self._left_t0002: Path | None = None
        self._right_t0002: Path | None = None
        self._left_backup_dir: Path | None = None
        self._right_backup_dir: Path | None = None

        layout = QHBoxLayout(self)
        self._left_label = QLabel("左侧备份：—")
        layout.addWidget(self._left_label, stretch=1)
        self._left_btn = QPushButton("回滚左侧")
        self._left_btn.setEnabled(False)
        self._left_btn.clicked.connect(self._on_rollback_left)
        layout.addWidget(self._left_btn)

        self._right_label = QLabel("右侧备份：—")
        layout.addWidget(self._right_label, stretch=1)
        self._right_btn = QPushButton("回滚右侧")
        self._right_btn.setEnabled(False)
        self._right_btn.clicked.connect(self._on_rollback_right)
        layout.addWidget(self._right_btn)

    def set_targets(self, left_t0002: Path | None, right_t0002: Path | None) -> None:
        self._left_t0002 = left_t0002
        self._right_t0002 = right_t0002

    def set_backups(self, left_backup: Path | None, right_backup: Path | None) -> None:
        self._left_backup_dir = left_backup
        self._right_backup_dir = right_backup
        self._refresh_ui()

    def clear(self) -> None:
        self.set_backups(None, None)

    def _refresh_ui(self) -> None:
        self._left_label.setText(f"左侧备份：{self._left_backup_dir}" if self._left_backup_dir else "左侧备份：—")
        self._right_label.setText(f"右侧备份：{self._right_backup_dir}" if self._right_backup_dir else "右侧备份：—")
        self._left_btn.setEnabled(self._left_backup_dir is not None)
        self._right_btn.setEnabled(self._right_backup_dir is not None)

    def _on_rollback_left(self) -> None:
        self._rollback_side("左侧", self._left_backup_dir, self._left_t0002)

    def _on_rollback_right(self) -> None:
        self._rollback_side("右侧", self._right_backup_dir, self._right_t0002)

    def _rollback_side(self, side: str, backup_dir: Path | None, t0002_path: Path | None) -> None:
        if backup_dir is None or t0002_path is None:
            return

        status = assert_tdx_not_running(t0002_path)
        if status.is_running:
            QMessageBox.warning(
                self,
                "通达信正在运行",
                f"检测到通达信正在运行：{status.process_name} (PID {status.pid})\n\n请先关闭后再回滚。",
            )
            return

        confirm = QMessageBox.question(
            self,
            f"确认回滚{side}",
            f"将从以下备份回滚到 {side} T0002：\n{backup_dir}\n\n确认继续吗？",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
        )
        if confirm != QMessageBox.StandardButton.Yes:
            return

        try:
            rollback(backup_dir, t0002_path)
            QMessageBox.information(self, "回滚成功", f"{side} 已成功回滚。")
        except Exception as exc:
            QMessageBox.critical(self, "回滚失败", str(exc))
