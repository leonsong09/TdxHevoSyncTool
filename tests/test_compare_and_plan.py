import os
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

from src.core.compare import (
    CONFLICT_MTIME,
    MODE_BI_MISSING,
    MODE_BI_SYNC,
    MODE_LEFT_TO_RIGHT,
    STRATEGY_DIFF,
    STRATEGY_FULL,
    STRATEGY_MISSING,
    build_transfer_plan,
    compare_t0002,
)
from src.core.data_items import DataItem

_OLD_MTIME = (1_600_000_000, 1_600_000_000)
_NEW_MTIME = (1_700_000_000, 1_700_000_000)


class TestCompareAndPlan(unittest.TestCase):
    def test_compare_detects_missing_and_conflict(self) -> None:
        with TemporaryDirectory() as td:
            base = Path(td)
            left = base / "left"
            right = base / "right"
            (left / "blocknew").mkdir(parents=True)
            (right / "blocknew").mkdir(parents=True)

            (left / "only_left.txt").write_text("L", encoding="utf-8")
            (right / "only_right.txt").write_text("R", encoding="utf-8")
            (left / "common.txt").write_text("A", encoding="utf-8")
            (right / "common.txt").write_text("B", encoding="utf-8")

            item = DataItem(
                id="test",
                name="test",
                description="",
                safety_level="safe",
                paths=("only_left.txt", "only_right.txt", "common.txt"),
            )
            result = compare_t0002(left, right, [item])
            cmp = result.by_item_id["test"]

            self.assertEqual(set(cmp.only_left), {"only_left.txt"})
            self.assertEqual(set(cmp.only_right), {"only_right.txt"})
            self.assertEqual(set(cmp.conflicts), {"common.txt"})

    def test_transfer_plan_single_direction_strategies(self) -> None:
        with TemporaryDirectory() as td:
            base = Path(td)
            left = base / "left"
            right = base / "right"
            (left / "blocknew").mkdir(parents=True)
            (right / "blocknew").mkdir(parents=True)

            (left / "only_left.txt").write_text("L", encoding="utf-8")
            (right / "only_right.txt").write_text("R", encoding="utf-8")
            (left / "common.txt").write_text("A", encoding="utf-8")
            (right / "common.txt").write_text("B", encoding="utf-8")

            item = DataItem(
                id="test",
                name="test",
                description="",
                safety_level="safe",
                paths=("only_left.txt", "only_right.txt", "common.txt"),
            )
            result = compare_t0002(left, right, [item])

            plan_missing = build_transfer_plan(result, ["test"], MODE_LEFT_TO_RIGHT, STRATEGY_MISSING)
            self.assertEqual(set(plan_missing.left_to_right), {"only_left.txt"})

            plan_diff = build_transfer_plan(result, ["test"], MODE_LEFT_TO_RIGHT, STRATEGY_DIFF)
            self.assertEqual(set(plan_diff.left_to_right), {"only_left.txt", "common.txt"})

            plan_full = build_transfer_plan(result, ["test"], MODE_LEFT_TO_RIGHT, STRATEGY_FULL)
            self.assertEqual(set(plan_full.left_to_right), {"only_left.txt", "common.txt"})

    def test_transfer_plan_bidirectional_missing_only(self) -> None:
        with TemporaryDirectory() as td:
            base = Path(td)
            left = base / "left"
            right = base / "right"
            (left / "blocknew").mkdir(parents=True)
            (right / "blocknew").mkdir(parents=True)

            (left / "only_left.txt").write_text("L", encoding="utf-8")
            (right / "only_right.txt").write_text("R", encoding="utf-8")
            (left / "common.txt").write_text("A", encoding="utf-8")
            (right / "common.txt").write_text("B", encoding="utf-8")

            item = DataItem(
                id="test",
                name="test",
                description="",
                safety_level="safe",
                paths=("only_left.txt", "only_right.txt", "common.txt"),
            )
            result = compare_t0002(left, right, [item])
            plan = build_transfer_plan(result, ["test"], MODE_BI_MISSING)

            self.assertEqual(set(plan.left_to_right), {"only_left.txt"})
            self.assertEqual(set(plan.right_to_left), {"only_right.txt"})

    def test_transfer_plan_bidirectional_sync_conflict_policy_mtime(self) -> None:
        with TemporaryDirectory() as td:
            base = Path(td)
            left = base / "left"
            right = base / "right"
            (left / "blocknew").mkdir(parents=True)
            (right / "blocknew").mkdir(parents=True)

            left_common = left / "common.txt"
            right_common = right / "common.txt"
            left_common.write_text("A", encoding="utf-8")
            right_common.write_text("B", encoding="utf-8")

            os.utime(left_common, _OLD_MTIME)
            os.utime(right_common, _NEW_MTIME)

            item = DataItem(
                id="test",
                name="test",
                description="",
                safety_level="safe",
                paths=("common.txt",),
            )
            result = compare_t0002(left, right, [item])
            plan = build_transfer_plan(result, ["test"], MODE_BI_SYNC, conflict_policy=CONFLICT_MTIME)

            self.assertEqual(plan.left_to_right, ())
            self.assertEqual(set(plan.right_to_left), {"common.txt"})
