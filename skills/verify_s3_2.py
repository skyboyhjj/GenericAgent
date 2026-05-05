#!/usr/bin/env python3
"""
S3-2: WoodGrower 木·生增强 验证脚本

验证项：
 1. 初始化：WoodGrower(registry) 创建成功，默认配置加载
 2. should_trigger_distill — 成功工具调用次数 ≥3 时返回 True
 3. should_trigger_distill — 成功工具调用次数 <3 时返回 False
 4. should_trigger_distill — 空历史返回 False
 5. build_distill_prompt — 返回非空字符串，含关键指令词
 6. post_validate — 无违规的 SOP 通过校验
 7. post_validate — 含绝对路径的 SOP 被检测并自动修复
 8. post_validate — 含日期的 SOP 被检测并自动修复
 9. post_validate — 缺少行动验证引用的 SOP 标记为 warning
10. post_validate — 关闭 auto_fix 时仅检测不修改
11. post_validate — 多违规同时存在时全部检测并分类
12. post_validate — 修复后的 SOP 不含违规内容
13. 禁用开关：config.enabled = False 时 should_trigger_distill 始终 False
14. 产物质量：自动修复后 SOP 行数 ≤ max_sop_lines
15. 与 SkillRegistry 兼容：WoodGrower 可接受 SkillRegistry 实例
"""

import shutil
from skills.skill_registry import SkillRegistry
from skills.wood_grower import (
    WoodGrower,
    WoodGrowerConfig,
    ValidationRule,
    ValidationResult,
    DEFAULT_RULES,
)
import sys
import os
import tempfile
from pathlib import Path

# 项目根
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))


PASS = "[PASS]"
FAIL = "[FAIL]"

passed = 0
failed = 0


def check(condition, desc):
    global passed, failed
    if condition:
        print(f"  {PASS} {desc}")
        passed += 1
    else:
        print(f"  {FAIL} {desc}")
        failed += 1


# ===========================================================================
# Setup
# ===========================================================================

print("=" * 60)
print("S3-2 WoodGrower 木·生增强 Tests")
print("=" * 60)

# 创建临时 SkillRegistry（用于兼容性测试）
tmp_dir = Path(tempfile.mkdtemp(prefix="s3_2_test_"))
tmp_registry_path = tmp_dir / "skill_registry.yaml"
registry = SkillRegistry(str(tmp_registry_path))

# ===========================================================================
# Test 1: Initialization
# ===========================================================================
print("\n[Test 1] WoodGrower initialization")
grower = WoodGrower(registry)
check(grower is not None, "WoodGrower created successfully")
check(grower.config.enabled is True, "Default config: enabled=True")
check(grower.config.min_tool_calls == 3, "Default config: min_tool_calls=3")
check(grower.config.post_validate is True,
      "Default config: post_validate=True")
check(grower.config.auto_fix is True, "Default config: auto_fix=True")
check(grower.config.max_sop_lines == 100, "Default config: max_sop_lines=100")

# 自定义 config
custom_config = WoodGrowerConfig(enabled=False, min_tool_calls=5)
grower_custom = WoodGrower(registry, config=custom_config)
check(grower_custom.config.enabled is False, "Custom config: enabled=False")
check(grower_custom.config.min_tool_calls ==
      5, "Custom config: min_tool_calls=5")

# ===========================================================================
# Test 2: should_trigger_distill — ≥3 次成功工具调用 → True
# ===========================================================================
print("\n[Test 2] should_trigger_distill: ≥3 successes → True")
history_many = [
    {"type": "tool_call", "name": "read_file", "result": "ok"},
    {"type": "tool_call", "name": "write_file", "result": "ok"},
    {"type": "tool_call", "name": "execute", "result": "ok"},
    {"type": "tool_call", "name": "search", "result": "ok"},
]
result = grower.should_trigger_distill(history_many)
check(result is True, "4 successful tool_calls → True")

# ===========================================================================
# Test 3: should_trigger_distill — <3 次成功工具调用 → False
# ===========================================================================
print("\n[Test 3] should_trigger_distill: <3 successes → False")
history_few = [
    {"type": "tool_call", "name": "read_file", "result": "ok"},
    {"type": "tool_call", "name": "write_file", "result": "ok"},
]
result = grower.should_trigger_distill(history_few)
check(result is False, "2 successful tool_calls → False")

# ===========================================================================
# Test 4: should_trigger_distill — 空历史 → False
# ===========================================================================
print("\n[Test 4] should_trigger_distill: empty history → False")
check(grower.should_trigger_distill([]) is False, "Empty list → False")
check(grower.should_trigger_distill(None) is False, "None → False")

# ===========================================================================
# Test 5: build_distill_prompt — 返回非空字符串，含关键指令词
# ===========================================================================
print("\n[Test 5] build_distill_prompt: non-empty with key instructions")
prompt = grower.build_distill_prompt()
check(len(prompt) > 0, "Prompt is non-empty")
check("start_long_term_update" in prompt, "Contains 'start_long_term_update'")
check("Do NOT include absolute paths" in prompt,
      "Contains absolute paths warning")
check("Do NOT include dates" in prompt, "Contains dates warning")
check("axiom" in prompt.lower() or "Axiom" in prompt, "Contains axiom reference")

# ===========================================================================
# Test 6: post_validate — 无违规的 SOP 通过校验
# ===========================================================================
print("\n[Test 6] post_validate: clean SOP passes")
clean_sop = tmp_dir / "clean_sop.md"
clean_sop.write_text(
    "# Test SOP\n\n"
    "## Steps\n"
    "1. Use file_read tool to check config\n"
    "2. Execute the verified command\n"
    "3. Confirm output matches expected result\n",
    encoding="utf-8",
)
result = grower.post_validate(str(clean_sop))
check(result.passed is True, "Clean SOP passes validation")
check(len(result.violations) == 0, "No violations detected")
check(len(result.warnings) == 0, "No warnings (R4 action refs present)")
check(result.original_sop == result.fixed_sop, "Fixed SOP equals original")

# ===========================================================================
# Test 7: post_validate — 含绝对路径的 SOP 被检测并自动修复
# ===========================================================================
print("\n[Test 7] post_validate: absolute paths detected and auto-fixed")
abs_path_sop = tmp_dir / "abs_path_sop.md"
abs_path_sop.write_text(
    "# SOP with absolute paths\n\n"
    "The file is at D:\\GenericAgent\\memory\\config.json\n"
    "Another reference: E:\\data\\input.csv\n",
    encoding="utf-8",
)
result = grower.post_validate(str(abs_path_sop))
check(len(result.violations) >= 1, "Absolute path violations detected")
check(any(v["rule_id"] == "R1" for v in result.violations), "R1 rule triggered")
check(len(result.auto_fixed) >= 1, "Auto-fix applied")
check("D:\\" not in result.fixed_sop and "E:\\" not in result.fixed_sop,
      "Fixed SOP no longer contains absolute paths")
check(result.passed is True, "Passes after auto-fix")

# ===========================================================================
# Test 8: post_validate — 含日期的 SOP 被检测并自动修复
# ===========================================================================
print("\n[Test 8] post_validate: dates detected and auto-fixed")
date_sop = tmp_dir / "date_sop.md"
date_sop.write_text(
    "# SOP with dates\n\n"
    "Created on 2026-05-03 by the system.\n"
    "Last updated: 2025-12-25.\n"
    "This line has no date.\n",
    encoding="utf-8",
)
result = grower.post_validate(str(date_sop))
check(len(result.violations) >= 1, "Date violations detected")
check(any(v["rule_id"] == "R2" for v in result.violations), "R2 rule triggered")

# Check that dates were removed in auto-fix (delete_line)
check("2026-05-03" not in result.fixed_sop, "Date 2026-05-03 removed")
check("2025-12-25" not in result.fixed_sop, "Date 2025-12-25 removed")
check(result.passed is True, "Passes after auto-fix")

# ===========================================================================
# Test 9: post_validate — 缺少行动验证引用，标记 warning
# ===========================================================================
print("\n[Test 9] post_validate: missing action verification → warning")
no_action_sop = tmp_dir / "no_action_sop.md"
no_action_sop.write_text(
    "# SOP without action references\n\n"
    "## Steps\n"
    "1. Do something.\n"
    "2. Do another thing.\n"
    "3. That's all.\n",
    encoding="utf-8",
)
result = grower.post_validate(str(no_action_sop))
check(result.passed is True, "Passes (R4 is warning only, no errors)")
check(len(result.warnings) >= 1, "Warning raised for missing action references")
check(any(w["rule_id"] == "R4" for w in result.warnings),
      "R4 warning: SOP lacks action verification references")
check(len(result.violations) == 0, "No error violations (R4 is warning)")

# ===========================================================================
# Test 10: post_validate — 关闭 auto_fix 时仅检测不修改
# ===========================================================================
print("\n[Test 10] post_validate: auto_fix=False only detects, no modification")
grower_no_fix = WoodGrower(registry, config=WoodGrowerConfig(auto_fix=False))
bad_sop = tmp_dir / "bad_sop_no_fix.md"
bad_sop_content = "# Bad SOP\n\nPath: D:\\data\\file.txt\nDate: 2026-05-03\n"
bad_sop.write_text(bad_sop_content, encoding="utf-8")
result = grower_no_fix.post_validate(str(bad_sop))
check(len(result.violations) >= 1, "Violations detected even without auto_fix")
check(len(result.auto_fixed) == 0, "No auto-fixes applied")
check(result.fixed_sop == result.original_sop, "Content unchanged")
check(result.passed is False, "Does not pass (violations unfixed)")

# ===========================================================================
# Test 11: post_validate — 多违规同时存在时全部检测并分类
# ===========================================================================
print("\n[Test 11] post_validate: multiple violations all detected and classified")
multi_bad_sop = tmp_dir / "multi_bad_sop.md"
multi_bad_sop.write_text(
    "# Multi-violation SOP\n\n"
    "Path: D:\\GenericAgent\\data\\file.txt\n"
    "Created: 2026-05-03\n"
    "User home: C:\\Users\\test\\config.json\n"
    "No action words here.\n",
    encoding="utf-8",
)
result = grower.post_validate(str(multi_bad_sop))
rule_ids = {v["rule_id"] for v in result.violations}
check("R1" in rule_ids, "R1 (absolute path) detected")
check("R2" in rule_ids, "R2 (date) detected")
check("R3" in rule_ids, "R3 (env-specific) detected")
check(len(result.violations) >= 3, "At least 3 violations detected")
check(len(result.auto_fixed) >= 2, "At least 2 auto-fixes applied")

# ===========================================================================
# Test 12: post_validate — 修复后的 SOP 不含违规内容
# ===========================================================================
print("\n[Test 12] post_validate: fixed SOP clean of violations")
result = grower.post_validate(str(multi_bad_sop))
# After fix, re-validate the fixed content
check("D:\\" not in result.fixed_sop, "No absolute paths in fixed SOP")
check("2026-05-03" not in result.fixed_sop, "No dates in fixed SOP")
check("C:\\Users\\" not in result.fixed_sop,
      "No env-specific paths in fixed SOP")
# Re-read the actual file to confirm it was written with fixes
actual_fixed = multi_bad_sop.read_text(encoding="utf-8")
check("D:\\" not in actual_fixed, "File on disk: no absolute paths")
check("2026-05-03" not in actual_fixed, "File on disk: no dates")

# ===========================================================================
# Test 13: 禁用开关 — config.enabled = False 时全部返回安全默认值
# ===========================================================================
print("\n[Test 13] Disabled switch: enabled=False returns safe defaults")
grower_off = WoodGrower(registry, config=WoodGrowerConfig(enabled=False))
# should_trigger_distill should always return False
check(grower_off.should_trigger_distill(history_many) is False,
      "should_trigger_distill → False when disabled")
check(grower_off.should_trigger_distill([]) is False,
      "should_trigger_distill([]) → False when disabled")
# build_distill_prompt should return empty string
check(grower_off.build_distill_prompt() == "",
      "build_distill_prompt → empty string when disabled")

# ===========================================================================
# Test 14: 产物质量 — 自动修复后 SOP 行数 ≤ max_sop_lines
# ===========================================================================
print("\n[Test 14] Product quality: fixed SOP ≤ max_sop_lines")
# Create a long SOP that should still be under 100 lines after fix
long_lines = ["# Long SOP\n\n"]
for i in range(90):
    long_lines.append(f"Step {i}: verified output confirmed via tool_call.\n")
long_sop = tmp_dir / "long_sop.md"
long_sop.write_text("".join(long_lines), encoding="utf-8")
result = grower.post_validate(str(long_sop))
fixed_line_count = len(result.fixed_sop.split("\n"))
check(fixed_line_count <= grower.config.max_sop_lines,
      f"Fixed SOP has {fixed_line_count} lines ≤ {grower.config.max_sop_lines}")

# Also test with a shorter SOP containing violations that get fixed
short_bad = tmp_dir / "short_bad_sop.md"
short_bad.write_text(
    "D:\\path\\to\\file\n2026-05-03\nSome valid content.\n" * 5,
    encoding="utf-8",
)
result = grower.post_validate(str(short_bad))
fixed_lines = len(result.fixed_sop.split("\n"))
check(fixed_lines <= grower.config.max_sop_lines,
      f"Fixed SOP ({fixed_lines} lines) ≤ max_sop_lines ({grower.config.max_sop_lines})")

# ===========================================================================
# Test 15: SkillRegistry 兼容性
# ===========================================================================
print("\n[Test 15] SkillRegistry compatibility")
check(grower._registry is registry, "Registry instance stored correctly")
check(grower._registry.get_skill_count is not None,
      "Registry has expected methods")

# Verify WoodGrower can work with a different SkillRegistry instance
registry2 = SkillRegistry(str(tmp_dir / "reg2.yaml"))
grower2 = WoodGrower(registry2)
check(grower2._registry is registry2, "Second registry instance works")

# ===========================================================================
# Cleanup
# ===========================================================================
shutil.rmtree(tmp_dir, ignore_errors=True)

# ===========================================================================
# Summary
# ===========================================================================
print("\n" + "=" * 60)
total = passed + failed
print(f"Results: {passed}/{total} passed, {failed}/{total} failed")
if failed == 0:
    print("S3-2 ALL TESTS PASSED")
    sys.exit(0)
else:
    print(f"S3-2 FAILED: {failed} test(s)")
    sys.exit(1)
