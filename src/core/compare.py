"""通达信 T0002 两侧对比与导入计划计算"""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Iterable

from src.core.data_items import DataItem
from src.core.tdx_finder import validate_t0002_path
from src.utils.file_ops import collect_files, sha256_file

ProgressCallback = Callable[[str, int, int], None]

MODE_LEFT_TO_RIGHT = "left_to_right"
MODE_RIGHT_TO_LEFT = "right_to_left"
MODE_BI_MISSING = "bidirectional_missing"
MODE_BI_SYNC = "bidirectional_sync"

STRATEGY_DIFF = "diff"        # 缺失 + 冲突
STRATEGY_MISSING = "missing"  # 仅缺失
STRATEGY_FULL = "full"        # 全量覆盖

CONFLICT_LEFT = "left"
CONFLICT_RIGHT = "right"
CONFLICT_MTIME = "mtime"


@dataclass(frozen=True)
class ItemCompare:
    item: DataItem
    left_files: tuple[str, ...]
    right_files: tuple[str, ...]
    left_total_size: int
    right_total_size: int
    only_left: tuple[str, ...]
    only_right: tuple[str, ...]
    conflicts: tuple[str, ...]

    def has_diff(self) -> bool:
        return bool(self.only_left or self.only_right or self.conflicts)


@dataclass(frozen=True)
class CompareResult:
    left_t0002: Path
    right_t0002: Path
    by_item_id: dict[str, ItemCompare]


@dataclass(frozen=True)
class TransferPlan:
    mode: str
    strategy: str
    conflict_policy: str
    left_to_right: tuple[str, ...]
    right_to_left: tuple[str, ...]

    def total_files(self) -> int:
        return len(self.left_to_right) + len(self.right_to_left)


@dataclass(frozen=True)
class _ItemIndex:
    item: DataItem
    left_map: dict[str, str]
    right_map: dict[str, str]
    common_keys: set[str]
    only_left_keys: set[str]
    only_right_keys: set[str]
    left_total_size: int
    right_total_size: int


def compare_t0002(
    left_t0002: Path,
    right_t0002: Path,
    items: Iterable[DataItem],
    progress_cb: ProgressCallback | None = None,
) -> CompareResult:
    _ensure_valid_pair(left_t0002, right_t0002)
    indices, total_common = _index_items(left_t0002, right_t0002, items)
    by_item_id = _build_item_compares(left_t0002, right_t0002, indices, total_common, progress_cb)

    return CompareResult(
        left_t0002=left_t0002,
        right_t0002=right_t0002,
        by_item_id=by_item_id,
    )


def build_transfer_plan(
    compare: CompareResult,
    selected_item_ids: Iterable[str],
    mode: str,
    strategy: str = STRATEGY_DIFF,
    conflict_policy: str = CONFLICT_MTIME,
) -> TransferPlan:
    left_to_right: set[str] = set()
    right_to_left: set[str] = set()

    for item_id in selected_item_ids:
        item_cmp = compare.by_item_id.get(item_id)
        if item_cmp is None:
            continue
        if item_cmp.item.safety_level == "forbidden":
            continue

        if mode == MODE_LEFT_TO_RIGHT:
            left_to_right |= _single_direction_files(item_cmp, "left", strategy)
        elif mode == MODE_RIGHT_TO_LEFT:
            right_to_left |= _single_direction_files(item_cmp, "right", strategy)
        elif mode == MODE_BI_MISSING:
            left_to_right |= set(item_cmp.only_left)
            right_to_left |= set(item_cmp.only_right)
        elif mode == MODE_BI_SYNC:
            left_to_right |= set(item_cmp.only_left)
            right_to_left |= set(item_cmp.only_right)
            for rel in item_cmp.conflicts:
                winner = _pick_conflict_winner(compare.left_t0002, compare.right_t0002, rel, conflict_policy)
                if winner == CONFLICT_RIGHT:
                    right_to_left.add(rel)
                else:
                    left_to_right.add(rel)
        else:
            raise ValueError(f"unknown mode: {mode}")

    return TransferPlan(
        mode=mode,
        strategy=strategy,
        conflict_policy=conflict_policy,
        left_to_right=tuple(sorted(left_to_right)),
        right_to_left=tuple(sorted(right_to_left)),
    )


def _ensure_valid_pair(left: Path, right: Path) -> None:
    if not validate_t0002_path(left):
        raise ValueError(f"左侧路径不是有效的 T0002：{left}")
    if not validate_t0002_path(right):
        raise ValueError(f"右侧路径不是有效的 T0002：{right}")
    if left.resolve() == right.resolve():
        raise ValueError("左右两侧不能选择同一个 T0002 目录。")


def _rel_str(base: Path, path: Path) -> str:
    return str(path.relative_to(base)).replace("\\", "/")


def _build_rel_map(base: Path, files: list[Path]) -> dict[str, str]:
    result: dict[str, str] = {}
    for p in files:
        rel = _rel_str(base, p)
        key = rel.casefold()
        result.setdefault(key, rel)
    return result


def _index_items(left_t0002: Path, right_t0002: Path, items: Iterable[DataItem]) -> tuple[list[_ItemIndex], int]:
    indices: list[_ItemIndex] = []
    total_common = 0
    for item in items:
        left_files = collect_files(left_t0002, item.paths)
        right_files = collect_files(right_t0002, item.paths)

        left_map = _build_rel_map(left_t0002, left_files)
        right_map = _build_rel_map(right_t0002, right_files)

        left_keys = set(left_map.keys())
        right_keys = set(right_map.keys())
        common = left_keys & right_keys

        indices.append(
            _ItemIndex(
                item=item,
                left_map=left_map,
                right_map=right_map,
                common_keys=common,
                only_left_keys=left_keys - right_keys,
                only_right_keys=right_keys - left_keys,
                left_total_size=_sum_size(left_t0002, left_map.values()),
                right_total_size=_sum_size(right_t0002, right_map.values()),
            )
        )
        total_common += len(common)
    return indices, total_common


def _build_item_compares(
    left_t0002: Path,
    right_t0002: Path,
    indices: list[_ItemIndex],
    total_common: int,
    progress_cb: ProgressCallback | None,
) -> dict[str, ItemCompare]:
    done = 0
    by_item_id: dict[str, ItemCompare] = {}
    for idx in indices:
        conflict_keys, done = _compute_conflicts(left_t0002, right_t0002, idx, done, total_common, progress_cb)
        by_item_id[idx.item.id] = ItemCompare(
            item=idx.item,
            left_files=tuple(sorted(idx.left_map.values())),
            right_files=tuple(sorted(idx.right_map.values())),
            left_total_size=idx.left_total_size,
            right_total_size=idx.right_total_size,
            only_left=tuple(sorted(idx.left_map[k] for k in idx.only_left_keys)),
            only_right=tuple(sorted(idx.right_map[k] for k in idx.only_right_keys)),
            conflicts=tuple(sorted(idx.left_map[k] for k in conflict_keys)),
        )
    return by_item_id


def _compute_conflicts(
    left_t0002: Path,
    right_t0002: Path,
    idx: _ItemIndex,
    done: int,
    total_common: int,
    progress_cb: ProgressCallback | None,
) -> tuple[list[str], int]:
    conflict_keys: list[str] = []
    for key in sorted(idx.common_keys):
        left_rel = idx.left_map[key]
        right_rel = idx.right_map[key]
        left_path = left_t0002 / left_rel
        right_path = right_t0002 / right_rel
        if _is_conflict(left_path, right_path):
            conflict_keys.append(key)

        done += 1
        if progress_cb:
            progress_cb(left_path.name, done, total_common)
    return conflict_keys, done


def _sum_size(base: Path, rels: Iterable[str]) -> int:
    total = 0
    for rel in rels:
        total += (base / rel).stat().st_size
    return total


def _is_conflict(left_path: Path, right_path: Path) -> bool:
    if left_path.stat().st_size != right_path.stat().st_size:
        return True
    return sha256_file(left_path) != sha256_file(right_path)


def _single_direction_files(item_cmp: ItemCompare, side: str, strategy: str) -> set[str]:
    if side not in {"left", "right"}:
        raise ValueError("side must be 'left' or 'right'")

    if strategy == STRATEGY_FULL:
        return set(item_cmp.left_files if side == "left" else item_cmp.right_files)
    if strategy == STRATEGY_MISSING:
        return set(item_cmp.only_left if side == "left" else item_cmp.only_right)
    if strategy == STRATEGY_DIFF:
        base = set(item_cmp.only_left if side == "left" else item_cmp.only_right)
        base |= set(item_cmp.conflicts)
        return base
    raise ValueError(f"unknown strategy: {strategy}")


def _pick_conflict_winner(left_t0002: Path, right_t0002: Path, rel: str, policy: str) -> str:
    if policy == CONFLICT_LEFT:
        return CONFLICT_LEFT
    if policy == CONFLICT_RIGHT:
        return CONFLICT_RIGHT
    if policy != CONFLICT_MTIME:
        raise ValueError(f"unknown conflict_policy: {policy}")

    left_mtime = (left_t0002 / rel).stat().st_mtime
    right_mtime = (right_t0002 / rel).stat().st_mtime
    return CONFLICT_RIGHT if right_mtime > left_mtime else CONFLICT_LEFT
