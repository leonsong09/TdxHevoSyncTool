#!/usr/bin/env python3
"""TdxHevoSyncTool 命令行入口（CLI）。

与 GUI 共用 `src/core` 的全部逻辑，不弹窗、可脚本化/自动化调用。

用法::

    python cli.py items
    python cli.py discover
    python cli.py export  --t0002 <T0002> --out <dir> [--items a,b | --level safe | --all] [--mode zip|folder]
    python cli.py import  --src <zip|dir> --t0002 <T0002> [--items a,b] [--apply]
    python cli.py compare --left <T0002> --right <T0002> [--items a,b]
    python cli.py plan    --left <T0002> --right <T0002> --mode l2r|r2l|bi-missing|bi-sync
                          [--strategy diff|missing|full] [--conflict left|right|mtime] [--items a,b]
    python cli.py rollback --backup <.tdx_backup_xxx> --t0002 <T0002> [--apply]
    python cli.py userini --src <user.ini> --dst <user.ini> [--apply]

约定（与家族其它工具一致）:
  * 所有**写**操作默认预演（dry-run），必须显式加 `--apply` 才落盘；
  * 导出/导入前会检测通达信是否在运行（与 GUI 同一判据）；
  * 退出码: 0 成功 / 1 业务失败（参数/校验/运行中冲突等）/ 2 用法错误。
"""
from __future__ import annotations

import argparse
import json
import sys
import zipfile
from pathlib import Path

# 让 `python cli.py` 与 `python -m cli` 都能 import 到 src.*
_ROOT = Path(__file__).resolve().parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from src.core import compare as cmp_mod  # noqa: E402
from src.core import exporter, importer, userini_handler  # noqa: E402
from src.core.data_items import (  # noqa: E402
    ALL_DATA_ITEMS,
    CAUTION_ITEMS,
    FORBIDDEN_ITEMS,
    ITEMS_BY_ID,
    SAFE_ITEMS,
)
from src.core.tdx_finder import find_tdx_instances, resolve_t0002_path  # noqa: E402
from src.core.tdx_process import detect_tdx_process  # noqa: E402
from src.core.version import APP_NAME, APP_VERSION  # noqa: E402

MODE_MAP = {
    "l2r": cmp_mod.MODE_LEFT_TO_RIGHT,
    "r2l": cmp_mod.MODE_RIGHT_TO_LEFT,
    "bi-missing": cmp_mod.MODE_BI_MISSING,
    "bi-sync": cmp_mod.MODE_BI_SYNC,
}
STRATEGY_MAP = {
    "diff": cmp_mod.STRATEGY_DIFF,
    "missing": cmp_mod.STRATEGY_MISSING,
    "full": cmp_mod.STRATEGY_FULL,
}
CONFLICT_MAP = {
    "left": cmp_mod.CONFLICT_LEFT,
    "right": cmp_mod.CONFLICT_RIGHT,
    "mtime": cmp_mod.CONFLICT_MTIME,
}
LEVEL_MAP = {"safe": SAFE_ITEMS, "caution": CAUTION_ITEMS, "forbidden": FORBIDDEN_ITEMS}


def _out(msg: str = "") -> None:
    print(msg)


def _human(n: int) -> str:
    v = float(n)
    for unit in ("B", "KB", "MB", "GB", "TB"):
        if v < 1024 or unit == "TB":
            return f"{v:.1f}{unit}" if unit != "B" else f"{int(v)}B"
        v /= 1024
    return f"{v:.1f}TB"


def _resolve_t0002(raw: str) -> Path:
    p = Path(raw).expanduser()
    resolved = resolve_t0002_path(p)
    if resolved is None:
        raise ValueError(f"不是有效的 T0002 目录（也不是含 T0002 子目录的安装根目录）：{p}")
    return resolved


def _select_items(args) -> list:
    """按 --items / --level / --all 选择数据项；缺省 = safe 全选。"""
    if getattr(args, "all", False):
        return [i for i in ALL_DATA_ITEMS if i.safety_level != "forbidden"]
    raw = getattr(args, "items", None)
    if raw:
        ids = [x.strip() for x in raw.split(",") if x.strip()]
        unknown = [x for x in ids if x not in ITEMS_BY_ID]
        if unknown:
            raise ValueError(f"未知数据项 id：{', '.join(unknown)}（用 `items` 子命令查看）")
        return [ITEMS_BY_ID[x] for x in ids]
    levels = getattr(args, "level", None)
    if levels:
        picked: list = []
        for lv in [x.strip() for x in levels.split(",") if x.strip()]:
            if lv not in LEVEL_MAP:
                raise ValueError(f"未知安全级别：{lv}（可选 safe/caution/forbidden）")
            for item in LEVEL_MAP[lv]:
                if item not in picked:
                    picked.append(item)
        return [i for i in picked if i.safety_level != "forbidden"]
    return list(SAFE_ITEMS)


def _progress(name: str, done: int, total: int) -> None:
    if total <= 0:
        return
    pct = int(done * 100 / total)
    sys.stdout.write(f"\r  [{done}/{total}] {pct:3d}%  {name[:40]:<40}")
    sys.stdout.flush()
    if done >= total:
        sys.stdout.write("\n")


# ---------------------------------------------------------------- subcommands

def cmd_items(args) -> int:
    _out(f"{APP_NAME} v{APP_VERSION} — 数据项清单（id | 安全级别 | 名称）")
    for item in ALL_DATA_ITEMS:
        _out(f"  {item.id:<20} {item.safety_level:<10} {item.name}")
        _out(f"  {'':<20} {'':<10} paths: {', '.join(item.paths)}")
    _out("")
    _out("说明: safe=默认全选 / caution=默认不选 / forbidden=禁止导入导出")
    return 0


def cmd_discover(args) -> int:
    instances = find_tdx_instances()
    if not instances:
        _out("未发现通达信实例（可用 --t0002 手动指定路径）。")
        return 1
    _out(f"发现 {len(instances)} 个通达信实例：")
    for inst in instances:
        _out(f"  - {inst.name}  [{inst.t0002_path}]  ({inst.source})")
    return 0


def cmd_export(args) -> int:
    t0002 = _resolve_t0002(args.t0002)
    items = _select_items(args)
    if not items:
        _out("未选中任何数据项。")
        return 1
    out_dir = Path(args.out).expanduser()
    out_dir.mkdir(parents=True, exist_ok=True)

    _out(f"源 T0002 : {t0002}")
    _out(f"数据项   : {', '.join(i.id for i in items)}")
    _out(f"模式     : {args.mode}")
    status = detect_tdx_process(t0002)
    if status.is_running:
        _out(f"[ERROR] 通达信正在运行（{status.process_name} PID={status.pid}），请先关闭。")
        return 1

    try:
        if args.mode == "folder":
            dest = exporter.export_to_folder(t0002, items, out_dir, _progress)
        else:
            dest = exporter.export_to_zip(t0002, items, out_dir, _progress)
    except exporter.ExportError as exc:
        _out(f"[ERROR] {exc}")
        return 1
    _out(f"[OK] 已导出: {dest}")
    return 0


def _manifest_of(src: Path) -> dict | None:
    try:
        if src.is_dir():
            mf = src / "manifest.json"
            if not mf.exists():
                return None
            return json.loads(mf.read_text(encoding="utf-8"))
        if zipfile.is_zipfile(src):
            with zipfile.ZipFile(src) as zf:
                if "manifest.json" not in zf.namelist():
                    return None
                return json.loads(zf.read("manifest.json").decode("utf-8"))
    except Exception:  # noqa: BLE001
        return None
    return None


def cmd_import(args) -> int:
    t0002 = _resolve_t0002(args.t0002)
    src = Path(args.src).expanduser()
    if not src.exists():
        _out(f"[ERROR] 备份源不存在：{src}")
        return 1

    manifest = _manifest_of(src)
    if manifest is None:
        _out("[WARN] 未找到 manifest.json（非本工具生成的标准备份包），将按扫描内容导入。")
        manifest_items = []
    else:
        manifest_items = manifest.get("selected_items", [])
        _out(f"备份包: tool_version={manifest.get('tool_version')} export_time={manifest.get('export_time')}")
        _out(f"        source_path={manifest.get('source_path')}")
        _out(f"        分类: {', '.join(manifest_items) or '(无)'}")

    ids = None
    if args.items:
        ids = [x.strip() for x in args.items.split(",") if x.strip()]
        unknown = [x for x in ids if x not in ITEMS_BY_ID]
        if unknown:
            _out(f"[ERROR] 未知数据项 id：{', '.join(unknown)}")
            return 1
        _out(f"仅导入指定分类: {', '.join(ids)}")

    effective = ids if ids is not None else (manifest_items or ["<全部>"])
    _out(f"目标 T0002: {t0002}")
    _out(f"将导入分类: {', '.join(effective)}")

    status = detect_tdx_process(t0002)
    if status.is_running:
        _out(f"[ERROR] 通达信正在运行（{status.process_name} PID={status.pid}），请先关闭。")
        return 1

    if not args.apply:
        _out("[DRY-RUN] 预演结束，未写入。确认无误后加 --apply 执行（导入前会自动备份到 .tdx_backup_*）。")
        return 0

    try:
        if src.is_dir():
            imported, backup_dir = importer.import_from_folder(src, t0002, ids, _progress)
        else:
            imported, backup_dir = importer.import_from_zip(src, t0002, ids, _progress)
    except importer.ImportError as exc:
        _out(f"[ERROR] {exc}")
        return 1
    _out(f"[OK] 已导入 {len(imported)} 个分类: {', '.join(i.id for i in imported)}")
    _out(f"     导入前备份: {backup_dir}（可 `rollback --backup` 回滚）")
    return 0


def cmd_compare(args) -> int:
    left = _resolve_t0002(args.left)
    right = _resolve_t0002(args.right)
    items = _select_items(args)
    try:
        result = cmp_mod.compare_t0002(left, right, items, _progress)
    except ValueError as exc:
        _out(f"[ERROR] {exc}")
        return 1

    _out(f"左: {left}")
    _out(f"右: {right}")
    _out("")
    _out(f"{'item':<20} {'only_L':>7} {'only_R':>7} {'conflict':>8} {'L_size':>10} {'R_size':>10}")
    diff_items = 0
    for item in items:
        ic = result.by_item_id.get(item.id)
        if ic is None:
            continue
        if ic.has_diff():
            diff_items += 1
        _out(
            f"{item.id:<20} {len(ic.only_left):>7} {len(ic.only_right):>7} "
            f"{len(ic.conflicts):>8} {_human(ic.left_total_size):>10} {_human(ic.right_total_size):>10}"
        )
    _out("")
    _out(f"有差异的分类数: {diff_items} / {len(items)}")
    return 0


def cmd_plan(args) -> int:
    left = _resolve_t0002(args.left)
    right = _resolve_t0002(args.right)
    items = _select_items(args)
    mode = MODE_MAP[args.mode]
    strategy = STRATEGY_MAP[args.strategy]
    conflict = CONFLICT_MAP[args.conflict]
    try:
        result = cmp_mod.compare_t0002(left, right, items, _progress)
        plan = cmp_mod.build_transfer_plan(result, [i.id for i in items], mode, strategy, conflict)
    except ValueError as exc:
        _out(f"[ERROR] {exc}")
        return 1

    _out(f"mode={args.mode} strategy={args.strategy} conflict={args.conflict}")
    _out(f"左→右 待复制文件数: {len(plan.left_to_right)}")
    for rel in plan.left_to_right[:50]:
        _out(f"    L->R {rel}")
    if len(plan.left_to_right) > 50:
        _out(f"    ... 其余 {len(plan.left_to_right) - 50} 个省略")
    _out(f"右→左 待复制文件数: {len(plan.right_to_left)}")
    for rel in plan.right_to_left[:50]:
        _out(f"    R->L {rel}")
    if len(plan.right_to_left) > 50:
        _out(f"    ... 其余 {len(plan.right_to_left) - 50} 个省略")
    _out("")
    _out("[DRY-RUN] 仅输出计划，不落盘。实际执行请在 GUI「对比/导入（两版本）」中确认后执行。")
    return 0


def cmd_rollback(args) -> int:
    t0002 = _resolve_t0002(args.t0002)
    backup_dir = Path(args.backup).expanduser()
    if not backup_dir.is_dir():
        _out(f"[ERROR] 备份目录不存在：{backup_dir}")
        return 1
    files = [p for p in backup_dir.rglob("*") if p.is_file()]
    _out(f"备份目录: {backup_dir}（{len(files)} 个文件）")
    _out(f"目标 T0002: {t0002}")
    status = detect_tdx_process(t0002)
    if status.is_running:
        _out(f"[ERROR] 通达信正在运行（{status.process_name} PID={status.pid}），请先关闭。")
        return 1
    if not args.apply:
        _out("[DRY-RUN] 预演结束，未写入。确认无误后加 --apply 执行回滚。")
        return 0
    importer.rollback(backup_dir, t0002)
    _out(f"[OK] 已从 {backup_dir} 回滚到 {t0002}")
    return 0


def cmd_userini(args) -> int:
    src = Path(args.src).expanduser()
    dst = Path(args.dst).expanduser()
    for p in (src, dst):
        if not p.is_file():
            _out(f"[ERROR] 文件不存在：{p}")
            return 1
    try:
        src_sections, _ = userini_handler.parse_ini(src)
        dst_sections, dst_header = userini_handler.parse_ini(dst)
        preview = userini_handler.preview_merge(src_sections, dst_sections)
    except ValueError as exc:
        _out(f"[ERROR] {exc}")
        return 1

    _out(f"源  : {src}")
    _out(f"目标: {dst}")
    _out(f"待替换键的段: {len(preview.keys_to_replace)}")
    for section, lines in preview.keys_to_replace:
        _out(f"    [{section.name}]  {len(lines)} 个键")
    _out(f"待追加键的段(extern_*): {len(preview.keys_to_add)}")
    for section, lines in preview.keys_to_add:
        _out(f"    [{section.name}]  {len(lines)} 个键")
    _out(f"目标缺失、将跳过的段: {len(preview.missing_target_sections)}")
    for section in preview.missing_target_sections[:20]:
        _out(f"    [{section.name}]")
    _out(f"已一致: {len(preview.already_identical)} 个段")
    if not args.apply:
        _out("[DRY-RUN] 预演结束，未写入。确认无误后加 --apply 执行（写入前生成 .bak）。")
        return 0
    userini_handler.apply_merge(dst, dst_sections, dst_header, preview)
    _out(f"[OK] 已同步到 {dst}（原文件备份为 {dst.with_suffix('.ini.bak')}）")
    return 0


# ---------------------------------------------------------------- parser

def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="tdx-sync",
        description=f"{APP_NAME} v{APP_VERSION} — 命令行入口（与 GUI 共用 core 逻辑）",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    sub = p.add_subparsers(dest="command", required=True)

    def add_sel(sp):
        sp.add_argument("--items", help="逗号分隔的数据项 id（见 items 子命令）")
        sp.add_argument("--level", help="按安全级别选：safe,caution（逗号分隔）")
        sp.add_argument("--all", action="store_true", help="选中全部非 forbidden 项（含 caution）")

    sp = sub.add_parser("items", help="列出全部数据项")
    sp.set_defaults(func=cmd_items)

    sp = sub.add_parser("discover", help="自动检测本机通达信 T0002")
    sp.set_defaults(func=cmd_discover)

    sp = sub.add_parser("export", help="导出 T0002 配置为 ZIP / 文件夹")
    sp.add_argument("--t0002", required=True, help="T0002 目录（或安装根目录）")
    sp.add_argument("--out", required=True, help="输出目录")
    sp.add_argument("--mode", choices=["zip", "folder"], default="zip")
    add_sel(sp)
    sp.set_defaults(func=cmd_export)

    sp = sub.add_parser("import", help="从 ZIP / 文件夹导入配置（默认预演）")
    sp.add_argument("--src", required=True, help="备份 ZIP 或备份文件夹")
    sp.add_argument("--t0002", required=True, help="目标 T0002 目录")
    sp.add_argument("--items", help="只导入指定数据项 id（逗号分隔）")
    sp.add_argument("--apply", action="store_true", help="真正写入（默认仅预演）")
    sp.set_defaults(func=cmd_import)

    sp = sub.add_parser("compare", help="对比两套 T0002 的差异")
    sp.add_argument("--left", required=True)
    sp.add_argument("--right", required=True)
    add_sel(sp)
    sp.set_defaults(func=cmd_compare)

    sp = sub.add_parser("plan", help="生成迁移/同步计划（只输出，不落盘）")
    sp.add_argument("--left", required=True)
    sp.add_argument("--right", required=True)
    sp.add_argument("--mode", choices=list(MODE_MAP), required=True)
    sp.add_argument("--strategy", choices=list(STRATEGY_MAP), default="diff")
    sp.add_argument("--conflict", choices=list(CONFLICT_MAP), default="mtime")
    add_sel(sp)
    sp.set_defaults(func=cmd_plan)

    sp = sub.add_parser("rollback", help="用导入前的 .tdx_backup_* 回滚（默认预演）")
    sp.add_argument("--backup", required=True, help=".tdx_backup_YYYYmmdd_HHMMSS 目录")
    sp.add_argument("--t0002", required=True)
    sp.add_argument("--apply", action="store_true")
    sp.set_defaults(func=cmd_rollback)

    sp = sub.add_parser("userini", help="user.ini 定向同步（默认预演）")
    sp.add_argument("--src", required=True, help="源 user.ini")
    sp.add_argument("--dst", required=True, help="目标 user.ini")
    sp.add_argument("--apply", action="store_true")
    sp.set_defaults(func=cmd_userini)
    return p


def main(argv: list[str] | None = None) -> int:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        return args.func(args)
    except ValueError as exc:
        _out(f"[ERROR] {exc}")
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
