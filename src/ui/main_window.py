"""主窗口"""
from __future__ import annotations
from datetime import datetime
from pathlib import Path

from PyQt6.QtWidgets import (
    QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QGroupBox, QPushButton, QTextEdit, QFileDialog,
    QMessageBox, QStatusBar,
)
from PyQt6.QtCore import QThread
from PyQt6.QtGui import QFont

from src.core.importer import rollback
from src.core.tdx_process import assert_tdx_not_running
from src.core.version import APP_NAME, APP_VERSION
from src.ui.data_panel import DataPanel
from src.ui.compare_dialog import CompareDialog
from src.ui.help_dialog import HelpDialog
from src.ui.path_selector import PathSelector
from src.ui.progress_dialog import ProgressDialog
from src.ui.userini_dialog import UserIniDialog
from src.ui.workers import ExportWorker, ImportWorker


# ─────────────────────────────── Main Window ────────────────────────────────

class MainWindow(QMainWindow):
    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle(f"{APP_NAME} v{APP_VERSION}")
        self.setMinimumSize(760, 680)
        self._t0002_path: Path | None = None
        self._last_backup_dir: Path | None = None
        self._worker: QThread | None = None
        self._progress_dlg: ProgressDialog | None = None
        self._build_ui()
        self._path_selector.refresh_instances()

    # ------------------------------------------------------------------ #
    # UI construction
    # ------------------------------------------------------------------ #

    def _build_ui(self) -> None:
        central = QWidget()
        self.setCentralWidget(central)
        root = QVBoxLayout(central)
        root.setSpacing(8)
        self._build_menu()
        self._build_path_group(root)
        self._build_data_group(root)
        self._build_operations_group(root)
        self._build_log_group(root)
        self._build_status_bar()

    def _build_menu(self) -> None:
        help_menu = self.menuBar().addMenu("帮助")
        action = help_menu.addAction("使用说明/简介…")
        action.triggered.connect(self._on_help)

    def _build_path_group(self, parent: QVBoxLayout) -> None:
        box = QGroupBox("T0002 源路径")
        layout = QVBoxLayout(box)
        self._path_selector = PathSelector()
        self._path_selector.path_changed.connect(self._on_path_changed)
        layout.addWidget(self._path_selector)
        parent.addWidget(box)

    def _build_data_group(self, parent: QVBoxLayout) -> None:
        box = QGroupBox("数据选择（右侧查看说明）")
        layout = QVBoxLayout(box)
        self._data_panel = DataPanel()
        layout.addWidget(self._data_panel)
        parent.addWidget(box, stretch=1)

    def _build_operations_group(self, parent: QVBoxLayout) -> None:
        box = QGroupBox("操作")
        layout = QHBoxLayout(box)

        self._export_zip_btn = QPushButton("导出为 ZIP")
        self._export_zip_btn.setObjectName("primaryButton")
        self._export_zip_btn.setToolTip("将选中数据项打包为 ZIP 文件")
        self._export_zip_btn.clicked.connect(self._on_export_zip)
        layout.addWidget(self._export_zip_btn)

        self._export_folder_btn = QPushButton("导出到文件夹")
        self._export_folder_btn.setToolTip("将选中数据项复制到文件夹")
        self._export_folder_btn.clicked.connect(self._on_export_folder)
        layout.addWidget(self._export_folder_btn)

        self._import_btn = QPushButton("从备份导入")
        self._import_btn.setObjectName("warningButton")
        self._import_btn.setToolTip("从备份 ZIP 或文件夹还原到当前 T0002 目录")
        self._import_btn.clicked.connect(self._on_import)
        layout.addWidget(self._import_btn)

        self._rollback_btn = QPushButton("回滚上次导入")
        self._rollback_btn.setObjectName("dangerButton")
        self._rollback_btn.setEnabled(False)
        self._rollback_btn.setToolTip("将上次导入前的自动备份恢复到 T0002 目录")
        self._rollback_btn.clicked.connect(self._on_rollback)
        layout.addWidget(self._rollback_btn)

        self._userini_btn = QPushButton("user.ini 定向同步")
        self._userini_btn.setObjectName("linkButton")
        self._userini_btn.setToolTip("按 section 定向同步 user.ini：普通 section 替换同名键，extern 额外追加缺失键")
        self._userini_btn.clicked.connect(self._on_userini)
        layout.addWidget(self._userini_btn)

        self._compare_btn = QPushButton("对比/导入（两版本）")
        self._compare_btn.setToolTip("对比两套通达信 T0002 差异，并按策略导入/同步")
        self._compare_btn.clicked.connect(self._on_compare)
        layout.addWidget(self._compare_btn)

        parent.addWidget(box)

    def _build_log_group(self, parent: QVBoxLayout) -> None:
        box = QGroupBox("操作日志")
        layout = QVBoxLayout(box)
        self._log = QTextEdit()
        self._log.setReadOnly(True)
        self._log.setFixedHeight(140)
        self._log.setFont(QFont("Consolas", 9))
        layout.addWidget(self._log)
        parent.addWidget(box)

    def _build_status_bar(self) -> None:
        self.setStatusBar(QStatusBar())
        self.statusBar().showMessage("就绪")

    # ------------------------------------------------------------------ #
    # slots
    # ------------------------------------------------------------------ #

    def _on_path_changed(self, path: Path) -> None:
        self._t0002_path = path
        self._data_panel.set_t0002_path(path)
        self._log_info(f"已选择 T0002 路径：{path}")
        self.statusBar().showMessage(str(path))

    def _on_help(self) -> None:
        HelpDialog(parent=self).exec()

    def _on_export_zip(self) -> None:
        self._run_export("zip")

    def _on_export_folder(self) -> None:
        self._run_export("folder")

    def _run_export(self, mode: str) -> None:
        if not self._check_path():
            return
        items = self._data_panel.selected_items()
        if not items:
            QMessageBox.warning(self, "未选择数据", "请至少选择一个数据项再导出。")
            return

        # 进程检测
        status = assert_tdx_not_running(self._t0002_path)
        if status.is_running:
            self._warn_tdx_running(status)
            return

        if mode == "zip":
            output_dir = QFileDialog.getExistingDirectory(self, "选择 ZIP 保存位置")
        else:
            output_dir = QFileDialog.getExistingDirectory(self, "选择备份文件夹保存位置")

        if not output_dir:
            return

        label = "导出为 ZIP" if mode == "zip" else "导出到文件夹"
        self._progress_dlg = ProgressDialog(label, self)

        self._worker = ExportWorker(mode, self._t0002_path, items, Path(output_dir))
        self._worker.progress.connect(self._progress_dlg.update_progress)
        self._worker.finished.connect(self._on_export_done)
        self._worker.error.connect(self._on_worker_error)
        self._worker.start()

        self._progress_dlg.exec()

    def _on_export_done(self, result_path: str) -> None:
        self._log_info(f"导出完成：{result_path}")
        if self._progress_dlg:
            self._progress_dlg.set_finished(f"导出完成：{result_path}")

    def _on_import(self) -> None:
        if not self._check_path():
            return

        status = assert_tdx_not_running(self._t0002_path)
        if status.is_running:
            self._warn_tdx_running(status)
            return

        src, _ = QFileDialog.getOpenFileName(
            self, "选择备份 ZIP 文件或取消后选择文件夹",
            "", "ZIP 备份 (*.zip);;所有文件 (*)"
        )
        if not src:
            # 尝试选择文件夹
            src = QFileDialog.getExistingDirectory(self, "选择备份文件夹")
        if not src:
            return

        confirm = QMessageBox.question(
            self, "确认导入",
            f"将从以下来源导入到:\n{self._t0002_path}\n\n"
            f"来源: {src}\n\n"
            "导入前将自动备份被覆盖的文件。\n确认继续？",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
        )
        if confirm != QMessageBox.StandardButton.Yes:
            return

        self._progress_dlg = ProgressDialog("导入配置", self)
        self._worker = ImportWorker(Path(src), self._t0002_path)
        self._worker.progress.connect(self._progress_dlg.update_progress)
        self._worker.finished.connect(self._on_import_done)
        self._worker.error.connect(self._on_worker_error)
        self._worker.start()
        self._progress_dlg.exec()

    def _on_import_done(self, summary: str, backup_dir: str) -> None:
        self._last_backup_dir = Path(backup_dir)
        self._rollback_btn.setEnabled(True)
        self._log_info(f"{summary}。自动备份：{backup_dir}")
        if self._progress_dlg:
            self._progress_dlg.set_finished(summary)

    def _on_rollback(self) -> None:
        if not self._last_backup_dir or not self._t0002_path:
            return
        confirm = QMessageBox.question(
            self, "确认回滚",
            f"将从以下备份回滚：\n{self._last_backup_dir}\n\n确认继续？",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
        )
        if confirm != QMessageBox.StandardButton.Yes:
            return
        try:
            rollback(self._last_backup_dir, self._t0002_path)
            self._log_info("已回滚到上次导入前的状态。")
            QMessageBox.information(self, "回滚成功", "已成功回滚。")
            self._rollback_btn.setEnabled(False)
        except Exception as exc:
            QMessageBox.critical(self, "回滚失败", str(exc))

    def _on_userini(self) -> None:
        dlg = UserIniDialog(t0002_path=self._t0002_path, parent=self)
        if self._t0002_path:
            candidate = self._t0002_path / "user.ini"
            if candidate.exists():
                self._log_info(f"提示：检测到目标 user.ini：{candidate}")
        dlg.exec()

    def _on_compare(self) -> None:
        dlg = CompareDialog(parent=self)
        dlg.exec()

    def _on_worker_error(self, msg: str) -> None:
        self._log_error(msg)
        if self._progress_dlg:
            self._progress_dlg.set_error(msg)

    # ------------------------------------------------------------------ #
    # helpers
    # ------------------------------------------------------------------ #

    def _check_path(self) -> bool:
        if self._t0002_path is None or not self._t0002_path.is_dir():
            QMessageBox.warning(self, "未设置路径", "请先选择有效的 T0002 目录。")
            return False
        return True

    def _warn_tdx_running(self, status) -> None:
        QMessageBox.warning(
            self,
            "通达信正在运行",
            f"检测到通达信主程序正在运行：\n"
            f"  进程：{status.process_name}\n"
            f"  PID：{status.pid}\n\n"
            "请先完全关闭通达信，再进行备份/还原操作，以确保数据完整性。",
        )

    def _log_info(self, msg: str) -> None:
        ts = datetime.now().strftime("%H:%M:%S")
        self._log.append(f'<span style="color:#27ae60">[{ts}]</span> {msg}')

    def _log_error(self, msg: str) -> None:
        ts = datetime.now().strftime("%H:%M:%S")
        self._log.append(f'<span style="color:#c0392b">[{ts}] 错误：{msg}</span>')
