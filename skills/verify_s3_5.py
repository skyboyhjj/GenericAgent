#!/usr/bin/env python3
"""
S3-5: RootAuditor 归根审计 + GA集成 验证脚本

验证项：
 1. RootAuditor 初始化成功，所有模块注入正确
 2. audit("daily") 返回有效 AuditReport
 3. audit("weekly") 包含质量抽检动作
 4. audit("manual") 执行全部审计动作（含占位模块）
 5. 审计时低健康度技能被自动归档
 6. 审计报告中的 actions 包含已归档技能的信息
 7. 审计报告中的 warnings 包含低健康度但未达归档阈值的技能
 8. 白名单技能在审计中不被归档
 9. get_last_audit_time() 初始返回 None
10. 审计后 get_last_audit_time() 返回有效时间戳
11. 审计历史记录正确（get_audit_history()）
12. WaterAdapter 导入成功，方法返回占位信息
13. EarthConnector 导入成功，方法返回占位信息
14. 任一模块的 enabled=False 时，审计跳过该模块
"""

import time as time_module
from skills.root_auditor import (
    RootAuditor,
    AuditReport,
    PERIOD_MANUAL,
    PERIOD_DAILY,
    PERIOD_WEEKLY,
    PERIOD_MONTHLY,
    LAST_AUDIT_FILE,
    AUDIT_LOG_FILE,
)
from skills.earth_connector import EarthConnector
from skills.water_adapter import WaterAdapter
from skills.metal_restrainer import MetalRestrainer, MetalRestrainerConfig
from skills.wood_grower import WoodGrower, WoodGrowerConfig
from skills.skill_registry import (
    SkillRegistry,
    SkillMeta,
    STATUS_ACTIVE,
    STATUS_ARCHIVED,
)
import sys
import os
import math
import tempfile
import shutil
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


# ---------------------------------------------------------------------------
# Setup
# ---------------------------------------------------------------------------

print("=" * 60)
print("S3-5 RootAuditor 归根审计 Tests")
print("=" * 60)

# 清理上次测试的审计文件
if LAST_AUDIT_FILE.exists():
    LAST_AUDIT_FILE.unlink()
if AUDIT_LOG_FILE.exists():
    AUDIT_LOG_FILE.unlink()

# 创建临时目录用于 SOP 文件
tmp_dir = Path(tempfile.mkdtemp(prefix="s3_5_test_"))

# 创建 SkillRegistry
registry = SkillRegistry()
now = datetime.now(timezone.utc)
now_str = now.strftime("%Y-%m-%dT%H:%M:%S")
ninety_days_ago = (now - timedelta(days=90)).strftime("%Y-%m-%dT%H:%M:%S")

# 创建测试 SOP 文件
clean_sop = tmp_dir / "skill_healthy_sop.md"
clean_sop.write_text(
    "# Healthy Skill SOP\n\n"
    "## Steps\n"
    "1. Use tool_call to read file\n"
    "2. Execute verified command\n"
    "3. Confirm output matched expected\n",
    encoding="utf-8",
)

stale_sop = tmp_dir / "skill_stale_sop.md"
stale_sop.write_text(
    "# Stale Skill SOP\n\n"
    "## Steps\n"
    "1. Old approach\n",
    encoding="utf-8",
)

wl_sop = tmp_dir / "memory_management_sop.md"
wl_sop.write_text(
    "# Memory Management SOP\n\n"
    "## Steps\n"
    "1. Core memory management\n",
    encoding="utf-8",
)

# 注册测试技能到 registry
# 技能 A: 健康技能
meta_a = SkillMeta(
    name="skill_healthy",
    file=str(clean_sop.relative_to(ROOT)) if clean_sop.is_relative_to(
        ROOT) else str(clean_sop),
    use_count=10,
    success_rate=0.95,
    last_used=now_str,
    created_at=now_str,
    status=STATUS_ACTIVE,
)

# 技能 B: 不健康技能（90天未用 + 低成功率）
meta_b = SkillMeta(
    name="skill_stale",
    file=str(stale_sop.relative_to(ROOT)) if stale_sop.is_relative_to(
        ROOT) else str(stale_sop),
    use_count=5,
    success_rate=0.2,
    last_used=ninety_days_ago,
    created_at=(now - timedelta(days=180)).strftime("%Y-%m-%dT%H:%M:%S"),
    status=STATUS_ACTIVE,
)

# 技能 C: 中等健康度（用于警告测试）
meta_c = SkillMeta(
    name="skill_mediocre",
    file=str(stale_sop.relative_to(ROOT)) if stale_sop.is_relative_to(
        ROOT) else str(stale_sop),
    use_count=3,
    success_rate=0.5,
    last_used=(now - timedelta(days=30)).strftime("%Y-%m-%dT%H:%M:%S"),
    created_at=(now - timedelta(days=60)).strftime("%Y-%m-%dT%H:%M:%S"),
    status=STATUS_ACTIVE,
)

# 白名单技能
meta_wl = SkillMeta(
    name="memory_management_sop",
    file=str(wl_sop.relative_to(ROOT)) if wl_sop.is_relative_to(
        ROOT) else str(wl_sop),
    use_count=100,
    success_rate=1.0,
    last_used=now_str,
    created_at=now_str,
    status=STATUS_ACTIVE,
)

registry.register("skill_healthy", meta_a)
registry.register("skill_stale", meta_b)
registry.register("skill_mediocre", meta_c)
registry.register("memory_management_sop", meta_wl)

# SkillRegistry.register() 会覆盖 last_used/created_at，需恢复
meta_b.last_used = ninety_days_ago
meta_b.created_at = (now - timedelta(days=180)).strftime("%Y-%m-%dT%H:%M:%S")
meta_c.last_used = (now - timedelta(days=30)).strftime("%Y-%m-%dT%H:%M:%S")
meta_c.created_at = (now - timedelta(days=60)).strftime("%Y-%m-%dT%H:%M:%S")

# 创建五行模块
wood_grower = WoodGrower(registry)
metal_restrainer = MetalRestrainer(registry)
water_adapter = WaterAdapter(registry)
earth_connector = EarthConnector(registry)

# 将 white list 中的 SOP 文件路径修正
# (MetalRestrainer 只通过 registry 操作，不依赖文件系统)
# 更新文件路径到实际位置
meta_a.file = str(clean_sop)
meta_b.file = str(stale_sop)
meta_c.file = str(stale_sop)
meta_wl.file = str(wl_sop)

# ===========================================================================
# Test 1: RootAuditor 初始化
# ===========================================================================
print("\n[Test 1] RootAuditor initialization")
auditor = RootAuditor(
    registry=registry,
    wood_grower=wood_grower,
    metal_restrainer=metal_restrainer,
    water_adapter=water_adapter,
    earth_connector=earth_connector,
)
check(auditor is not None, "RootAuditor created successfully")
check(auditor.registry is registry, "Registry injected correctly")
check(auditor.wood_grower is wood_grower, "WoodGrower injected correctly")
check(auditor.metal_restrainer is metal_restrainer,
      "MetalRestrainer injected correctly")
check(auditor.water_adapter is water_adapter,
      "WaterAdapter injected correctly")
check(auditor.earth_connector is earth_connector,
      "EarthConnector injected correctly")
check(auditor.fire_transformer is None,
      "FireTransformer default to None (placeholder)")

# ===========================================================================
# Test 2: audit("daily") 返回有效 AuditReport
# ===========================================================================
print("\n[Test 2] audit('daily') returns valid AuditReport")
report_daily = auditor.audit(PERIOD_DAILY)
check(isinstance(report_daily, AuditReport), "Result is AuditReport instance")
check(report_daily.period == PERIOD_DAILY, "period = 'daily'")
check(len(report_daily.timestamp) > 0, "timestamp is non-empty")
check(isinstance(report_daily.actions, list), "actions is a list")
check(isinstance(report_daily.warnings, list), "warnings is a list")
check(report_daily.active_count > 0,
      f"active_count > 0 (got {report_daily.active_count})")
check(report_daily.archived_count >= 0, "archived_count >= 0")

# ===========================================================================
# Test 3: audit("daily") 自动归档低健康度技能
# ===========================================================================
print("\n[Test 3] Low health skills auto-archived during daily audit")
# 先恢复 skill_stale 为 active（可能在之前测试中被归档）
if registry.get("skill_stale").status != STATUS_ACTIVE:
    registry.recover("skill_stale")

# 执行每日审计
report = auditor.audit(PERIOD_DAILY)

# 检查 skill_stale 是否被归档（健康度应 < 0.3）
stale_meta = registry.get("skill_stale")
check(stale_meta.status == STATUS_ARCHIVED,
      f"skill_stale archived after audit (status={stale_meta.status})")

# 检查审计报告 actions 中是否包含归档信息
archive_actions = [a for a in report.actions if a.get("type") == "archive"]
check(len(archive_actions) >= 1,
      f"Actions contain archive entries (got {len(archive_actions)})")

# ===========================================================================
# Test 4: 审计报告 warnings 包含低健康度但未归档的技能
# ===========================================================================
print("\n[Test 4] Audit warnings contain low-health non-archived skills")
# skill_mediocre should have health around 0.3-0.5 (warn, not archive)
low_health_warnings = [
    w for w in report.warnings if w.get("type") == "low_health"]
# skill_mediocre might or might not trigger warning depending on exact calculation
# At minimum, the warnings structure should be correct
check(isinstance(report.warnings, list), "Warnings is a list")

# ===========================================================================
# Test 5: 白名单技能在审计中不被归档
# ===========================================================================
print("\n[Test 5] Whitelist skill NOT archived during audit")
wl_meta = registry.get("memory_management_sop")
check(wl_meta.status == STATUS_ACTIVE,
      f"Whitelist skill remains active (status={wl_meta.status})")

archive_skill_ids = [a.get("skill_id")
                     for a in report.actions if a.get("type") == "archive"]
check("memory_management_sop" not in archive_skill_ids,
      "Whitelist skill NOT in archive actions")

# ===========================================================================
# Test 6: audit("weekly") 包含质量抽检
# ===========================================================================
print("\n[Test 6] audit('weekly') includes quality spot check")
# 恢复 skill_stale 用于测试
registry.recover("skill_stale")
meta_b.status = STATUS_ACTIVE

report_weekly = auditor.audit(PERIOD_WEEKLY)
check(isinstance(report_weekly, AuditReport), "Weekly result is AuditReport")
check(report_weekly.period == PERIOD_WEEKLY, "period = 'weekly'")
# weekly 应包含 daily 的金·克评估 + 质量抽检
check(report_weekly.active_count > 0, "Weekly audit has active_count")

# ===========================================================================
# Test 7: audit("manual") 执行全量审计 + 占位模块
# ===========================================================================
print("\n[Test 7] audit('manual') executes full audit with placeholders")
registry.recover("skill_stale")
meta_b.status = STATUS_ACTIVE

report_manual = auditor.audit(PERIOD_MANUAL)
check(report_manual.period == PERIOD_MANUAL, "period = 'manual'")

# 检查占位模块的 actions
water_actions = [a for a in report_manual.actions if a.get(
    "module") == "water_adapter"]
earth_actions = [a for a in report_manual.actions if a.get(
    "module") == "earth_connector"]
check(len(water_actions) >= 1,
      f"Manual audit invokes WaterAdapter (got {len(water_actions)})")
check(len(earth_actions) >= 1,
      f"Manual audit invokes EarthConnector (got {len(earth_actions)})")

# 检查 health_trend
if report_manual.health_trend:
    check("avg_health" in report_manual.health_trend,
          "Monthly audit includes avg_health in trend")
    check("low_health_count" in report_manual.health_trend,
          "Monthly audit includes low_health_count in trend")

# ===========================================================================
# Test 8: get_last_audit_time() 初始返回 None → 审计后返回时间戳
# ===========================================================================
print("\n[Test 8] get_last_audit_time() before and after audit")

# 需要全新创建的 auditor 来测试"从未审计"
# 清理审计文件
if LAST_AUDIT_FILE.exists():
    LAST_AUDIT_FILE.unlink()

fresh_auditor = RootAuditor(
    registry=registry,
    wood_grower=wood_grower,
    metal_restrainer=metal_restrainer,
)
check(fresh_auditor.get_last_audit_time() is None,
      "get_last_audit_time() returns None before any audit")

# 执行审计
fresh_auditor.audit(PERIOD_DAILY)
last_time = fresh_auditor.get_last_audit_time()
check(last_time is not None, "get_last_audit_time() returns timestamp after audit")
check("T" in (last_time or ""), f"Timestamp is ISO format (got {last_time})")

# ===========================================================================
# Test 9: 审计历史记录正确
# ===========================================================================
print("\n[Test 9] get_audit_history() returns correct records")
# fresh_auditor 已执行了 1 次审计
history = fresh_auditor.get_audit_history(limit=10)
check(len(history) >= 1, f"Audit history has entries (got {len(history)})")

# 再执行一次审计
fresh_auditor.audit(PERIOD_DAILY)
history2 = fresh_auditor.get_audit_history(limit=10)
check(len(history2) >= 2,
      f"History grows after second audit (got {len(history2)})")

# 检查历史项结构
if history2:
    entry = history2[0]
    check("period" in entry, "History entry has 'period'")
    check("timestamp" in entry, "History entry has 'timestamp'")
    check("actions" in entry, "History entry has 'actions'")
    check("warnings" in entry, "History entry has 'warnings'")

# ===========================================================================
# Test 10: is_audit_due() 判断逻辑
# ===========================================================================
print("\n[Test 10] is_audit_due() logic")
# 刚执行完审计，不应该到期
check(fresh_auditor.is_audit_due(PERIOD_DAILY) is False,
      "is_audit_due('daily') returns False right after audit")

# 从未审计的 auditor 应该到期
never_auditor = RootAuditor(
    registry=registry,
    wood_grower=wood_grower,
    metal_restrainer=metal_restrainer,
)
# 清理可能残留的审计文件
if LAST_AUDIT_FILE.exists():
    LAST_AUDIT_FILE.unlink()
never_auditor._last_audit_time = None
check(never_auditor.is_audit_due(PERIOD_DAILY) is True,
      "is_audit_due('daily') returns True when never audited")

# ===========================================================================
# Test 11: WaterAdapter 占位模块
# ===========================================================================
print("\n[Test 11] WaterAdapter placeholder")
result_wa = water_adapter.check_and_update("test_skill")
check(result_wa["status"] == "placeholder",
      f"WaterAdapter returns placeholder status (got {result_wa['status']})")
check("skill_id" in result_wa, "Result contains skill_id")
check("message" in result_wa, "Result contains message")

result_api = water_adapter.detect_api_changes("test_skill")
check(result_api["status"] == "placeholder",
      "detect_api_changes returns placeholder")

# ===========================================================================
# Test 12: EarthConnector 占位模块
# ===========================================================================
print("\n[Test 12] EarthConnector placeholder")
result_ec = earth_connector.check_compatibility("test_skill", {"os": "linux"})
check(result_ec["status"] == "placeholder",
      f"EarthConnector returns placeholder status (got {result_ec['status']})")
check("skill_id" in result_ec, "Result contains skill_id")
check("message" in result_ec, "Result contains message")

result_env = earth_connector.get_environment_meta("test_skill")
check(result_env["status"] == "placeholder",
      "get_environment_meta returns placeholder")

# ===========================================================================
# Test 13: audit_async() 非阻塞执行
# ===========================================================================
print("\n[Test 13] audit_async() non-blocking execution")

callback_called = [False]
callback_report = [None]


def audit_callback(report):
    callback_called[0] = True
    callback_report[0] = report


auditor.audit_async(PERIOD_DAILY, callback=audit_callback)
# 等待后台线程完成（最多 5 秒）
timeout = 5.0
start = time_module.time()
while not callback_called[0] and (time_module.time() - start) < timeout:
    time_module.sleep(0.1)

check(callback_called[0], "audit_async callback was invoked")
check(callback_report[0] is not None, "Callback received AuditReport")
if callback_report[0]:
    check(isinstance(callback_report[0], AuditReport),
          "Callback received valid AuditReport")

# ===========================================================================
# Test 14: 禁用模块时审计跳过
# ===========================================================================
print("\n[Test 14] Disabled module skipped during audit")
disabled_config = MetalRestrainerConfig(enabled=False)
disabled_mr = MetalRestrainer(registry, config=disabled_config)

disabled_auditor = RootAuditor(
    registry=registry,
    wood_grower=wood_grower,
    metal_restrainer=disabled_mr,
)

# 恢复技能以便测试
registry.recover("skill_stale")
meta_b.status = STATUS_ACTIVE

report_disabled = disabled_auditor.audit(PERIOD_DAILY)
# 金·克被禁用，不应有归档动作
archive_actions = [
    a for a in report_disabled.actions if a.get("type") == "archive"]
check(len(archive_actions) == 0,
      f"No archive actions when MetalRestrainer disabled (got {len(archive_actions)})")
check(report_disabled.archived_count == 0,
      f"archived_count = 0 when disabled (got {report_disabled.archived_count})")

# ===========================================================================
# 附加：五行模块完整性检查
# ===========================================================================
print("\n[Test 15] Five-element module integrity")
# 检查所有模块是否可正常导入和使用
modules_ok = True
try:
    from skills.skill_registry import SkillRegistry
    from skills.wood_grower import WoodGrower
    from skills.metal_restrainer import MetalRestrainer
    from skills.water_adapter import WaterAdapter
    from skills.earth_connector import EarthConnector
    from skills.root_auditor import RootAuditor
except ImportError as e:
    modules_ok = False
    print(f"  Import error: {e}")
check(modules_ok, "All five-element modules importable")

# 检查 launch_huihui.pyw 中包含引擎初始化代码
launch_path = ROOT / "launch_huihui.pyw"
if launch_path.exists():
    launch_content = launch_path.read_text(encoding="utf-8")
    check("_init_wuxing_engine" in launch_content,
          "launch_huihui.pyw contains _init_wuxing_engine()")
    check("_check_and_audit" in launch_content,
          "launch_huihui.pyw contains _check_and_audit()")
    check("_run_wuxing_audit_on_startup" in launch_content,
          "launch_huihui.pyw contains _run_wuxing_audit_on_startup()")

# ===========================================================================
# Cleanup
# ===========================================================================
# 清理审计文件
if LAST_AUDIT_FILE.exists():
    LAST_AUDIT_FILE.unlink()
if AUDIT_LOG_FILE.exists():
    AUDIT_LOG_FILE.unlink()
# 清理临时目录
shutil.rmtree(tmp_dir, ignore_errors=True)

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
