"""导入功能 — 从 ZIP 或文件夹还原"""
from __future__ import annotations
import fnmatch
import hashlib
import json
import shutil
import zipfile
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Callable

from src.core.data_items import ITEMS_BY_ID, DataItem
from src.core.tdx_process import assert_tdx_not_running
from src.utils.file_ops import (
    collect_files,
    count_size,
    free_space,
    safe_copy_file,
)

_MAX_AUTO_BACKUPS = 3
_WILDCARD_CHARS = ("*", "?", "[")


class ImportError(Exception):  # noqa: A001
    pass


@dataclass(frozen=True)
class _ZipTarget:
    arc_name: str
    rel_path: str


def _load_manifest(data: str) -> dict:
    try:
        return json.loads(data)
    except json.JSONDecodeError as exc:
        raise ImportError(f"manifest.json 解析失败：{exc}") from exc


def _normalize_rel_path(path: str) -> str:
    normalized = path.replace("\\", "/")
    return normalized[2:] if normalized.startswith("./") else normalized


def _has_wildcard(pattern: str) -> bool:
    return any(ch in pattern for ch in _WILDCARD_CHARS)


def _zip_name_matches_pattern(zip_name: str, pattern: str) -> bool:
    zip_norm = _normalize_rel_path(zip_name)
    pat_norm = _normalize_rel_path(pattern)

    if _has_wildcard(pat_norm):
        if "/" not in pat_norm and "/" in zip_norm:
            return False
        return fnmatch.fnmatch(zip_norm.lower(), pat_norm.lower())

    prefix = pat_norm.rstrip("/")
    return zip_norm == prefix or zip_norm.startswith(prefix + "/")


def _collect_zip_targets(zip_names: list[str], items: list[DataItem]) -> list[_ZipTarget]:
    patterns = [p for item in items for p in item.paths]
    if not patterns:
        return []

    targets: list[_ZipTarget] = []
    seen: set[str] = set()

    for arc_name in zip_names:
        if arc_name == "manifest.json" or arc_name.endswith(("/", "\\")):
            continue
        rel_path = _normalize_rel_path(arc_name)
        if rel_path in seen:
            continue
        if any(_zip_name_matches_pattern(arc_name, pat) for pat in patterns):
            seen.add(rel_path)
            targets.append(_ZipTarget(arc_name=arc_name, rel_path=rel_path))

    return targets


def _zip_targets_total_size(zf: zipfile.ZipFile, targets: list[_ZipTarget]) -> int:
    return sum(zf.getinfo(t.arc_name).file_size for t in targets)


def _verify_zip_hashes(
    zf: zipfile.ZipFile,
    targets: list[_ZipTarget],
    manifest_hashes: dict[str, str],
) -> None:
    for t in targets:
        expected = manifest_hashes.get(t.arc_name) or manifest_hashes.get(t.rel_path)
        if not expected:
            raise ImportError(f"manifest.json 缺少文件哈希，无法校验：{t.rel_path}")
        actual = hashlib.sha256(zf.read(t.arc_name)).hexdigest()
        if actual != expected:
            raise ImportError(f"文件完整性校验失败：{t.rel_path}")


def _safe_dest_path(t0002_path: Path, rel_path: str) -> Path:
    dest = (t0002_path / rel_path).resolve()
    if not dest.is_relative_to(t0002_path.resolve()):
        raise ImportError(f"ZIP 内含非法路径（疑似路径穿越）：{rel_path}")
    return dest


def _extract_zip_targets(
    zf: zipfile.ZipFile,
    targets: list[_ZipTarget],
    t0002_path: Path,
    progress_cb: Callable[[str, int, int], None] | None,
) -> None:
    total = len(targets)
    for idx, t in enumerate(targets, 1):
        dest = _safe_dest_path(t0002_path, t.rel_path)
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_bytes(zf.read(t.arc_name))
        if progress_cb:
            progress_cb(Path(t.rel_path).name, idx, total)


def _auto_backup(t0002_path: Path, file_relpaths: list[str]) -> Path:
    """
    导入前将目标 T0002 中即将被覆盖的文件备份到隐藏子目录，
    保留最近 3 次。返回本次备份目录路径。
    """
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    backup_dir = t0002_path / f".tdx_backup_{timestamp}"
    backup_dir.mkdir(parents=True, exist_ok=True)

    for rel in file_relpaths:
        src = t0002_path / rel
        if src.exists():
            dst = backup_dir / rel
            safe_copy_file(src, dst)

    # 清理超出限制的旧备份
    backup_dirs = sorted(
        [d for d in t0002_path.iterdir() if d.is_dir() and d.name.startswith(".tdx_backup_")],
        key=lambda d: d.name,
    )
    for old_dir in backup_dirs[: max(0, len(backup_dirs) - _MAX_AUTO_BACKUPS)]:
        shutil.rmtree(old_dir, ignore_errors=True)

    return backup_dir


def _ensure_tdx_closed(t0002_path: Path) -> None:
    status = assert_tdx_not_running(t0002_path)
    if status.is_running:
        raise ImportError(
            f"检测到通达信正在运行（进程: {status.process_name}, PID: {status.pid}）。\n"
            "请先关闭通达信后再进行导入操作。"
        )


def import_from_zip(
    zip_path: Path,
    t0002_path: Path,
    selected_item_ids: list[str] | None = None,
    progress_cb: Callable[[str, int, int], None] | None = None,
) -> tuple[list[DataItem], Path]:
    """从 ZIP 文件导入配置，返回 (已导入数据项, 本次自动备份目录)。"""
    _ensure_tdx_closed(t0002_path)

    if not zipfile.is_zipfile(zip_path):
        raise ImportError(f"文件损坏或不是有效的 ZIP 文件：{zip_path}")

    with zipfile.ZipFile(zip_path, "r") as zf:
        zip_names = zf.namelist()

        # 读取 manifest
        if "manifest.json" not in zip_names:
            raise ImportError("ZIP 中缺少 manifest.json，无法验证数据完整性。")
        manifest = _load_manifest(zf.read("manifest.json").decode("utf-8"))
        manifest_hashes: dict[str, str] = manifest.get("file_hashes", {})
        manifest_items: list[str] = manifest.get("selected_items", [])

        # 确定要导入的项目
        import_ids = set(selected_item_ids) if selected_item_ids is not None else set(manifest_items)
        imported_items: list[DataItem] = [
            ITEMS_BY_ID[iid] for iid in import_ids if iid in ITEMS_BY_ID
        ]
        imported_items = [i for i in imported_items if i.safety_level != "forbidden"]

        targets = _collect_zip_targets(zip_names, imported_items)
        if not targets:
            raise ImportError("ZIP 中没有找到选中数据项对应的文件。")

        # 磁盘空间检测（解压前估算）
        total_size = _zip_targets_total_size(zf, targets)
        if free_space(t0002_path) < total_size:
            raise ImportError(
                f"目标磁盘空间不足：需要 {total_size // 1024 // 1024} MB，"
                f"可用 {free_space(t0002_path) // 1024 // 1024} MB。"
            )

        # 校验 ZIP 内文件哈希
        _verify_zip_hashes(zf, targets, manifest_hashes)

        # 自动备份
        backup_dir = _auto_backup(t0002_path, [t.rel_path for t in targets])

        # 解压
        _extract_zip_targets(zf, targets, t0002_path, progress_cb)

    return imported_items, backup_dir


def _folder_manifest_items(src_dir: Path) -> list[str]:
    manifest_path = src_dir / "manifest.json"
    if not manifest_path.exists():
        return []
    manifest = _load_manifest(manifest_path.read_text(encoding="utf-8"))
    return manifest.get("selected_items", [])


def _collect_folder_files(
    src_dir: Path,
    import_ids: set[str],
) -> tuple[list[DataItem], list[Path]]:
    imported_items: list[DataItem] = []
    all_src_files: list[Path] = []

    for iid in import_ids:
        item = ITEMS_BY_ID.get(iid)
        if item is None or item.safety_level == "forbidden":
            continue
        files = collect_files(src_dir, item.paths)
        if files:
            imported_items.append(item)
            all_src_files.extend(files)

    return imported_items, all_src_files


def _copy_folder_files(
    src_dir: Path,
    t0002_path: Path,
    all_src_files: list[Path],
    progress_cb: Callable[[str, int, int], None] | None,
) -> None:
    total = len(all_src_files)
    for idx, src_file in enumerate(all_src_files, 1):
        rel = src_file.relative_to(src_dir)
        dst = t0002_path / rel
        safe_copy_file(src_file, dst)
        if progress_cb:
            progress_cb(src_file.name, idx, total)


def import_from_folder(
    src_dir: Path,
    t0002_path: Path,
    selected_item_ids: list[str] | None = None,
    progress_cb: Callable[[str, int, int], None] | None = None,
) -> tuple[list[DataItem], Path]:
    """从备份文件夹导入配置，返回 (已导入数据项, 本次自动备份目录)。"""
    _ensure_tdx_closed(t0002_path)

    manifest_items = _folder_manifest_items(src_dir)
    import_ids = set(selected_item_ids) if selected_item_ids is not None else set(manifest_items)
    if not import_ids:
        # 自动扫描：把 src_dir 下的全部内容当作备份
        import_ids = set(ITEMS_BY_ID.keys())

    imported_items, all_src_files = _collect_folder_files(src_dir, import_ids)
    if not all_src_files:
        raise ImportError("备份文件夹中没有找到选中数据项对应的文件。")

    raw_size = count_size(all_src_files)
    if free_space(t0002_path) < raw_size:
        raise ImportError(
            f"目标磁盘空间不足：需要 {raw_size // 1024 // 1024} MB，"
            f"可用 {free_space(t0002_path) // 1024 // 1024} MB。"
        )

    rel_paths = [str(f.relative_to(src_dir)).replace("\\", "/") for f in all_src_files]
    backup_dir = _auto_backup(t0002_path, rel_paths)
    _copy_folder_files(src_dir, t0002_path, all_src_files, progress_cb)

    return imported_items, backup_dir


def rollback(backup_dir: Path, t0002_path: Path) -> None:
    """将自动备份目录中的文件回滚到 T0002 目录。"""
    for src_file in backup_dir.rglob("*"):
        if src_file.is_file():
            rel = src_file.relative_to(backup_dir)
            dst = t0002_path / rel
            safe_copy_file(src_file, dst)
