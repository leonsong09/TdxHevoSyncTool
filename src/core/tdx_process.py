"""通达信进程检测"""
from __future__ import annotations
from dataclasses import dataclass
from pathlib import Path

import psutil

# 通达信常见进程名称列表（小写匹配）
_TDX_PROCESS_NAMES = {
    "tdxw.exe",
    "tdx.exe",
    "new_tdxw.exe",
    "zd_zsone.exe",
    "hkex_tdx.exe",
    "tdxwh.exe",
}


@dataclass(frozen=True)
class TdxProcessStatus:
    is_running: bool
    process_name: str = ""
    pid: int = 0
    exe_path: str = ""


def detect_tdx_process(t0002_path: Path | None = None) -> TdxProcessStatus:
    """
    检测通达信主程序是否正在运行。

    若提供 t0002_path，则额外校验进程的可执行文件是否在该通达信目录下
    （精确匹配当前操作的实例）。未提供时，只要有任意通达信进程在运行即返回 True。
    """
    for proc in psutil.process_iter(["name", "pid", "exe"]):
        try:
            proc_name = (proc.info.get("name") or "").lower()
            if proc_name not in _TDX_PROCESS_NAMES:
                continue

            exe = proc.info.get("exe") or ""
            if t0002_path is not None:
                # 判断进程是否属于当前操作的通达信实例
                try:
                    proc_path = Path(exe).resolve()
                    tdx_root = t0002_path.parent.resolve()
                    if not proc_path.is_relative_to(tdx_root):
                        continue
                except (ValueError, OSError):
                    pass  # 路径无法解析时不过滤，保守起见视为冲突

            return TdxProcessStatus(
                is_running=True,
                process_name=proc.info.get("name") or proc_name,
                pid=proc.info.get("pid") or 0,
                exe_path=exe,
            )
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            continue

    return TdxProcessStatus(is_running=False)


def assert_tdx_not_running(t0002_path: Path | None = None) -> TdxProcessStatus:
    """
    若通达信正在运行则返回状态对象（调用方负责弹窗提示），
    未运行返回 is_running=False。
    """
    return detect_tdx_process(t0002_path)
