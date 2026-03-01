"""后台任务线程（导入/导出）"""
from __future__ import annotations

from pathlib import Path

from PyQt6.QtCore import QThread, pyqtSignal

from src.core.data_items import DataItem
from src.core.exporter import ExportError, export_to_folder, export_to_zip
from src.core.importer import ImportError, import_from_folder, import_from_zip


class ExportWorker(QThread):
    progress = pyqtSignal(str, int, int)
    finished = pyqtSignal(str)
    error = pyqtSignal(str)

    def __init__(self, mode: str, t0002_path: Path, items: list[DataItem], output_dir: Path) -> None:
        super().__init__()
        self._mode = mode  # "zip" | "folder"
        self._t0002_path = t0002_path
        self._items = items
        self._output_dir = output_dir

    def run(self) -> None:
        try:
            if self._mode == "zip":
                result = export_to_zip(
                    self._t0002_path,
                    self._items,
                    self._output_dir,
                    progress_cb=lambda f, d, t: self.progress.emit(f, d, t),
                )
            else:
                result = export_to_folder(
                    self._t0002_path,
                    self._items,
                    self._output_dir,
                    progress_cb=lambda f, d, t: self.progress.emit(f, d, t),
                )
            self.finished.emit(str(result))
        except ExportError as exc:
            self.error.emit(str(exc))
        except Exception as exc:
            self.error.emit(f"未知错误：{exc}")


class ImportWorker(QThread):
    progress = pyqtSignal(str, int, int)
    finished = pyqtSignal(str, str)  # (summary, backup_dir)
    error = pyqtSignal(str)

    def __init__(self, src: Path, t0002_path: Path) -> None:
        super().__init__()
        self._src = src
        self._t0002_path = t0002_path

    def run(self) -> None:
        try:
            if self._src.is_file() and self._src.suffix.lower() == ".zip":
                items, backup_dir = import_from_zip(
                    self._src,
                    self._t0002_path,
                    progress_cb=lambda f, d, t: self.progress.emit(f, d, t),
                )
            else:
                items, backup_dir = import_from_folder(
                    self._src,
                    self._t0002_path,
                    progress_cb=lambda f, d, t: self.progress.emit(f, d, t),
                )
            summary = f"成功导入 {len(items)} 个数据项"
            self.finished.emit(summary, str(backup_dir))
        except ImportError as exc:
            self.error.emit(str(exc))
        except Exception as exc:
            self.error.emit(f"未知错误：{exc}")
