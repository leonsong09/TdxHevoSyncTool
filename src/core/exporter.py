"""导出功能 — ZIP 和文件夹两种模式"""
from __future__ import annotations
import json
import zipfile
from datetime import datetime
from pathlib import Path
from typing import Callable

from src.core.data_items import DataItem
from src.core.tdx_process import assert_tdx_not_running
from src.core.version import TOOL_VERSION
from src.utils.file_ops import (
    collect_files,
    count_size,
    free_space,
    sha256_file,
    safe_copy_file,
    safe_copy_tree,
    verify_copies,
)


def _make_manifest(
    t0002_path: Path,
    selected_items: list[DataItem],
    file_hashes: dict[str, str],
) -> dict:
    return {
        "tool_version": TOOL_VERSION,
        "export_time": datetime.now().isoformat(),
        "source_path": str(t0002_path),
        "selected_items": [item.id for item in selected_items],
        "file_hashes": file_hashes,
    }


class ExportError(Exception):
    pass


def _ensure_no_forbidden_items(selected_items: list[DataItem]) -> None:
    forbidden = [i.name for i in selected_items if i.safety_level == "forbidden"]
    if forbidden:
        raise ExportError(f"禁止导出的数据项：{'、'.join(forbidden)}")


def export_to_zip(
    t0002_path: Path,
    selected_items: list[DataItem],
    output_dir: Path,
    progress_cb: Callable[[str, int, int], None] | None = None,
) -> Path:
    """
    将选中的数据项导出为 ZIP 文件。

    Args:
        t0002_path: 通达信 T0002 目录路径
        selected_items: 选中的数据项列表
        output_dir: ZIP 文件输出目录
        progress_cb: 进度回调 (当前文件名, 已完成数, 总数)

    Returns:
        生成的 ZIP 文件路径
    """
    _ensure_no_forbidden_items(selected_items)
    # 进程检测
    status = assert_tdx_not_running(t0002_path)
    if status.is_running:
        raise ExportError(
            f"检测到通达信正在运行（进程: {status.process_name}, PID: {status.pid}）。\n"
            "请先关闭通达信后再进行导出操作。"
        )

    # 收集所有文件
    all_files: list[Path] = []
    for item in selected_items:
        all_files.extend(collect_files(t0002_path, item.paths))

    total = len(all_files)
    if total == 0:
        raise ExportError("选中的数据项中没有找到任何文件，请确认 T0002 路径正确。")

    # 磁盘空间检测（估算 ZIP 压缩后约为原始大小）
    raw_size = count_size(all_files)
    if free_space(output_dir) < raw_size:
        raise ExportError(
            f"目标磁盘空间不足。需要约 {raw_size // 1024 // 1024} MB，"
            f"可用 {free_space(output_dir) // 1024 // 1024} MB。"
        )

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    zip_name = f"TDX_Backup_{timestamp}.zip"
    zip_path = output_dir / zip_name

    file_hashes: dict[str, str] = {}

    with zipfile.ZipFile(zip_path, "w", compression=zipfile.ZIP_DEFLATED) as zf:
        for idx, src_file in enumerate(all_files, 1):
            rel = src_file.relative_to(t0002_path)
            arc_name = str(rel).replace("\\", "/")
            zf.write(src_file, arcname=arc_name)
            file_hashes[arc_name] = sha256_file(src_file)
            if progress_cb:
                progress_cb(src_file.name, idx, total + 1)

        # 写入 manifest
        manifest = _make_manifest(t0002_path, selected_items, file_hashes)
        zf.writestr("manifest.json", json.dumps(manifest, ensure_ascii=False, indent=2))

    if progress_cb:
        progress_cb("manifest.json", total + 1, total + 1)

    return zip_path


def export_to_folder(
    t0002_path: Path,
    selected_items: list[DataItem],
    output_dir: Path,
    progress_cb: Callable[[str, int, int], None] | None = None,
) -> Path:
    """
    将选中的数据项导出到文件夹。

    Returns:
        生成的备份文件夹路径
    """
    _ensure_no_forbidden_items(selected_items)
    status = assert_tdx_not_running(t0002_path)
    if status.is_running:
        raise ExportError(
            f"检测到通达信正在运行（进程: {status.process_name}, PID: {status.pid}）。\n"
            "请先关闭通达信后再进行导出操作。"
        )

    all_files: list[Path] = []
    for item in selected_items:
        all_files.extend(collect_files(t0002_path, item.paths))

    total = len(all_files)
    if total == 0:
        raise ExportError("选中的数据项中没有找到任何文件。")

    raw_size = count_size(all_files)
    if free_space(output_dir) < raw_size:
        raise ExportError(
            f"目标磁盘空间不足。需要约 {raw_size // 1024 // 1024} MB，"
            f"可用 {free_space(output_dir) // 1024 // 1024} MB。"
        )

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    dest_dir = output_dir / f"TDX_Backup_{timestamp}"
    dest_dir.mkdir(parents=True, exist_ok=True)

    file_hashes: dict[str, str] = {}
    copied_files: list[Path] = []

    for idx, src_file in enumerate(all_files, 1):
        rel = src_file.relative_to(t0002_path)
        dst_file = dest_dir / rel
        safe_copy_file(src_file, dst_file)
        file_hashes[str(rel).replace("\\", "/")] = sha256_file(src_file)
        copied_files.append(dst_file)
        if progress_cb:
            progress_cb(src_file.name, idx, total + 1)

    # 写入 manifest
    manifest = _make_manifest(t0002_path, selected_items, file_hashes)
    manifest_path = dest_dir / "manifest.json"
    manifest_path.write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8"
    )

    # 导出后校验
    mismatches = verify_copies(all_files, copied_files)
    if mismatches:
        mismatch_names = ", ".join(str(o.name) for o, _ in mismatches[:5])
        raise ExportError(f"导出校验失败，以下文件内容不一致：{mismatch_names}")

    if progress_cb:
        progress_cb("完成", total + 1, total + 1)

    return dest_dir
