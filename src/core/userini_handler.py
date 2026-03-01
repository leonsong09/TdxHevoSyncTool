"""user.ini extern 段落解析与合并"""
from __future__ import annotations
import re
from dataclasses import dataclass, field
from pathlib import Path

_SECTION_RE = re.compile(r"^\[([^\]]+)\]$")
_EXTERN_RE = re.compile(r"^\[extern_\d+\]$", re.IGNORECASE)

_DEFAULT_ENCODINGS = ("gbk", "gb2312", "utf-8", "latin-1")


def _read_text_auto(path: Path) -> str:
    """尝试多种编码读取文件内容，返回字符串。"""
    for enc in _DEFAULT_ENCODINGS:
        try:
            return path.read_text(encoding=enc)
        except (UnicodeDecodeError, LookupError):
            continue
    return path.read_bytes().decode("latin-1")


@dataclass
class IniSection:
    name: str
    lines: list[str] = field(default_factory=list)

    def is_extern(self) -> bool:
        return bool(_EXTERN_RE.match(f"[{self.name}]"))

    def as_text(self) -> str:
        return f"[{self.name}]\n" + "".join(self.lines)


def parse_ini(path: Path) -> tuple[list[IniSection], list[str]]:
    """
    解析 user.ini，返回 (sections, header_lines)。
    header_lines 包含第一个节之前的内容（通常为空或注释）。
    """
    raw = _read_text_auto(path)
    sections: list[IniSection] = []
    header_lines: list[str] = []
    current: IniSection | None = None

    for line in raw.splitlines(keepends=True):
        m = _SECTION_RE.match(line.strip())
        if m:
            current = IniSection(name=m.group(1))
            sections.append(current)
        elif current is not None:
            current.lines.append(line)
        else:
            header_lines.append(line)

    return sections, header_lines


def get_extern_sections(sections: list[IniSection]) -> list[IniSection]:
    return [s for s in sections if s.is_extern()]


@dataclass(frozen=True)
class MergePreview:
    """合并预览结果"""
    sections_to_add: list[IniSection]      # 目标中不存在、将直接追加的段落
    keys_to_add: list[tuple[IniSection, list[str]]]  # (目标段, 要追加的行)
    already_identical: list[IniSection]   # 已完全相同无需变动


def preview_merge(
    src_sections: list[IniSection],
    dst_sections: list[IniSection],
) -> MergePreview:
    """分析源和目标的 extern 段落，返回合并预览。"""
    dst_map: dict[str, IniSection] = {s.name: s for s in dst_sections}
    src_map: dict[str, IniSection] = {s.name: s for s in src_sections}

    sections_to_add: list[IniSection] = []
    keys_to_add: list[tuple[IniSection, list[str]]] = []
    already_identical: list[IniSection] = []

    for name, src_sec in src_map.items():
        if name not in dst_map:
            sections_to_add.append(src_sec)
        else:
            dst_sec = dst_map[name]
            dst_keys = {
                line.split("=", 1)[0].strip()
                for line in dst_sec.lines
                if "=" in line
            }
            new_lines = [
                line
                for line in src_sec.lines
                if "=" in line and line.split("=", 1)[0].strip() not in dst_keys
            ]
            if new_lines:
                keys_to_add.append((dst_sec, new_lines))
            else:
                already_identical.append(src_sec)

    return MergePreview(
        sections_to_add=sections_to_add,
        keys_to_add=keys_to_add,
        already_identical=already_identical,
    )


def apply_merge(
    dst_path: Path,
    dst_sections: list[IniSection],
    dst_header: list[str],
    preview: MergePreview,
) -> None:
    """
    将预览结果写入目标 user.ini。
    写入前创建 .bak 备份。
    """
    bak_path = dst_path.with_suffix(".ini.bak")
    bak_path.write_bytes(dst_path.read_bytes())

    # 更新 keys_to_add 对应的段落
    name_to_add_lines: dict[str, list[str]] = {
        sec.name: lines for sec, lines in preview.keys_to_add
    }

    parts: list[str] = list(dst_header)
    for sec in dst_sections:
        parts.append(f"[{sec.name}]\n")
        parts.extend(sec.lines)
        if sec.name in name_to_add_lines:
            parts.extend(name_to_add_lines[sec.name])

    # 追加全新的段落
    for sec in preview.sections_to_add:
        parts.append(sec.as_text())

    merged_text = "".join(parts)
    # 保持原始编码（尝试 GBK 写入）
    try:
        dst_path.write_text(merged_text, encoding="gbk")
    except (UnicodeEncodeError, LookupError):
        dst_path.write_text(merged_text, encoding="utf-8")
