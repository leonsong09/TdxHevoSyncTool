"""文件操作工具 — 安全复制、SHA256 校验等"""
from __future__ import annotations
import hashlib
import shutil
from pathlib import Path
from typing import Callable

_WILDCARD_CHARS = ("*", "?", "[")
_HASH_CHUNK_SIZE = 65536


def sha256_file(path: Path) -> str:
    """计算文件的 SHA256 哈希值。"""
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(_HASH_CHUNK_SIZE), b""):
            h.update(chunk)
    return h.hexdigest()


def safe_copy_file(
    src: Path,
    dst: Path,
    progress_cb: Callable[[str], None] | None = None,
) -> None:
    """将 src 复制到 dst，保留文件属性，目标目录不存在时自动创建。"""
    dst.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(src, dst)
    if progress_cb:
        progress_cb(str(src.name))


def safe_copy_tree(
    src_dir: Path,
    dst_dir: Path,
    progress_cb: Callable[[str], None] | None = None,
) -> None:
    """递归复制整个目录树，保留文件属性。"""
    for src_file in src_dir.rglob("*"):
        if src_file.is_file():
            relative = src_file.relative_to(src_dir)
            dst_file = dst_dir / relative
            safe_copy_file(src_file, dst_file, progress_cb)


def collect_files(base: Path, paths: tuple[str, ...]) -> list[Path]:
    """收集给定相对路径列表下的所有文件（展开目录）。"""
    files: list[Path] = []
    for rel in paths:
        if any(ch in rel for ch in _WILDCARD_CHARS):
            files.extend(p for p in base.glob(rel) if p.is_file())
            continue

        target = base / rel
        if target.is_file():
            files.append(target)
        elif target.is_dir():
            files.extend(p for p in target.rglob("*") if p.is_file())
    return _dedup_files(files)


def _dedup_files(files: list[Path]) -> list[Path]:
    seen: set[str] = set()
    result: list[Path] = []
    for p in files:
        try:
            key = str(p.resolve()).casefold()
        except OSError:
            key = str(p).casefold()
        if key in seen:
            continue
        seen.add(key)
        result.append(p)
    return result


def count_size(files: list[Path]) -> int:
    """返回文件列表的总字节数（跳过不存在的文件）。"""
    total = 0
    for f in files:
        try:
            total += f.stat().st_size
        except OSError:
            pass
    return total


def free_space(path: Path) -> int:
    """返回指定路径所在磁盘的可用字节数。"""
    return shutil.disk_usage(path).free


def verify_copies(
    originals: list[Path],
    copies: list[Path],
) -> list[tuple[Path, Path]]:
    """对比原文件和副本的 SHA256，返回不一致的 (orig, copy) 对。"""
    mismatches: list[tuple[Path, Path]] = []
    for orig, copy in zip(originals, copies):
        if not copy.exists():
            mismatches.append((orig, copy))
        elif sha256_file(orig) != sha256_file(copy):
            mismatches.append((orig, copy))
    return mismatches
