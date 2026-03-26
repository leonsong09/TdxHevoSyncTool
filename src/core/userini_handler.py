"""user.ini 定向同步与写回。"""
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


@dataclass(frozen=True)
class SectionKeyLine:
    key: str
    value: str
    line: str
    line_idx: int


@dataclass(frozen=True)
class SectionKeyIndex:
    by_key: dict[str, SectionKeyLine]
    duplicate_keys: list[str]


@dataclass(frozen=True)
class MergePreview:
    """合并预览结果。"""

    keys_to_replace: list[tuple[IniSection, list[str]]]
    keys_to_add: list[tuple[IniSection, list[str]]]
    missing_target_sections: list[IniSection]
    already_identical: list[IniSection]


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
        match = _SECTION_RE.match(line.strip())
        if match:
            current = IniSection(name=match.group(1))
            sections.append(current)
            continue
        if current is None:
            header_lines.append(line)
            continue
        current.lines.append(line)

    return sections, header_lines


def get_extern_sections(sections: list[IniSection]) -> list[IniSection]:
    return [section for section in sections if section.is_extern()]


def _parse_key_line(line: str) -> tuple[str, str] | None:
    if "=" not in line:
        return None
    key, value = line.split("=", 1)
    key = key.strip()
    if not key:
        return None
    return key, value.rstrip("\r\n")


def _index_section_keys(section: IniSection) -> SectionKeyIndex:
    by_key: dict[str, SectionKeyLine] = {}
    duplicate_keys: list[str] = []
    seen_duplicates: set[str] = set()
    for line_idx, line in enumerate(section.lines):
        parsed = _parse_key_line(line)
        if parsed is None:
            continue
        key, value = parsed
        key_norm = key.casefold()
        if key_norm in by_key:
            if key_norm not in seen_duplicates:
                duplicate_keys.append(key)
                seen_duplicates.add(key_norm)
            continue
        by_key[key_norm] = SectionKeyLine(key=key, value=value, line=line, line_idx=line_idx)
    return SectionKeyIndex(by_key=by_key, duplicate_keys=duplicate_keys)


def _find_duplicate_section_names(sections: list[IniSection]) -> list[str]:
    seen: set[str] = set()
    duplicates: list[str] = []
    seen_duplicates: set[str] = set()
    for section in sections:
        name_key = section.name.casefold()
        if name_key in seen and name_key not in seen_duplicates:
            duplicates.append(section.name)
            seen_duplicates.add(name_key)
            continue
        seen.add(name_key)
    return duplicates


def _build_replace_lines(
    src_index: SectionKeyIndex,
    dst_index: SectionKeyIndex,
) -> list[str]:
    replace_lines: list[str] = []
    for key_norm, src_key_line in src_index.by_key.items():
        dst_key_line = dst_index.by_key.get(key_norm)
        if dst_key_line is None or dst_key_line.value == src_key_line.value:
            continue
        replace_lines.append(src_key_line.line)
    return replace_lines


def _build_add_lines(
    src_section: IniSection,
    src_index: SectionKeyIndex,
    dst_index: SectionKeyIndex,
) -> list[str]:
    if not src_section.is_extern():
        return []
    add_lines: list[str] = []
    for key_norm, src_key_line in src_index.by_key.items():
        if key_norm in dst_index.by_key:
            continue
        add_lines.append(src_key_line.line)
    return add_lines


def preview_merge(
    src_sections: list[IniSection],
    dst_sections: list[IniSection],
) -> MergePreview:
    """分析源和目标的 section，返回同步预览。"""
    src_duplicate_names = _find_duplicate_section_names(src_sections)
    if src_duplicate_names:
        duplicates = ", ".join(f"[{name}]" for name in src_duplicate_names)
        raise ValueError(f"源 user.ini 存在重复的段，无法安全同步：{duplicates}")

    dst_duplicate_names = _find_duplicate_section_names(dst_sections)
    if dst_duplicate_names:
        duplicates = ", ".join(f"[{name}]" for name in dst_duplicate_names)
        raise ValueError(f"目标 user.ini 存在重复的段，无法安全同步：{duplicates}")

    dst_map = {section.name.casefold(): section for section in dst_sections}
    keys_to_replace: list[tuple[IniSection, list[str]]] = []
    keys_to_add: list[tuple[IniSection, list[str]]] = []
    missing_target_sections: list[IniSection] = []
    already_identical: list[IniSection] = []

    for src_section in src_sections:
        dst_section = dst_map.get(src_section.name.casefold())
        if dst_section is None:
            missing_target_sections.append(src_section)
            continue

        src_index = _index_section_keys(src_section)
        dst_index = _index_section_keys(dst_section)
        if dst_index.duplicate_keys:
            duplicates = ", ".join(dst_index.duplicate_keys)
            raise ValueError(
                f"目标 user.ini 的 [{dst_section.name}] 存在重复键，无法安全同步：{duplicates}"
            )

        replace_lines = _build_replace_lines(src_index, dst_index)
        add_lines = _build_add_lines(src_section, src_index, dst_index)
        if replace_lines:
            keys_to_replace.append((dst_section, replace_lines))
        if add_lines:
            keys_to_add.append((dst_section, add_lines))
        if not replace_lines and not add_lines:
            already_identical.append(src_section)

    return MergePreview(
        keys_to_replace=keys_to_replace,
        keys_to_add=keys_to_add,
        missing_target_sections=missing_target_sections,
        already_identical=already_identical,
    )


def _lines_by_key(lines: list[str]) -> dict[str, str]:
    by_key: dict[str, str] = {}
    for line in lines:
        parsed = _parse_key_line(line)
        if parsed is None:
            continue
        key, _ = parsed
        by_key[key.casefold()] = line
    return by_key


def _replace_section_lines(section: IniSection, replace_by_key: dict[str, str]) -> list[str]:
    updated_lines: list[str] = []
    for line in section.lines:
        parsed = _parse_key_line(line)
        if parsed is None:
            updated_lines.append(line)
            continue
        key, _ = parsed
        updated_lines.append(replace_by_key.get(key.casefold(), line))
    return updated_lines


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

    replace_map = {
        section.name.casefold(): _lines_by_key(lines)
        for section, lines in preview.keys_to_replace
    }
    add_map = {
        section.name.casefold(): lines
        for section, lines in preview.keys_to_add
    }

    parts: list[str] = list(dst_header)
    for section in dst_sections:
        parts.append(f"[{section.name}]\n")
        replaced_lines = _replace_section_lines(
            section,
            replace_map.get(section.name.casefold(), {}),
        )
        parts.extend(replaced_lines)
        add_lines = add_map.get(section.name.casefold(), [])
        if not add_lines:
            continue
        if replaced_lines and not replaced_lines[-1].endswith(("\n", "\r")):
            parts.append("\n")
        parts.extend(add_lines)

    merged_text = "".join(parts)
    try:
        dst_path.write_text(merged_text, encoding=original_encoding)
    except (UnicodeEncodeError, LookupError):
        fallback_encoding = "gbk" if original_encoding == "gb2312" else "utf-8"
        dst_path.write_text(merged_text, encoding=fallback_encoding)
