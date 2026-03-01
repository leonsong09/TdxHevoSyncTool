"""通达信路径自动检测"""
from __future__ import annotations
import winreg
from dataclasses import dataclass
from pathlib import Path
from string import ascii_uppercase

# 通达信目录下的标志性子目录，用于验证路径有效性
_MARKER_DIRS = ("blocknew", "dl", "vipdoc", "signals", "pad")

# 常见固定安装子目录名称（快速匹配）
_COMMON_SUBDIRS = (
    "new_tdx",
    "tdx",
    "通达信",
    "TDX",
    "zd_zsone",
    "hkex_tdx",
    "广发证券",
    "华泰证券",
    "国泰君安",
    "中信证券",
    "招商证券",
    "海通证券",
    "兴业证券",
    "东方财富",
)


@dataclass(frozen=True)
class TdxInstance:
    name: str
    t0002_path: Path
    source: str  # "registry" | "scan" | "manual"

    def __str__(self) -> str:
        return f"{self.name}  [{self.t0002_path}]"


def _is_valid_t0002(path: Path) -> bool:
    """检验路径是否为有效的 T0002 目录。"""
    if not path.is_dir():
        return False
    return any((path / m).exists() for m in _MARKER_DIRS)


def _find_via_registry() -> list[TdxInstance]:
    """从注册表查找通达信安装路径。"""
    results: list[TdxInstance] = []
    hives = [winreg.HKEY_LOCAL_MACHINE, winreg.HKEY_CURRENT_USER]
    sub_keys = [
        r"SOFTWARE\Microsoft\Windows\CurrentVersion\Uninstall",
        r"SOFTWARE\WOW6432Node\Microsoft\Windows\CurrentVersion\Uninstall",
    ]

    for hive in hives:
        for sub_key in sub_keys:
            try:
                with winreg.OpenKey(hive, sub_key) as key:
                    idx = 0
                    while True:
                        try:
                            sub_name = winreg.EnumKey(key, idx)
                            idx += 1
                        except OSError:
                            break
                        try:
                            with winreg.OpenKey(key, sub_name) as sub_key_handle:
                                display_name = winreg.QueryValueEx(
                                    sub_key_handle, "DisplayName"
                                )[0]
                                if "通达信" not in display_name and "TDX" not in display_name.upper():
                                    continue
                                install_loc = winreg.QueryValueEx(
                                    sub_key_handle, "InstallLocation"
                                )[0]
                                t0002 = Path(install_loc) / "T0002"
                                if _is_valid_t0002(t0002):
                                    results.append(
                                        TdxInstance(
                                            name=display_name,
                                            t0002_path=t0002,
                                            source="registry",
                                        )
                                    )
                        except OSError:
                            continue
            except OSError:
                continue

    return results


def _available_drives() -> list[str]:
    """返回系统所有盘符列表（如 ['C:', 'D:', 'E:']）。"""
    return [f"{d}:" for d in ascii_uppercase if Path(f"{d}:/").exists()]


def _search_t0002_under(root: Path, seen: set[Path], results: list[TdxInstance], depth: int = 2) -> None:
    """在 root 下递归最多 depth 层，查找所有 T0002 目录。"""
    if depth == 0 or not root.is_dir():
        return
    try:
        for child in root.iterdir():
            if not child.is_dir():
                continue
            if child.name.upper() == "T0002":
                if child not in seen and _is_valid_t0002(child):
                    seen.add(child)
                    results.append(
                        TdxInstance(
                            name=f"通达信 ({child.parent.name})",
                            t0002_path=child,
                            source="scan",
                        )
                    )
            else:
                _search_t0002_under(child, seen, results, depth - 1)
    except PermissionError:
        pass


def _find_via_scan() -> list[TdxInstance]:
    """扫描所有盘符下的通达信安装路径。

    策略：
    1. 快速匹配：盘根 / Program Files* / 固定子目录名 / T0002
    2. 深度扫描：在每个盘符根目录及 Program Files* 下递归两层，
       找到所有名为 T0002 的有效目录（覆盖带版本号的长路径）。
    """
    results: list[TdxInstance] = []
    seen: set[Path] = set()

    for drive in _available_drives():
        drive_path = Path(drive + "/")

        # 快速匹配固定名称
        for subdir in _COMMON_SUBDIRS:
            for base in (
                drive_path,
                drive_path / "Program Files",
                drive_path / "Program Files (x86)",
            ):
                t0002 = base / subdir / "T0002"
                if t0002 not in seen and _is_valid_t0002(t0002):
                    seen.add(t0002)
                    results.append(
                        TdxInstance(
                            name=f"通达信 ({t0002.parent.name})",
                            t0002_path=t0002,
                            source="scan",
                        )
                    )

        # 深度扫描（覆盖任意安装目录名，如带版本号的中文路径）
        # depth=4 覆盖：盘根/中间目录/安装目录(带版本号)/同名子目录/T0002
        for base in (
            drive_path,
            drive_path / "Program Files",
            drive_path / "Program Files (x86)",
        ):
            _search_t0002_under(base, seen, results, depth=4)

    return results


def find_tdx_instances() -> list[TdxInstance]:
    """查找所有通达信实例（注册表优先，再扫描常见路径），去重后返回。"""
    instances: list[TdxInstance] = []
    seen_paths: set[Path] = set()

    for inst in _find_via_registry():
        if inst.t0002_path not in seen_paths:
            instances.append(inst)
            seen_paths.add(inst.t0002_path)

    for inst in _find_via_scan():
        if inst.t0002_path not in seen_paths:
            instances.append(inst)
            seen_paths.add(inst.t0002_path)

    return instances


def validate_t0002_path(path: Path) -> bool:
    """对外暴露的路径验证接口。"""
    return _is_valid_t0002(path)
