"""对比/导入后台线程"""
from __future__ import annotations

import shutil
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

from PyQt6.QtCore import QThread, pyqtSignal

from src.core.compare import TransferPlan, compare_t0002
from src.core.data_items import ALL_DATA_ITEMS
from src.core.importer import import_from_folder
from src.utils.file_ops import safe_copy_file, verify_copies

_TEMP_DIR_NAME = "temp"
_TRANSFER_ROOT_NAME = "tdx_hevo_transfer"
_STAGE_L2R = "L2R"
_STAGE_R2L = "R2L"


@dataclass(frozen=True)
class TransferOutcome:
    summary: str
    staging_root: str
    left_backup_dir: str | None
    right_backup_dir: str | None


class CompareWorker(QThread):
    progress = pyqtSignal(str, int, int)
    finished = pyqtSignal(object)  # CompareResult
    error = pyqtSignal(str)

    def __init__(self, left_t0002: Path, right_t0002: Path) -> None:
        super().__init__()
        self._left_t0002 = left_t0002
        self._right_t0002 = right_t0002

    def run(self) -> None:
        try:
            result = compare_t0002(
                self._left_t0002,
                self._right_t0002,
                ALL_DATA_ITEMS,
                progress_cb=lambda f, d, t: self.progress.emit(f, d, t),
            )
            self.finished.emit(result)
        except Exception as exc:
            self.error.emit(str(exc))


class TransferWorker(QThread):
    progress = pyqtSignal(str, int, int)
    finished = pyqtSignal(object)  # TransferOutcome
    error = pyqtSignal(str)

    def __init__(
        self,
        plan: TransferPlan,
        left_t0002: Path,
        right_t0002: Path,
        selected_item_ids: list[str],
    ) -> None:
        super().__init__()
        self._plan = plan
        self._left_t0002 = left_t0002
        self._right_t0002 = right_t0002
        self._selected_item_ids = selected_item_ids

    def run(self) -> None:
        staging_root = _make_staging_root()
        try:
            outcome = self._run_with_staging(staging_root)
            shutil.rmtree(staging_root, ignore_errors=True)
            self.finished.emit(outcome)
        except Exception as exc:
            self.error.emit(f"{exc}\n\n临时目录已保留：{staging_root}")

    def _run_with_staging(self, staging_root: Path) -> TransferOutcome:
        staging_root.mkdir(parents=True, exist_ok=True)

        total = self._plan.total_files() * 2
        done = 0
        left_backup: str | None = None
        right_backup: str | None = None

        if self._plan.left_to_right:
            stage_dir = staging_root / _STAGE_L2R
            done = self._stage_files(self._left_t0002, self._plan.left_to_right, stage_dir, done, total)
            _imported_items, backup_dir = import_from_folder(
                stage_dir,
                self._right_t0002,
                selected_item_ids=self._selected_item_ids,
                progress_cb=lambda f, d, t: self._progress_import(f, done, d, total),
            )
            done += len(self._plan.left_to_right)
            right_backup = str(backup_dir)

        if self._plan.right_to_left:
            stage_dir = staging_root / _STAGE_R2L
            done = self._stage_files(self._right_t0002, self._plan.right_to_left, stage_dir, done, total)
            _imported_items, backup_dir = import_from_folder(
                stage_dir,
                self._left_t0002,
                selected_item_ids=self._selected_item_ids,
                progress_cb=lambda f, d, t: self._progress_import(f, done, d, total),
            )
            done += len(self._plan.right_to_left)
            left_backup = str(backup_dir)

        summary = self._build_summary()
        return TransferOutcome(
            summary=summary,
            staging_root=str(staging_root),
            left_backup_dir=left_backup,
            right_backup_dir=right_backup,
        )

    def _build_summary(self) -> str:
        parts: list[str] = []
        if self._plan.left_to_right:
            parts.append(f"写入右侧 {len(self._plan.left_to_right)} 个文件")
        if self._plan.right_to_left:
            parts.append(f"写入左侧 {len(self._plan.right_to_left)} 个文件")
        return "，".join(parts) if parts else "没有需要导入的文件"

    def _stage_files(
        self,
        source_t0002: Path,
        rels: tuple[str, ...],
        stage_dir: Path,
        done: int,
        total: int,
    ) -> int:
        originals: list[Path] = []
        copies: list[Path] = []
        for rel in rels:
            src = source_t0002 / rel
            dst = stage_dir / rel
            safe_copy_file(src, dst)
            originals.append(src)
            copies.append(dst)
            done += 1
            self.progress.emit(rel, done, total)

        mismatches = verify_copies(originals, copies)
        if mismatches:
            names = ", ".join(str(o.name) for o, _ in mismatches[:5])
            raise RuntimeError(f"临时复制校验失败（SHA256 不一致）：{names}")

        return done

    def _progress_import(self, filename: str, offset: int, done: int, total: int) -> None:
        self.progress.emit(filename, offset + done, total)


def _make_staging_root() -> Path:
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    return Path.cwd() / _TEMP_DIR_NAME / _TRANSFER_ROOT_NAME / ts
