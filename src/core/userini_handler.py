"""user.ini extern 段落解析与合并"""
from __future__ import annotations
import re
from dataclasses import dataclass, field
from pathlib import Path

_SECTION_RE = re.compile(r"^\[([^\]]+)\]$")
_EXTERN_RE = re.compile(r"^\[extern_\d+\]$", re.IGNORECASE)

_DEFAULT_ENCODINGS = ("utf-8", "gbk", "gb2312", "latin-1")
_UTF8_BOM = b"\xef\xbb\xbf"


def _decode_text_auto(raw_bytes: bytes) -> tuple[str, str]:
    if raw_bytes.startswith(_UTF8_BOM):
        return raw_bytes.decode("utf-8-sig"), "utf-8-sig"
    for enc in _DEFAULT_ENCODINGS:
        try:
            return raw_bytes.decode(enc), enc
        except (UnicodeDecodeError, LookupError):
            continue
    return raw_bytes.decode("latin-1"), "latin-1"


def _read_text_auto(path: Path) -> str:
    """尝试多种编码读取文件内容，返回字符串。"""
    raw_bytes = path.read_bytes()
    text, _ = _decode_text_auto(raw_bytes)
    return text


def _detect_encoding(path: Path) -> str:
    _, encoding = _decode_text_auto(path.read_bytes())
    return encoding


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
    if raw.startswith("\ufeff"):
        raw = raw.lstrip("\ufeff")
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


def _find_duplicate_extern_names(sections: list[IniSection]) -> list[str]:
    seen: set[str] = set()
    duplicates: set[str] = set()
    for section in sections:
        if not section.is_extern():
            continue
        name_key = section.name.casefold()
        if name_key in seen:
            duplicates.add(section.name)
            continue
        seen.add(name_key)
    return sorted(duplicates)


def _iter_new_key_lines(src_sec: IniSection, dst_keys: set[str]) -> list[str]:
    new_lines: list[str] = []
    seen_src_keys: set[str] = set()
    for line in src_sec.lines:
        if "=" not in line:
            continue
        key = line.split("=", 1)[0].strip()
        key_norm = key.casefold()
        if key_norm in dst_keys or key_norm in seen_src_keys:
            continue
        seen_src_keys.add(key_norm)
        new_lines.append(line)
    return new_lines


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
    src_duplicate_names = _find_duplicate_extern_names(src_sections)
    if src_duplicate_names:
        duplicates = ", ".join(f"[{name}]" for name in src_duplicate_names)
        raise ValueError(f"源 user.ini 存在重复的 extern 段，无法安全同步：{duplicates}")

    duplicate_names = _find_duplicate_extern_names(dst_sections)
    if duplicate_names:
        duplicates = ", ".join(f"[{name}]" for name in duplicate_names)
        raise ValueError(f"目标 user.ini 存在重复的 extern 段，无法安全同步：{duplicates}")

    dst_map: dict[str, IniSection] = {s.name.casefold(): s for s in dst_sections}
    src_map: dict[str, IniSection] = {s.name: s for s in src_sections}

    sections_to_add: list[IniSection] = []
    keys_to_add: list[tuple[IniSection, list[str]]] = []
    already_identical: list[IniSection] = []

    for name, src_sec in src_map.items():
        name_key = name.casefold()
        if name_key not in dst_map:
            sections_to_add.append(src_sec)
        else:
            dst_sec = dst_map[name_key]
            dst_keys = {
                line.split("=", 1)[0].strip().casefold()
                for line in dst_sec.lines
                if "=" in line
            }
            new_lines = _iter_new_key_lines(src_sec, dst_keys)
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
    original_encoding = _detect_encoding(dst_path)
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
            if sec.lines and not sec.lines[-1].endswith(("\n", "\r")):
                parts.append("\n")
            parts.extend(name_to_add_lines[sec.name])

    # 追加全新的段落
    for sec in preview.sections_to_add:
        parts.append(sec.as_text())

    merged_text = "".join(parts)
    # 尽量保持目标文件原始编码；gb2312 失败时退回 gbk。
    try:
        dst_path.write_text(merged_text, encoding=original_encoding)
    except (UnicodeEncodeError, LookupError):
        fallback_encoding = "gbk" if original_encoding == "gb2312" else "utf-8"
        dst_path.write_text(merged_text, encoding=fallback_encoding)
