"""进度对话框"""
from __future__ import annotations
from PyQt6.QtWidgets import QDialog, QVBoxLayout, QLabel, QProgressBar, QPushButton, QTextEdit
from PyQt6.QtCore import Qt


class ProgressDialog(QDialog):
    def __init__(self, title: str, parent=None) -> None:
        super().__init__(parent)
        self.setWindowTitle(title)
        self.setMinimumWidth(480)
        self.setWindowFlags(
            self.windowFlags() & ~Qt.WindowType.WindowContextHelpButtonHint
        )
        self._cancelled = False

        layout = QVBoxLayout(self)

        self._status_label = QLabel("准备中…")
        layout.addWidget(self._status_label)

        self._progress = QProgressBar()
        self._progress.setRange(0, 100)
        layout.addWidget(self._progress)

        self._log = QTextEdit()
        self._log.setReadOnly(True)
        self._log.setFixedHeight(160)
        layout.addWidget(self._log)

        self._cancel_btn = QPushButton("取消")
        self._cancel_btn.clicked.connect(self._on_cancel)
        layout.addWidget(self._cancel_btn, alignment=Qt.AlignmentFlag.AlignRight)

    def update_progress(self, filename: str, done: int, total: int) -> None:
        pct = int(done / total * 100) if total > 0 else 0
        self._progress.setValue(pct)
        self._status_label.setText(f"正在处理：{filename}")
        self._log.append(filename)

    def set_finished(self, message: str = "操作完成") -> None:
        self._progress.setValue(100)
        self._status_label.setText(message)
        self._cancel_btn.setText("关闭")
        self._cancel_btn.clicked.disconnect()
        self._cancel_btn.clicked.connect(self.accept)

    def set_error(self, message: str) -> None:
        self._status_label.setText(f"错误：{message}")
        self._log.append(f"[错误] {message}")
        self._cancel_btn.setText("关闭")
        self._cancel_btn.clicked.disconnect()
        self._cancel_btn.clicked.connect(self.reject)

    def is_cancelled(self) -> bool:
        return self._cancelled

    def _on_cancel(self) -> None:
        self._cancelled = True
        self._status_label.setText("正在取消…")
        self._cancel_btn.setEnabled(False)
