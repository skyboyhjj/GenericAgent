#!/usr/bin/env python3
"""
S3-3: MetalRestrainer 金·克修剪 验证脚本

验证项：
 1. 初始化：MetalRestrainer(registry) 创建成功，默认配置加载
 2. 健康度计算：evaluate() 返回有效 HealthReport，且 health_score ∈ [0,1]
 3. 新鲜度衰减：距上次使用 90 天的技能健康度 < 0.5
 4. 可靠性影响：success_rate=0.5 的技能可靠性得分 = 0.5
 5. 复杂度加分：tool_count ≥ 5 的技能获得满分复杂度加分
 6. 边界情况：use_count=0 的技能使用默认可靠性 0.5
 7. evaluate_all() 返回所有活跃技能报告，跳过白名单
 8. evaluate_all() 返回按健康度升序排列
 9. archive() 后技能状态变为 archived
10. archive() 后 get_active_skills() 不再包含该技能
11. restore() 后技能恢复为 active
12. get_archived_skills() 返回正确列表
13. 白名单技能 evaluate() 返回健康度 1.0
14. 白名单技能 archive() 返回 False（拒绝归档）
15. dry_run=True 时 archive() 不实际归档
16. 禁用开关：config.enabled=False 时 evaluate_all() 返回空列表
"""

from skills.metal_restrainer import (
    MetalRestrainer,
    MetalRestrainerConfig,
    HealthReport,
)
from skills.skill_registry import (
    SkillRegistry,
    SkillMeta,
    STATUS_ACTIVE,
    STATUS_ARCHIVED,
)
import sys
import math
from pathlib import Path
from datetime import datetime, timezone, timedelta

# 项目根
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))


# ---------------------------------------------------------------------------
# 测试工具
# ---------------------------------------------------------------------------

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


def assert_close(actual, expected, desc, tolerance=0.01):
    """验证浮点数近似相等"""
    ok = abs(actual - expected) < tolerance
    check(ok, f"{desc} (actual={actual:.4f}, expected={expected:.4f})")


# ---------------------------------------------------------------------------
# Setup
# ---------------------------------------------------------------------------

print("=" * 60)
print("S3-3 MetalRestrainer 金·克修剪 Tests")
print("=" * 60)

# 创建 SkillRegistry
registry = SkillRegistry()
now = datetime.now(timezone.utc)
now_str = now.strftime("%Y-%m-%dT%H:%M:%S")

# 注册测试技能
# 技能 A: 最近使用，use_count 高，成功率高 — 应该很健康
meta_a = SkillMeta(
    name="skill_healthy",
    file="memory/skill_healthy_sop.md",
    use_count=10,
    success_rate=0.95,
    last_used=now_str,
    created_at=now_str,
    status=STATUS_ACTIVE,
)
# 技能 B: 90 天未使用，成功率低 — 应该不健康
ninety_days_ago = (now - timedelta(days=90)).strftime("%Y-%m-%dT%H:%M:%S")
meta_b = SkillMeta(
    name="skill_stale",
    file="memory/skill_stale_sop.md",
    use_count=5,
    success_rate=0.4,
    last_used=ninety_days_ago,
    created_at=(now - timedelta(days=180)).strftime("%Y-%m-%dT%H:%M:%S"),
    status=STATUS_ACTIVE,
)
# 技能 C: 从未使用 — 应该使用默认值
meta_c = SkillMeta(
    name="skill_unused",
    file="memory/skill_unused_sop.md",
    use_count=0,
    success_rate=1.0,
    last_used=now_str,
    created_at=now_str,
    status=STATUS_ACTIVE,
)
# 技能 D: success_rate=0.5 — 可靠性测试
meta_d = SkillMeta(
    name="skill_half_reliable",
    file="memory/skill_half_reliable_sop.md",
    use_count=8,
    success_rate=0.5,
    last_used=now_str,
    created_at=now_str,
    status=STATUS_ACTIVE,
)
# 技能 E: 用于测试归档
meta_e = SkillMeta(
    name="skill_to_archive",
    file="memory/skill_to_archive_sop.md",
    use_count=2,
    success_rate=0.3,
    last_used=ninety_days_ago,
    created_at=(now - timedelta(days=200)).strftime("%Y-%m-%dT%H:%M:%S"),
    status=STATUS_ACTIVE,
)
# 白名单技能
meta_wl = SkillMeta(
    name="memory_management_sop",
    file="memory/memory_management_sop.md",
    use_count=100,
    success_rate=1.0,
    last_used=now_str,
    created_at=now_str,
    status=STATUS_ACTIVE,
)

registry.register("skill_healthy", meta_a)
registry.register("skill_stale", meta_b)
registry.register("skill_unused", meta_c)
registry.register("skill_half_reliable", meta_d)
registry.register("skill_to_archive", meta_e)
registry.register("memory_management_sop", meta_wl)

# SkillRegistry.register() 会覆盖 last_used 和 created_at 为当前时间，
# 因此需要在注册后手动恢复为测试需要的值。
meta_b.last_used = ninety_days_ago
meta_b.created_at = (now - timedelta(days=180)).strftime("%Y-%m-%dT%H:%M:%S")
meta_e.last_used = ninety_days_ago
meta_e.created_at = (now - timedelta(days=200)).strftime("%Y-%m-%dT%H:%M:%S")

# ===========================================================================
# Test 1: Initialization
# ===========================================================================
print("\n[Test 1] MetalRestrainer initialization")
restrainer = MetalRestrainer(registry)
check(restrainer is not None, "MetalRestrainer created successfully")
check(restrainer.config.enabled is True, "Default config: enabled=True")
check(restrainer.config.archive_threshold == 0.3,
      "Default config: archive_threshold=0.3")
check(restrainer.config.warning_threshold == 0.5,
      "Default config: warning_threshold=0.5")
check(restrainer.config.freshness_decay == 0.02,
      "Default config: freshness_decay=0.02")
check(restrainer.config.weights == (0.4, 0.4, 0.2),
      "Default config: weights=(0.4, 0.4, 0.2)")
check(restrainer.config.dry_run is False, "Default config: dry_run=False")
check("memory_management_sop" in restrainer.config.whitelist,
      "Whitelist contains memory_management_sop")

# 自定义 config
custom_config = MetalRestrainerConfig(
    enabled=False,
    archive_threshold=0.2,
    warning_threshold=0.4,
    dry_run=True,
)
restrainer_custom = MetalRestrainer(registry, config=custom_config)
check(restrainer_custom.config.enabled is False, "Custom config: enabled=False")
check(restrainer_custom.config.archive_threshold == 0.2,
      "Custom config: archive_threshold=0.2")
check(restrainer_custom.config.dry_run is True, "Custom config: dry_run=True")

# ===========================================================================
# Test 2: Health calculation — evaluate() returns valid HealthReport
# ===========================================================================
print("\n[Test 2] evaluate() returns valid HealthReport with score in [0,1]")
report = restrainer.evaluate("skill_healthy")
check(isinstance(report, HealthReport), "Report is HealthReport instance")
check(report.skill_id == "skill_healthy", "skill_id correct")
check(0.0 <= report.health_score <= 1.0,
      f"health_score ({report.health_score:.4f}) ∈ [0,1]")
check(0.0 <= report.freshness <= 1.0,
      f"freshness ({report.freshness:.4f}) ∈ [0,1]")
check(0.0 <= report.reliability <= 1.0,
      f"reliability ({report.reliability:.4f}) ∈ [0,1]")
check(report.use_count == 10, "use_count correct")
check(report.recommendation in ("archive", "warn", "keep"),
      f"recommendation '{report.recommendation}' valid")

# ===========================================================================
# Test 3: Freshness decay — 90 days since last use → health < 0.5
# ===========================================================================
print("\n[Test 3] Freshness decay: 90 days → health < 0.5")
report_stale = restrainer.evaluate("skill_stale")
check(report_stale.health_score < 0.5,
      f"Stale skill health ({report_stale.health_score:.4f}) < 0.5")
check(report_stale.days_since_last_use >= 89,
      f"days_since_last_use ({report_stale.days_since_last_use}) >= 89")

# 验证新鲜度衰减公式: exp(-0.02 * 90) ≈ exp(-1.8) ≈ 0.165
expected_freshness = math.exp(-0.02 * report_stale.days_since_last_use)
assert_close(report_stale.freshness, expected_freshness,
             f"Freshness matches exp(-λ*days) formula")

# ===========================================================================
# Test 4: Reliability impact — success_rate=0.5 → reliability=0.5
# ===========================================================================
print("\n[Test 4] Reliability impact: success_rate=0.5 → reliability=0.5")
report_half = restrainer.evaluate("skill_half_reliable")
assert_close(report_half.reliability, 0.5,
             "reliability = 0.5 for success_rate=0.5 skill")

# ===========================================================================
# Test 5: Complexity bonus — tool_count ≥ 5 → full bonus
# ===========================================================================
print("\n[Test 5] Complexity bonus: tool_count >= 5 → full bonus")
# 给技能设置 tool_count
meta_5 = SkillMeta(
    name="skill_complex",
    file="memory/skill_complex_sop.md",
    use_count=10,
    success_rate=1.0,
    last_used=now_str,
    created_at=now_str,
    status=STATUS_ACTIVE,
)
meta_5.tool_count = 5
registry.register("skill_complex", meta_5)

report_complex = restrainer.evaluate("skill_complex")
assert_close(report_complex.complexity_bonus, 1.0,
             "complexity_bonus = 1.0 for tool_count=5")

# tool_count=2 → bonus = 0.4
meta_2 = SkillMeta(
    name="skill_simple",
    file="memory/skill_simple_sop.md",
    use_count=10,
    success_rate=1.0,
    last_used=now_str,
    created_at=now_str,
    status=STATUS_ACTIVE,
)
meta_2.tool_count = 2
registry.register("skill_simple", meta_2)

report_simple = restrainer.evaluate("skill_simple")
assert_close(report_simple.complexity_bonus, 0.4,
             "complexity_bonus = 0.4 for tool_count=2")

# ===========================================================================
# Test 6: Boundary — use_count=0 → default reliability 0.5
# ===========================================================================
print("\n[Test 6] Boundary: use_count=0 → defaults")
report_unused = restrainer.evaluate("skill_unused")
check(report_unused.use_count == 0, "use_count=0 confirmed")
check(report_unused.freshness == 1.0,
      f"Freshness=1.0 for never-used skill (actual={report_unused.freshness})")
check(report_unused.reliability == 0.5,
      f"Reliability=0.5 for never-used skill (actual={report_unused.reliability})")
check(report_unused.days_since_last_use == -1,
      "days_since_last_use=-1 for never-used skill")

# ===========================================================================
# Test 7: evaluate_all() returns all active skills, skips whitelist
# ===========================================================================
print("\n[Test 7] evaluate_all() returns all active, skips whitelist")
all_reports = restrainer.evaluate_all()
# 活跃技能: skill_healthy, skill_stale, skill_unused, skill_half_reliable,
#            skill_to_archive, skill_complex, skill_simple (7个)
# 白名单: memory_management_sop (跳过)
skill_ids = {r.skill_id for r in all_reports}
check("memory_management_sop" not in skill_ids,
      "Whitelist skill NOT included in evaluate_all()")
check("skill_healthy" in skill_ids, "skill_healthy included")
check("skill_stale" in skill_ids, "skill_stale included")
check("skill_unused" in skill_ids, "skill_unused included")
check(len(all_reports) >= 7,
      f"All active non-whitelist skills reported ({len(all_reports)})")

# ===========================================================================
# Test 8: evaluate_all() sorted by health ascending
# ===========================================================================
print("\n[Test 8] evaluate_all() sorted by health ascending")
all_reports = restrainer.evaluate_all()
health_scores = [r.health_score for r in all_reports]
check(health_scores == sorted(health_scores),
      "Reports sorted by health_score ascending (lowest first)")

# 最不健康的应该是 skill_stale 或 skill_to_archive（90天未用 + 低成功率）
lowest = all_reports[0]
check(lowest.recommendation in ("archive", "warn"),
      f"Lowest health skill has recommendation '{lowest.recommendation}'")

# ===========================================================================
# Test 9: archive() changes status to archived
# ===========================================================================
print("\n[Test 9] archive() changes status to archived")
result = restrainer.archive("skill_to_archive")
check(result is True, "archive() returns True for active skill")

meta_after = registry.get("skill_to_archive")
check(meta_after is not None, "Skill still exists in registry")
check(meta_after.status == STATUS_ARCHIVED,
      f"Status changed to archived (actual={meta_after.status})")

# ===========================================================================
# Test 10: archive() removes from get_active_skills()
# ===========================================================================
print("\n[Test 10] archive() removes from get_active_skills()")
active_after = registry.get_active_skills()
active_names = {s.name for s in active_after}
check("skill_to_archive" not in active_names,
      "Archived skill NOT in get_active_skills()")

# 确认在归档列表中
archived_after = registry.get_archived_skills()
archived_names = {s.name for s in archived_after}
check("skill_to_archive" in archived_names,
      "Archived skill IS in get_archived_skills()")

# ===========================================================================
# Test 11: restore() brings skill back to active
# ===========================================================================
print("\n[Test 11] restore() brings skill back to active")
result = restrainer.restore("skill_to_archive")
check(result is True, "restore() returns True for archived skill")

meta_restored = registry.get("skill_to_archive")
check(meta_restored.status == STATUS_ACTIVE,
      f"Status restored to active (actual={meta_restored.status})")

# 再次 restore 应返回 False（已是 active）
result2 = restrainer.restore("skill_to_archive")
check(result2 is False, "restore() returns False for already-active skill")

# ===========================================================================
# Test 12: get_archived_skills() returns correct list
# ===========================================================================
print("\n[Test 12] get_archived_skills() returns correct list")
# 先归档一个技能用于测试
restrainer.archive("skill_to_archive")

archived_list = restrainer.get_archived_skills()
check(isinstance(archived_list, list), "get_archived_skills() returns list")
check(len(archived_list) >= 1,
      f"At least 1 archived skill (got {len(archived_list)})")

# 检查列表项结构
if len(archived_list) > 0:
    item = archived_list[0]
    check("skill_id" in item, "Archived item has 'skill_id'")
    check("health_score" in item, "Archived item has 'health_score'")
    check("reason" in item, "Archived item has 'reason'")
    check("status" in item, "Archived item has 'status'")
    check(item["status"] == STATUS_ARCHIVED, "Status is 'archived'")

# 恢复以便后续测试
restrainer.restore("skill_to_archive")

# ===========================================================================
# Test 13: Whitelist evaluate() returns health 1.0
# ===========================================================================
print("\n[Test 13] Whitelist evaluate() returns health 1.0")
report_wl = restrainer.evaluate("memory_management_sop")
check(report_wl.health_score == 1.0,
      f"Whitelist health_score=1.0 (actual={report_wl.health_score})")
check(report_wl.freshness == 1.0, "Whitelist freshness=1.0")
check(report_wl.reliability == 1.0, "Whitelist reliability=1.0")
check(report_wl.recommendation == "keep", "Whitelist recommendation='keep'")
check("Whitelisted" in report_wl.reason, "Reason mentions whitelist")

# ===========================================================================
# Test 14: Whitelist archive() returns False (refused)
# ===========================================================================
print("\n[Test 14] Whitelist archive() returns False")
result_wl = restrainer.archive("memory_management_sop")
check(result_wl is False, "Archive whitelist skill returns False")

# 确认状态未变
meta_wl_check = registry.get("memory_management_sop")
check(meta_wl_check.status == STATUS_ACTIVE,
      "Whitelist skill remains active after archive attempt")

# ===========================================================================
# Test 15: dry_run=True doesn't actually archive
# ===========================================================================
print("\n[Test 15] dry_run=True doesn't actually archive")
dry_config = MetalRestrainerConfig(dry_run=True)
dry_restrainer = MetalRestrainer(registry, config=dry_config)

meta_before_dry = registry.get("skill_to_archive")
check(meta_before_dry.status == STATUS_ACTIVE,
      "skill_to_archive is active before dry_run")

result_dry = dry_restrainer.archive("skill_to_archive")
check(result_dry is True, "dry_run archive() returns True")

meta_after_dry = registry.get("skill_to_archive")
check(meta_after_dry.status == STATUS_ACTIVE,
      "skill_to_archive STILL active after dry_run (not actually archived)")

# ===========================================================================
# Test 16: Disabled config → evaluate_all() returns empty
# ===========================================================================
print("\n[Test 16] Disabled config → evaluate_all() returns empty")
disabled_config = MetalRestrainerConfig(enabled=False)
disabled_restrainer = MetalRestrainer(registry, config=disabled_config)

reports_disabled = disabled_restrainer.evaluate_all()
check(reports_disabled == [],
      f"evaluate_all() returns empty list when disabled (got {len(reports_disabled)})")

# 但单个 evaluate 仍可用
report_disabled = disabled_restrainer.evaluate("skill_healthy")
check(isinstance(report_disabled, HealthReport),
      "evaluate() still works when disabled")
check(report_disabled.health_score > 0,
      "evaluate() returns valid health score when disabled")

# ===========================================================================
# 附加测试：非存在技能的处理
# ===========================================================================
print("\n[Test 17] Non-existent skill handling")
report_nonexist = restrainer.evaluate("nonexistent_skill")
check(report_nonexist.health_score == 0.0,
      "Non-existent skill has health_score=0.0")
check(report_nonexist.recommendation == "not_found",
      "Non-existent skill recommendation='not_found'")

result_nonexist = restrainer.archive("nonexistent_skill")
check(result_nonexist is False, "archive() non-existent skill returns False")

result_nonexist_restore = restrainer.restore("nonexistent_skill")
check(result_nonexist_restore is False,
      "restore() non-existent skill returns False")

# ===========================================================================
# Summary
# ===========================================================================
print("\n" + "=" * 60)
print(f"Results: {passed} passed, {failed} failed, {passed + failed} total")
if failed == 0:
    print("ALL TESTS PASSED")
else:
    print(f"SOME TESTS FAILED ({failed} failures)")
print("=" * 60)

sys.exit(0 if failed == 0 else 1)
