# user.ini 全板块定向同步 Implementation Plan

> **For agentic workers:** REQUIRED: Use superpowers:subagent-driven-development (if subagents available) or superpowers:executing-plans to implement this plan. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 让源 `user.ini` 的所有 section 按规则同步到目标 `user.ini`：普通 section 仅替换同名异值键，`extern_*` 额外允许追加缺失键，且不新增任何段落。

**Architecture:** 在 `src/core/userini_handler.py` 把当前 extern-only 逻辑升级为按全部 section 感知的行级同步，同时保留最小写回、编码兼容和 `.ini.bak` 备份。`src/ui/userini_dialog.py` 与相关提示文案同步更新为“定向同步”，测试集中覆盖 core 规则、UI 预览和最终写回结果。

**Tech Stack:** Python 3, unittest, pathlib, PyQt6

---

### Task 1: 建立新规则的失败测试

**Files:**
- Modify: `tests/test_userini_handler.py`
- Modify: `tests/test_userini_dialog.py`

- [x] **Step 1: 写失败测试，覆盖普通 section 替换、extern 追加、缺失 section 跳过与重复 key/section 异常**

```python
def test_preview_merge_replaces_existing_value_in_normal_section():
    ...

def test_preview_merge_does_not_add_missing_key_to_normal_section():
    ...

def test_preview_merge_replaces_and_adds_for_extern_section():
    ...

def test_preview_merge_skips_missing_target_section():
    ...

def test_preview_merge_rejects_duplicate_keys_in_target_section():
    ...
```

- [x] **Step 2: 运行针对性测试，确认按预期失败**

Run: `.\\.venv\\Scripts\\python.exe -m unittest discover -s tests -p "test_userini*.py" -v`
Expected: FAIL，暴露当前 extern-only 与不覆盖旧值的旧行为

### Task 2: 实现 core 定向同步逻辑

**Files:**
- Modify: `src/core/userini_handler.py`
- Test: `tests/test_userini_handler.py`

- [x] **Step 1: 为 section 建立 key 索引与重复检测辅助函数**

```python
def _index_section_keys(section: IniSection) -> SectionKeyIndex:
    ...
```

- [x] **Step 2: 重写 `MergePreview`，支持 replace/add/skip-missing 三类结果**

```python
@dataclass(frozen=True)
class MergePreview:
    keys_to_replace: ...
    keys_to_add: ...
    missing_target_sections: ...
```

- [x] **Step 3: 重写 `preview_merge()`，对全部 section 做差异计算**

```python
if src_sec.is_extern():
    ...
else:
    ...
```

- [x] **Step 4: 重写 `apply_merge()`，原位替换 key，且仅对 extern 追加缺失 key**

```python
for line in sec.lines:
    if key in replacements:
        ...
```

- [x] **Step 5: 运行 core 测试，确认转绿**

Run: `.\\.venv\\Scripts\\python.exe -m unittest discover -s tests -p "test_userini_handler.py" -v`
Expected: PASS

### Task 3: 更新 UI 与用户可见文案

**Files:**
- Modify: `src/ui/userini_dialog.py`
- Modify: `src/ui/main_window.py`
- Modify: `src/ui/help_dialog.py`
- Modify: `src/ui/compare_view.py`
- Modify: `src/ui/data_panel.py`
- Modify: `src/core/data_items.py`
- Modify: `README.md`
- Test: `tests/test_userini_dialog.py`

- [x] **Step 1: 调整对话框标题、按钮文字与预览说明，反映“全板块定向同步”**

- [x] **Step 2: 让源/目标列表显示全部 section，预览中区分替换、extern 追加与缺失 section 跳过**

- [x] **Step 3: 更新帮助文档与说明文案，保持与真实行为一致**

- [x] **Step 4: 运行 UI 与说明相关测试**

Run: `.\\.venv\\Scripts\\python.exe -m unittest discover -s tests -p "test_userini_dialog.py" -v`
Expected: PASS

### Task 4: 完整验证与发布准备

**Files:**
- Modify: `pyproject.toml`
- Modify: `src/core/version.py`
- Modify: `docs/superpowers/specs/2026-03-26-userini-extern-sync-design.md`
- Modify: `docs/superpowers/plans/2026-03-26-userini-extern-sync.md`

- [x] **Step 1: 运行本次变更直接相关的测试集**

Run: `.\\.venv\\Scripts\\python.exe -m unittest discover -s tests -p "test_*.py" -v`
Expected: PASS

- [x] **Step 2: 按仓库版本约定更新版本号**

```python
version = "1.0.x"
APP_VERSION = "1.0.x"
```

- [x] **Step 3: 运行打包脚本验证发布产物可生成**

Run: `cmd /c "echo.|build_gui.bat"`
Expected: `dist\\TdxHevoSyncTool.exe` 生成成功

- [x] **Step 4: 复查 git diff，仅保留本次同步与发布相关文件**

Run: `git diff -- src/core/userini_handler.py src/ui/userini_dialog.py src/ui/main_window.py src/ui/help_dialog.py src/ui/compare_view.py src/ui/data_panel.py src/core/data_items.py tests/test_userini_handler.py tests/test_userini_dialog.py README.md pyproject.toml src/core/version.py docs/superpowers/specs/2026-03-26-userini-extern-sync-design.md docs/superpowers/plans/2026-03-26-userini-extern-sync.md`
Expected: 只包含本次 user.ini 定向同步与发布文案

### Task 5: 提交与推送

**Files:**
- Modify: `git index`

- [ ] **Step 1: 以清晰提交信息提交本次变更**

Run: `git commit -m "✨ feat(userini): 扩展全板块定向同步规则"`
Expected: commit 成功

- [ ] **Step 2: 推送到当前分支**

Run: `git push`
Expected: push 成功
