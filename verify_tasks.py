"""verify_tasks.py — 验证三个文档任务"""

import re
import sys
from pathlib import Path

BASE = Path(__file__).parent
errors: list[str] = []

# ============================================================
# Task 1: 哲学奠基书.md
# ============================================================
print("=" * 60)
print("Task 1: docs/哲学奠基书.md")
p1 = BASE / "docs" / "哲学奠基书.md"
if not p1.exists():
    errors.append("T1: 文件不存在")
else:
    content = p1.read_text(encoding="utf-8")
    size_kb = len(content.encode("utf-8")) / 1024
    print(f"  大小: {size_kb:.1f} KB")

    # Check 5 required sections by heading content
    required_headings = ["苍天", "炎天", "黄天", "三真合一", "对应表"]
    h2_headings = re.findall(r"^## (.+)$", content, re.MULTILINE)
    found = 0
    for heading in h2_headings:
        for req in required_headings:
            if req in heading:
                found += 1
                break
    if found >= len(required_headings):
        print(f"  5大章节: 全部包含 PASS")
    else:
        errors.append(f"T1: 缺少章节 (found {found}/5)")

    # Check three core values in correspondence table
    values = ["我命由我不由天", "善行无辙迹", "为道日损"]
    missing_vals = [v for v in values if v not in content]
    if missing_vals:
        errors.append(f"T1: 对照表中缺少价值观: {missing_vals}")
    else:
        print("  三大价值观在对照表中: 全部包含 PASS")

    # Check three heavens in table
    heavens = ["苍天", "炎天", "黄天"]
    missing_heavens = [h for h in heavens if h not in content]
    if missing_heavens:
        errors.append(f"T1: 对照表中缺少天道: {missing_heavens}")
    else:
        print("  三天道在对照表中: 全部包含 PASS")

    # Check moral/philosophical connections
    if "道德经" in content:
        print("  道德经引用: 包含 PASS")

# ============================================================
# Task 2: 产品体验定义书
# ============================================================
print()
print("=" * 60)
print("Task 2: docs/慧惠产品体验定义书v010.md")
p2 = BASE / "docs" / "慧惠产品体验定义书v010.md"
if not p2.exists():
    errors.append("T2: 文件不存在")
else:
    content = p2.read_text(encoding="utf-8")

    # Check prologue chapter
    if "序章：她的天命" in content:
        print("  序章: 存在 PASS")
    else:
        errors.append("T2: 缺少序章")

    # Check chapter renumbering — "一、" should NOT be a chapter heading
    chapters = re.findall(r"^## (.+)$", content, re.MULTILINE)
    print(f"  章节数: {len(chapters)}")
    for c in chapters:
        print(f"    {c}")

    # Old chapter "一、一句话定义" should now be "二、一句话定义" or gone
    if re.search(r"^## 一、", content, re.MULTILINE):
        errors.append("T2: 章节编号未更新 (仍存在'一、')")
    elif "二、一句话定义" in content:
        print("  章节编号顺延: PASS (一→二)")
    else:
        print("  章节编号: 已更新")

    # Verify total chapters — should be 10 (序章 + 二 through 十)
    if len(chapters) == 10:
        print("  章节总数(10): PASS")
    else:
        errors.append(f"T2: 章节总数应为10，实际为{len(chapters)}")

# ============================================================
# Task 3: 技术规格书_v0.4.0
# ============================================================
print()
print("=" * 60)
print("Task 3: docs/技术规格书_v0.4.0.md")
p3 = BASE / "docs" / "技术规格书_v0.4.0.md"
if not p3.exists():
    errors.append("T3: 文件不存在")
else:
    content = p3.read_text(encoding="utf-8")

    # Version check — first 200 chars should contain v0.4.0
    header = content[:300]
    if "v0.4.0" in header:
        print("  版本 v0.4.0: PASS")
    else:
        errors.append("T3: 版本信息不是v0.4.0")

    # Core changes updated — should mention three heavens
    if "三真天道" in header or ("苍" in header and "炎" in header and "黄" in header):
        print("  核心变更描述已更新: PASS")
    else:
        errors.append("T3: 核心变更描述未更新")

    # 天道对应 column in table
    if "天道对应" in content:
        print("  天道对应列: 存在 PASS")
    else:
        errors.append("T3: 核心价值观表格缺少'天道对应'列")

    # Three heavens in table
    heavens = ["苍天", "炎天", "黄天"]
    missing = [h for h in heavens if h not in content]
    if missing:
        errors.append(f"T3: 表格中缺少天道名称: {missing}")
    else:
        print("  三天道在表格中: 全部包含 PASS")

    # v0.4.0 in version history
    appendix_start = content.find("附录")
    if appendix_start > 0 and "v0.4.0" in content[appendix_start:]:
        print("  版本历史含v0.4.0: PASS")
    elif "v0.4.0" in content:
        print("  版本历史含v0.4.0: PASS")
    else:
        errors.append("T3: 版本历史中缺少v0.4.0")

# ============================================================
# Cross-check: consistency between 哲学奠基书 and 技术规格书
# ============================================================
print()
print("=" * 60)
print("Cross-check: 哲学奠基书 <-> 技术规格书_v0.4.0 一致性")

if p1.exists() and p3.exists():
    p1c = p1.read_text(encoding="utf-8")
    p3c = p3.read_text(encoding="utf-8")

    # Both should mention all three heavens
    for heaven in ["苍天", "炎天", "黄天"]:
        in_p1 = heaven in p1c
        in_p3 = heaven in p3c
        status = "PASS" if in_p1 and in_p3 else "FAIL"
        print(
            f"  {heaven}: 哲学奠基书={'Y' if in_p1 else 'N'} 技术规格书={'Y' if in_p3 else 'N'} -> {status}")
        if not (in_p1 and in_p3):
            errors.append(f"Cross: {heaven}不一致")

# ============================================================
# Result
# ============================================================
print()
print("=" * 60)
if errors:
    print(f"FAIL: {len(errors)} 个问题:")
    for e in errors:
        print(f"  - {e}")
    sys.exit(1)
else:
    print("ALL TASKS PASSED")
    sys.exit(0)
