# user.ini extern 安全同步 Implementation Plan

> **For agentic workers:** REQUIRED: Use superpowers:subagent-driven-development (if subagents available) or superpowers:executing-plans to implement this plan. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 让源 `user.ini` 的 `extern_*` 设置能安全同步到第二个通达信的 `user.ini`，避免 BOM、重复段和换行边界导致的错误写入。

**Architecture:** 先在 `src/core/userini_handler.py` 修复解析和合并语义，再在 `src/ui/userini_dialog.py` 把异常目标结构显式提示给用户。测试集中放在新的 `tests/test_userini_handler.py`，覆盖解析、预览和写回三个层面。

**Tech Stack:** Python 3, unittest, pathlib, PyQt6

---

### Task 1: 为 user.ini 合并行为建立回归测试

**Files:**
- Create: `tests/test_userini_handler.py`
- Test: `tests/test_userini_handler.py`

- [x] **Step 1: 写失败测试，覆盖 BOM、重复段、末行无换行、源段重复键、已有键不覆盖**

```python
def test_parse_ini_supports_utf8_bom_first_section():
    ...

def test_preview_merge_rejects_duplicate_extern_sections_in_target():
    ...

def test_apply_merge_inserts_newline_before_appended_keys():
    ...

def test_preview_merge_dedupes_duplicate_keys_from_source_section():
    ...

def test_preview_merge_keeps_existing_target_value():
    ...
```

- [x] **Step 2: 运行测试，确认按预期失败**

Run: `python -m unittest tests.test_userini_handler -v`
Expected: FAIL，暴露当前解析/合并的边界问题

### Task 2: 修复 core 合并逻辑

**Files:**
- Modify: `src/core/userini_handler.py`
- Test: `tests/test_userini_handler.py`

- [x] **Step 1: 修复 `parse_ini()` 的 BOM 兼容**

```python
raw = _read_text_auto(path)
if raw.startswith("\ufeff"):
    raw = raw.lstrip("\ufeff")
```

- [x] **Step 2: 在预览阶段检测目标重复 `extern_*` 段并抛出明确异常**

```python
raise ValueError("目标 user.ini 存在重复的 extern 段：[...]")
```

- [x] **Step 3: 让源段内部重复键只保留第一次出现，且已有目标键不覆盖**

```python
seen_src_keys = set()
for line in src_sec.lines:
    ...
```

- [x] **Step 4: 追加键时补足目标段尾部换行，避免写出 `A=1B=2`**

```python
if sec.lines and not sec.lines[-1].endswith(("\n", "\r")):
    parts.append("\n")
```

- [x] **Step 5: 运行测试，确认 core 行为转绿**

Run: `python -m unittest tests.test_userini_handler -v`
Expected: PASS

### Task 3: 修复 UI 对异常目标结构的反馈

**Files:**
- Modify: `src/ui/userini_dialog.py`
- Test: `tests/test_userini_handler.py`

- [x] **Step 1: 在 `_on_preview()` 捕获重复段异常并阻止确认合并**

```python
except ValueError as exc:
    QMessageBox.warning(self, "预览失败", str(exc))
    self._preview = None
    self._apply_btn.setEnabled(False)
    return
```

- [x] **Step 2: 保持现有成功路径和 `.ini.bak` 提示不变**

- [x] **Step 3: 运行针对性测试和已有相关测试**

Run: `python -m unittest tests.test_userini_handler tests.test_importer_folder_forbidden -v`
Expected: PASS

### Task 4: 最终验证

**Files:**
- Modify: `src/core/userini_handler.py`
- Modify: `src/ui/userini_dialog.py`
- Create: `tests/test_userini_handler.py`

- [x] **Step 1: 运行本次变更直接相关的测试集**

Run: `python -m unittest tests.test_userini_handler tests.test_importer_folder_forbidden tests.test_compare_and_plan -v`
Expected: PASS

- [x] **Step 2: 复查 git diff，仅保留本次修复相关文件**

Run: `git diff -- src/core/userini_handler.py src/ui/userini_dialog.py tests/test_userini_handler.py docs/superpowers/specs/2026-03-26-userini-extern-sync-design.md docs/superpowers/plans/2026-03-26-userini-extern-sync.md`
Expected: 只包含本次同步修复与文档
