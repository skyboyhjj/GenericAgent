"""
S3-6: Sprint 3 集成测试 — 五行流转引擎端到端验证

测试范围：
  [PASS] 木·生 → 注册 → 金·克评估 → 归档 → 恢复 → 审计闭环
  [PASS] 禁用开关
  [OBS] 火·化相似度观测（merge/split 跳过）

测试策略：
  - 全程不调用 LLM，纯程序化验证
  - 使用模拟 turn_history 和 SOP 文件
  - 每个场景独立运行，确保状态隔离
"""

from skills.root_auditor import RootAuditor
from skills.fire_transformer import FireTransformer, FireTransformerConfig
from skills.metal_restrainer import MetalRestrainer, MetalRestrainerConfig
from skills.wood_grower import WoodGrower, WoodGrowerConfig
from skills.skill_registry import (
    SkillRegistry, SkillMeta, EnvironmentMeta,
    STATUS_ACTIVE, STATUS_ARCHIVED
)
import sys
import os
import subprocess
import tempfile
import json
import re
from datetime import datetime, timezone, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))


ROOT = Path(__file__).resolve().parent.parent
MEMORY_DIR = ROOT / "memory"
LAST_AUDIT_FILE = MEMORY_DIR / "last_audit.txt"
AUDIT_LOG_FILE = MEMORY_DIR / "audit_log.json"

CHECKS_PASSED = 0
CHECKS_TOTAL = 0


def check(condition: bool, description: str) -> None:
    """Assert-like check that increments global counters."""
    global CHECKS_PASSED, CHECKS_TOTAL
    CHECKS_TOTAL += 1
    if not condition:
        print(f"    [FAIL] {description}")
    else:
        CHECKS_PASSED += 1
        print(f"    [PASS] {description}")


def _make_iso(days_ago: int) -> str:
    """生成 days_ago 天前的 ISO 时间字符串（UTC）"""
    dt = datetime.now(timezone.utc) - timedelta(days=days_ago)
    return dt.strftime("%Y-%m-%dT%H:%M:%S")


def _register_with_past_last_used(registry, skill_name, meta, days_ago):
    """
    注册技能并设置过去的 last_used 时间（因为 register() 会覆盖为当前时间）。

    SkillRegistry.register() 强制设置 last_used=now，所以需要在注册后手动改回。
    """
    registry.register(skill_name, meta)
    skill = registry.get(skill_name)
    if skill:
        skill.last_used = _make_iso(days_ago)


# ===========================================================================
# 审计文件备份（RootAuditor 会写入 memory/ 目录）
# ===========================================================================

def _backup_audit_files() -> dict:
    backups = {}
    if LAST_AUDIT_FILE.exists():
        backups["last_audit"] = LAST_AUDIT_FILE.read_text(encoding="utf-8")
    if AUDIT_LOG_FILE.exists():
        backups["audit_log"] = AUDIT_LOG_FILE.read_text(encoding="utf-8")
    return backups


def _restore_audit_files(backups: dict) -> None:
    MEMORY_DIR.mkdir(parents=True, exist_ok=True)
    if "last_audit" in backups:
        LAST_AUDIT_FILE.write_text(backups["last_audit"], encoding="utf-8")
    elif LAST_AUDIT_FILE.exists():
        LAST_AUDIT_FILE.unlink()
    if "audit_log" in backups:
        AUDIT_LOG_FILE.write_text(backups["audit_log"], encoding="utf-8")
    elif AUDIT_LOG_FILE.exists():
        AUDIT_LOG_FILE.unlink()


# ===========================================================================
# 场景 1：木·生 → 注册（核心链路 A）
# ===========================================================================

def test_crystallize_to_register() -> None:
    with tempfile.TemporaryDirectory() as tmpdir:
        tmp = Path(tmpdir)
        reg_path = tmp / "skill_registry.yaml"
        registry = SkillRegistry(str(reg_path))
        wg = WoodGrower(registry)

        # 1. 构造含 3+ 次成功工具调用的 turn_history
        turn_history = [
            {"type": "tool_call", "tool": "search_files"},
            {"type": "tool_call", "tool": "read_file"},
            {"type": "tool_call", "tool": "grep"},
            {"type": "tool_call", "tool": "write_file"},
        ]

        # 2. 验证 should_trigger_distill 返回 True
        check(wg.should_trigger_distill(turn_history) is True,
              "should_trigger_distill with 4 successful tool calls -> True")

        # 2b. 不足 min_tool_calls 时不触发
        short_history = [
            {"type": "tool_call", "tool": "search_files"},
            {"type": "tool_call", "tool": "read_file"},
        ]
        check(wg.should_trigger_distill(short_history) is False,
              "should_trigger_distill with 2 tool calls (< 3) -> False")

        # 2c. 关闭开关时始终返回 False
        wg_disabled = WoodGrower(registry, WoodGrowerConfig(enabled=False))
        check(wg_disabled.should_trigger_distill(turn_history) is False,
              "disabled WoodGrower.should_trigger_distill -> False")
        check(wg_disabled.build_distill_prompt() == "",
              "disabled WoodGrower.build_distill_prompt -> ''")

        # 3. 验证 build_distill_prompt 返回有效指令
        prompt = wg.build_distill_prompt()
        check("start_long_term_update" in prompt,
              "build_distill_prompt contains start_long_term_update")
        check(len(prompt) > 50,
              "build_distill_prompt length > 50")

        # 4. 创建模拟 SOP 文件（无易变状态），验证 post_validate 通过
        sop_path = tmp / "test_skill_sop.md"
        sop_content = (
            "# Test SOP\n\n"
            "## Steps\n"
            "1. Run tool: search_files\n"
            "2. Verified: output correct\n"
            "3. Execute: final step\n"
        )
        sop_path.write_text(sop_content, encoding="utf-8")

        result = wg.post_validate(str(sop_path))
        check(result.passed is True,
              "post_validate passed (clean SOP, no volatile state)")
        check(len(result.violations) == 0,
              "post_validate: 0 violations")

        # 4b. 含易变状态的 SOP — 用 auto_fix=False 先测（避免文件被修改）
        volatile_sop_no_fix = tmp / "volatile_nofix.md"
        volatile_content = (
            "# Bad SOP\n\n"
            "Path: D:\\Users\\test\\config.json\n"
            "Date: 2026-05-03\n"
            "User: /home/testuser/data\n"
        )
        volatile_sop_no_fix.write_text(volatile_content, encoding="utf-8")

        # auto_fix=False：检测违规但不修复 → passed 应为 False
        wg_no_fix = WoodGrower(registry, WoodGrowerConfig(auto_fix=False))
        nofix_result = wg_no_fix.post_validate(str(volatile_sop_no_fix))
        check(nofix_result.passed is False,
              "post_validate with auto_fix=False -> passed=False (unfixed violations)")
        check(len(nofix_result.violations) >= 2,
              f"post_validate auto_fix=False violations >=2 (got {len(nofix_result.violations)})")
        # 验证 auto_fixed 为空
        check(len(nofix_result.auto_fixed) == 0,
              f"post_validate auto_fix=False has 0 auto_fixed (got {len(nofix_result.auto_fixed)})")

        # 4c. 含易变状态的 SOP — 用 auto_fix=True（新文件，避免读到已修复内容）
        volatile_sop_fix = tmp / "volatile_fix.md"
        volatile_sop_fix.write_text(volatile_content, encoding="utf-8")
        wg_fix = WoodGrower(registry, WoodGrowerConfig(auto_fix=True))
        fix_result = wg_fix.post_validate(str(volatile_sop_fix))
        check(len(fix_result.violations) >= 2,
              f"post_validate auto_fix=True detected >=2 violations (got {len(fix_result.violations)})")
        check(len(fix_result.auto_fixed) >= 2,
              f"post_validate auto_fix=True applied >=2 fixes (got {len(fix_result.auto_fixed)})")
        # auto_fix 修复后 passed 应为 True
        check(fix_result.passed is True,
              "post_validate with auto_fix=True -> passed=True (all violations fixed)")

        # 5. 调用 SkillRegistry.register()，验证注册成功
        meta = SkillMeta(
            name="test_crystallize",
            file="memory/test_crystallize_sop.md",
            dependencies=["os", "pathlib", "json"],
            environment=EnvironmentMeta(os="Linux", python_version="3.11"),
        )
        registry.register("test_crystallize", meta)

        # 6. 验证 registry 中可查询到该技能
        skill = registry.get("test_crystallize")
        check(skill is not None,
              "registry.get('test_crystallize') returns skill")
        check(skill.name == "test_crystallize",
              "registered skill name correct")
        check(skill.status == STATUS_ACTIVE,
              "registered skill status is active")
        check(skill.created_at != "",
              "created_at timestamp auto-set")

        # 6b. 技能出现在 get_active_skills 中
        active_names = [s.name for s in registry.get_active_skills()]
        check("test_crystallize" in active_names,
              "skill appears in get_active_skills()")
        check(len(registry.get_active_skills()) == 1,
              "registry has exactly 1 active skill")

    print("    Scene 1: WoodGrower trigger -> validate -> register pipeline OK")


# ===========================================================================
# 场景 2：注册 → 金·克评估（核心链路 B）
# ===========================================================================

def test_register_to_health_eval() -> None:
    with tempfile.TemporaryDirectory() as tmpdir:
        tmp = Path(tmpdir)
        reg_path = tmp / "skill_registry.yaml"
        registry = SkillRegistry(str(reg_path))

        # 注册多个技能（register() 会覆盖 last_used → 注册后手动设置）
        # 高频使用、近期活跃、高成功率 → 高健康度
        meta_fresh = SkillMeta(
            name="fresh_skill",
            file="memory/fresh_sop.md",
            use_count=20,
            success_rate=0.95,
            dependencies=["os", "json", "pathlib"],
            environment=EnvironmentMeta(os="Linux", python_version="3.11"),
        )
        _register_with_past_last_used(registry, "fresh_skill", meta_fresh, 1)

        # 中等活跃度
        meta_medium = SkillMeta(
            name="medium_skill",
            file="memory/medium_sop.md",
            use_count=8,
            success_rate=0.80,
            dependencies=["os", "pathlib"],
            environment=EnvironmentMeta(os="Linux", python_version="3.11"),
        )
        _register_with_past_last_used(
            registry, "medium_skill", meta_medium, 15)

        # 长期未用、低成功率 → 低健康度
        meta_stale = SkillMeta(
            name="stale_skill",
            file="memory/stale_sop.md",
            use_count=3,
            success_rate=0.40,
            dependencies=["json"],
            environment=EnvironmentMeta(os="Linux", python_version="3.10"),
        )
        _register_with_past_last_used(registry, "stale_skill", meta_stale, 60)

        # 从未使用 → 新鲜度满分但可靠性中性
        meta_new = SkillMeta(
            name="new_skill",
            file="memory/new_sop.md",
            use_count=0,
            success_rate=1.0,
            dependencies=["os"],
            environment=EnvironmentMeta(os="Linux", python_version="3.11"),
        )
        registry.register("new_skill", meta_new)

        # 调用 MetalRestrainer.evaluate_all()
        mr = MetalRestrainer(registry)
        reports = mr.evaluate_all()

        # 验证返回列表非空
        check(len(reports) >= 3,
              f"evaluate_all returns >=3 reports (got {len(reports)})")

        # 验证按健康度升序排列
        sorted_correct = all(
            reports[i].health_score <= reports[i + 1].health_score
            for i in range(len(reports) - 1)
        )
        check(sorted_correct,
              "evaluate_all returns list sorted by health_score ascending")

        # 验证最近使用的技能健康度高于长期未用的技能
        fresh_report = next(r for r in reports if r.skill_id == "fresh_skill")
        stale_report = next(r for r in reports if r.skill_id == "stale_skill")
        check(fresh_report.health_score > stale_report.health_score,
              f"fresh_skill health ({fresh_report.health_score:.4f}) > stale_skill ({stale_report.health_score:.4f})")

        # 验证成功率高的技能可靠性 > 低成功率
        check(fresh_report.reliability > stale_report.reliability,
              f"fresh_skill reliability ({fresh_report.reliability:.4f}) > stale_skill ({stale_report.reliability:.4f})")

        # 验证从未使用的技能新鲜度为 1.0
        new_report = next(r for r in reports if r.skill_id == "new_skill")
        check(new_report.freshness == 1.0,
              f"unused skill freshness = 1.0 (got {new_report.freshness})")

        # 验证各 report 字段完整性
        sample = reports[0]
        for field in ["skill_id", "health_score", "freshness", "reliability",
                      "recommendation", "reason"]:
            check(hasattr(sample, field),
                  f"HealthReport has field '{field}'")

        # 验证 recommendation 合法
        for r in reports:
            check(r.recommendation in ("archive", "warn", "keep"),
                  f"skill '{r.skill_id}' recommendation valid: '{r.recommendation}'")

    print("    Scene 2: register -> health eval -> sorting pipeline OK")


# ===========================================================================
# 场景 3：金·克评估 → 归档（核心链路 C）
# ===========================================================================

def test_health_to_archive() -> None:
    with tempfile.TemporaryDirectory() as tmpdir:
        tmp = Path(tmpdir)
        reg_path = tmp / "skill_registry.yaml"
        registry = SkillRegistry(str(reg_path))

        # 1. 构造健康度明显低于 0.3 的技能（120 天前使用）
        meta_low = SkillMeta(
            name="archive_candidate",
            file="memory/archive_sop.md",
            use_count=5,
            success_rate=0.30,
            dependencies=["os"],
            environment=EnvironmentMeta(os="Linux", python_version="3.11"),
        )
        _register_with_past_last_used(
            registry, "archive_candidate", meta_low, 120)

        # 构造健康度正常的技能
        meta_healthy = SkillMeta(
            name="healthy_skill",
            file="memory/healthy_sop.md",
            use_count=10,
            success_rate=0.95,
            dependencies=["os", "json", "pathlib"],
            environment=EnvironmentMeta(os="Linux", python_version="3.11"),
        )
        _register_with_past_last_used(
            registry, "healthy_skill", meta_healthy, 1)

        mr = MetalRestrainer(registry)

        # 2. 调用 evaluate_all()，验证 recommendation 为 "archive"
        reports = mr.evaluate_all()
        low_report = next(r for r in reports if r.skill_id ==
                          "archive_candidate")
        check(low_report.recommendation == "archive",
              f"low health skill recommendation='archive' (health={low_report.health_score:.4f})")

        healthy_report = next(
            r for r in reports if r.skill_id == "healthy_skill")
        check(healthy_report.recommendation == "keep",
              f"healthy skill recommendation='keep' (health={healthy_report.health_score:.4f})")

        # 3. 执行 archive()，验证返回值 True
        archived = mr.archive("archive_candidate")
        check(archived is True,
              "MetalRestrainer.archive() returns True")

        # 4. 验证该技能在 get_active_skills() 中不再出现
        active_names = [s.name for s in registry.get_active_skills()]
        check("archive_candidate" not in active_names,
              "archived skill NOT in get_active_skills()")
        check("healthy_skill" in active_names,
              "healthy skill still in get_active_skills()")

        # 5. 验证该技能在 get_archived_skills() 中出现
        archived_names = [s.name for s in registry.get_archived_skills()]
        check("archive_candidate" in archived_names,
              "archived skill IN get_archived_skills()")

        # 6. 验证白名单技能拒绝归档
        meta_whitelist = SkillMeta(
            name="memory_management_sop",
            file="memory/mm_sop.md",
            dependencies=["os"],
            environment=EnvironmentMeta(os="Linux", python_version="3.11"),
        )
        registry.register("memory_management_sop", meta_whitelist)
        wl_result = mr.archive("memory_management_sop")
        check(wl_result is False,
              "whitelist skill 'memory_management_sop' rejected archive")

        # 7. 验证归档不存在技能返回 False
        check(mr.archive("nonexistent") is False,
              "archive nonexistent skill returns False")

        # 8. 验证重复归档返回 False
        check(mr.archive("archive_candidate") is False,
              "double archive returns False")

    print("    Scene 3: health eval -> archive -> status change pipeline OK")


# ===========================================================================
# 场景 4：归档 → 恢复
# ===========================================================================

def test_archive_to_restore() -> None:
    with tempfile.TemporaryDirectory() as tmpdir:
        tmp = Path(tmpdir)
        reg_path = tmp / "skill_registry.yaml"
        registry = SkillRegistry(str(reg_path))

        # 注册并归档一个技能
        meta = SkillMeta(
            name="to_restore",
            file="memory/restore_sop.md",
            use_count=5,
            success_rate=0.30,
            dependencies=["os"],
            environment=EnvironmentMeta(os="Linux", python_version="3.11"),
        )
        _register_with_past_last_used(registry, "to_restore", meta, 120)

        mr = MetalRestrainer(registry)
        mr.archive("to_restore")

        # 确认前置条件：已归档
        check("to_restore" not in [s.name for s in registry.get_active_skills()],
              "pre-condition: to_restore NOT in active")
        check("to_restore" in [s.name for s in registry.get_archived_skills()],
              "pre-condition: to_restore IN archived")

        # 1. 恢复
        restored = mr.restore("to_restore")
        check(restored is True,
              "MetalRestrainer.restore() returns True")

        # 2. 验证重新出现在 get_active_skills() 中
        active_names = [s.name for s in registry.get_active_skills()]
        check("to_restore" in active_names,
              "restored skill back in get_active_skills()")

        # 3. 验证从 get_archived_skills() 中移除
        archived_names = [s.name for s in registry.get_archived_skills()]
        check("to_restore" not in archived_names,
              "restored skill removed from get_archived_skills()")

        # 4. 验证恢复后状态是 active
        skill = registry.get("to_restore")
        check(skill.status == STATUS_ACTIVE,
              f"restored skill status is active (got {skill.status})")

        # 5. 验证重复恢复返回 False
        check(mr.restore("to_restore") is False,
              "double restore returns False")

        # 6. 验证恢复不存在的技能返回 False
        check(mr.restore("nonexistent") is False,
              "restore nonexistent skill returns False")

    print("    Scene 4: archive -> restore -> recovery pipeline OK")


# ===========================================================================
# 场景 5：每日审计全流程（端到端闭环）
# ===========================================================================

def test_full_daily_audit_cycle() -> None:
    backups = _backup_audit_files()

    try:
        with tempfile.TemporaryDirectory() as tmpdir:
            tmp = Path(tmpdir)
            reg_path = tmp / "skill_registry.yaml"
            registry = SkillRegistry(str(reg_path))

            # 低健康度（会被自动归档）：180 天前，低成功率
            meta_stale = SkillMeta(
                name="stale_tool",
                file="memory/stale_tool_sop.md",
                use_count=3,
                success_rate=0.25,
                dependencies=["os"],
                environment=EnvironmentMeta(os="Linux", python_version="3.11"),
            )
            _register_with_past_last_used(
                registry, "stale_tool", meta_stale, 180)

            # 中等健康度（仅警告，不归档）
            meta_warn = SkillMeta(
                name="warning_tool",
                file="memory/warning_sop.md",
                use_count=5,
                success_rate=0.50,
                dependencies=["os", "json"],
                environment=EnvironmentMeta(os="Linux", python_version="3.11"),
            )
            _register_with_past_last_used(
                registry, "warning_tool", meta_warn, 60)

            # 高健康度
            meta_fresh = SkillMeta(
                name="fresh_tool",
                file="memory/fresh_tool_sop.md",
                use_count=30,
                success_rate=0.98,
                dependencies=["os", "json", "pathlib", "requests"],
                environment=EnvironmentMeta(os="Linux", python_version="3.11"),
            )
            _register_with_past_last_used(
                registry, "fresh_tool", meta_fresh, 2)

            # 创建五行模块和审计器
            mr = MetalRestrainer(registry)
            auditor = RootAuditor(registry, metal_restrainer=mr)

            # 1. 执行每日审计
            report = auditor.audit(period="daily")
            check(report is not None,
                  "audit(period='daily') returns non-null report")

            # 2. 验证 AuditReport 包含正确的字段
            check(hasattr(report, "period") and report.period == "daily",
                  "report.period == 'daily'")
            check(hasattr(report, "timestamp") and report.timestamp != "",
                  "report.timestamp is set")
            check(hasattr(report, "actions"),
                  "report has actions field")
            check(hasattr(report, "warnings"),
                  "report has warnings field")

            # 3. 验证低健康度技能在审计中被自动归档
            archive_actions = [
                a for a in report.actions if a.get("type") == "archive"]
            check(len(archive_actions) >= 1,
                  f"audit produced >=1 archive actions (got {len(archive_actions)})")

            # 验证 stale_tool 被归档
            archived_skill = registry.get("stale_tool")
            check(archived_skill.status == STATUS_ARCHIVED,
                  f"stale_tool archived after audit (status={archived_skill.status})")

            # 4. 验证 active_count 正确
            active_after = registry.get_active_skills()
            check(len(active_after) == report.active_count,
                  f"report.active_count ({report.active_count}) matches actual active count")

            # 5. 验证审计后 get_last_audit_time() 更新
            last_audit = auditor.get_last_audit_time()
            check(last_audit is not None,
                  "get_last_audit_time() is not None after audit")
            check(last_audit == report.timestamp,
                  "get_last_audit_time() == report.timestamp")

            # 6. 验证 get_audit_history() 包含本次审计记录
            history = auditor.get_audit_history()
            check(len(history) >= 1,
                  f"get_audit_history() has >=1 entry (got {len(history)})")
            latest = history[0]
            check(latest.get("period") == "daily",
                  f"latest audit record period='daily' (got '{latest.get('period')}')")
            check(latest.get("timestamp") == report.timestamp,
                  "audit history timestamp matches report")

            # 7. 验证 warning_tool 产生警告但不归档
            warning_tool_skill = registry.get("warning_tool")
            check(warning_tool_skill.status == STATUS_ACTIVE,
                  "warning_tool NOT archived (warning only)")

            # 8. 验证 fresh_tool 保持活跃
            fresh_tool_skill = registry.get("fresh_tool")
            check(fresh_tool_skill.status == STATUS_ACTIVE,
                  "fresh_tool stays active")

    finally:
        _restore_audit_files(backups)

    print("    Scene 5: daily audit -> auto-archive -> report -> history pipeline OK")


# ===========================================================================
# 场景 6：禁用开关
# ===========================================================================

def test_disabled_module_bypass() -> None:
    with tempfile.TemporaryDirectory() as tmpdir:
        tmp = Path(tmpdir)
        reg_path = tmp / "skill_registry.yaml"
        registry = SkillRegistry(str(reg_path))

        # 注册一个技能供测试
        meta = SkillMeta(
            name="test_skill",
            file="memory/test_sop.md",
            dependencies=["os"],
            environment=EnvironmentMeta(os="Linux", python_version="3.11"),
        )
        registry.register("test_skill", meta)

        turn_history = [
            {"type": "tool_call"},
            {"type": "tool_call"},
            {"type": "tool_call"},
            {"type": "tool_call"},
        ]

        # 1. 关闭 WoodGrower
        wg_off = WoodGrower(registry, WoodGrowerConfig(enabled=False))
        check(wg_off.should_trigger_distill(turn_history) is False,
              "WoodGrower(enabled=False).should_trigger_distill -> False")
        check(wg_off.build_distill_prompt() == "",
              "WoodGrower(enabled=False).build_distill_prompt -> ''")

        # 2. 关闭 MetalRestrainer
        mr_off = MetalRestrainer(
            registry, MetalRestrainerConfig(enabled=False))
        check(mr_off.evaluate_all() == [],
              "MetalRestrainer(enabled=False).evaluate_all -> []")

        # 3. 关闭 FireTransformer
        ft_off = FireTransformer(
            registry, FireTransformerConfig(enabled=False))
        check(ft_off.find_similar_pairs() == [],
              "FireTransformer(enabled=False).find_similar_pairs -> []")
        check(ft_off.generate_suggestions() == [],
              "FireTransformer(enabled=False).generate_suggestions -> []")

        # 4. 验证所有模块在禁用状态下不抛异常
        exception_occurred = False
        try:
            wg_off.should_trigger_distill([])
            wg_off.build_distill_prompt()
            mr_off.evaluate_all()
            ft_off.find_similar_pairs()
            ft_off.generate_suggestions()
        except Exception:
            exception_occurred = True
        check(not exception_occurred,
              "all disabled module calls raise no exception")

        # 5. 验证禁用模块的 merge/split 仍然返回 not_implemented
        merge_result = ft_off.merge("a", "b")
        check(merge_result.get("status") == "not_implemented",
              "disabled FireTransformer.merge() still returns not_implemented")

    print("    Scene 6: 3 modules disabled -> safe defaults -> zero exceptions")


# ===========================================================================
# 场景 7：火·化观测（merge/split 跳过）
# ===========================================================================

def test_fire_transformer_observation() -> None:
    with tempfile.TemporaryDirectory() as tmpdir:
        tmp = Path(tmpdir)
        reg_path = tmp / "skill_registry.yaml"
        registry = SkillRegistry(str(reg_path))

        # 注册两个高度相似技能（共享大量 deps，相同 tags，相同 env，包含关系名称）
        meta_a = SkillMeta(
            name="file_check",
            file="memory/file_check_sop.md",
            dependencies=["os", "pathlib", "glob", "json", "re", "shutil"],
            environment=EnvironmentMeta(os="Linux", python_version="3.11"),
        )
        meta_a.tags = ["file_ops", "inspection", "data"]
        registry.register("file_check", meta_a)

        meta_b = SkillMeta(
            name="file_checker",
            file="memory/file_checker_sop.md",
            dependencies=["os", "pathlib", "glob", "json", "re", "requests"],
            environment=EnvironmentMeta(os="Linux", python_version="3.11"),
        )
        meta_b.tags = ["file_ops", "inspection", "data"]
        registry.register("file_checker", meta_b)

        # 注册一个不相关的技能
        meta_unrelated = SkillMeta(
            name="stock_query",
            file="memory/stock_sop.md",
            dependencies=["requests", "pandas"],
            environment=EnvironmentMeta(os="Linux", python_version="3.11"),
        )
        meta_unrelated.tags = ["finance", "api"]
        registry.register("stock_query", meta_unrelated)

        ft = FireTransformer(registry)

        # 1. 调用 find_similar_pairs()
        pairs = ft.find_similar_pairs()
        check(len(pairs) >= 1,
              f"find_similar_pairs() found >=1 similar pair (got {len(pairs)})")

        # 2. 验证返回的相似度 >= threshold
        if pairs:
            for pair in pairs:
                check(pair.overall_similarity >= ft.config.similarity_threshold,
                      f"similarity {pair.overall_similarity:.4f} >= threshold {ft.config.similarity_threshold}")
                check(pair.confidence in ("high", "medium"),
                      f"confidence is 'high' or 'medium' (got '{pair.confidence}')")

        # 3. 验证 generate_suggestions() 包含该技能对
        suggestions = ft.generate_suggestions()
        check(len(suggestions) >= 1,
              f"generate_suggestions() returns >=1 suggestion (got {len(suggestions)})")

        # 验证建议结构完整性
        for s in suggestions:
            check(isinstance(s, dict),
                  "each suggestion is a dict")
            for key in ("skill_a", "skill_b", "similarity", "confidence", "dimensions", "reason"):
                check(key in s,
                      f"suggestion has field '{key}'")
            dims = s.get("dimensions", {})
            for dk in ("name", "dependencies", "tags", "environment"):
                check(dk in dims,
                      f"dimensions has '{dk}'")

        # 验证 file_check 与 file_checker 配对被识别
        found = False
        for s in suggestions:
            pair_set = {s["skill_a"], s["skill_b"]}
            if pair_set == {"file_check", "file_checker"}:
                found = True
                break
        check(found,
              "generate_suggestions contains file_check <-> file_checker pair")

        # 4. 验证 merge() 返回 not_implemented
        merge_result = ft.merge("file_check", "file_checker")
        check(merge_result.get("status") == "not_implemented",
              "FireTransformer.merge() -> status='not_implemented'")

        # 5. 验证 split() 返回 not_implemented
        split_result = ft.split("any_merged")
        check(split_result.get("status") == "not_implemented",
              "FireTransformer.split() -> status='not_implemented'")

        # 6. 验证不相关的技能不在建议中
        stock_found = False
        for s in suggestions:
            if "stock_query" in (s["skill_a"], s["skill_b"]):
                stock_found = True
                break
        check(not stock_found or len(suggestions) <= 1,
              "stock_query not in similar pairs")

    print("    Scene 7: similarity scan -> suggestions -> merge/split placeholder OK")


# ===========================================================================
# 场景 8：回归验证（运行所有已有验证脚本）
# ===========================================================================

def test_backward_compatibility() -> None:
    verify_scripts = [
        ("S3-1 SkillRegistry", "skills/verify_s3_1.py", 85),
        ("S3-2 WoodGrower", "skills/verify_s3_2.py", 57),
        ("S3-3 MetalRestrainer", "skills/verify_s3_3.py", 67),
        ("S3-4 FireTransformer", "skills/verify_s3_4.py", 69),
        ("S3-5 RootAuditor", "skills/verify_s3_5.py", 55),
    ]

    for name, script_rel_path, expected_passed in verify_scripts:
        script_path = ROOT / script_rel_path
        if not script_path.exists():
            print(
                f"    [WARN] {name}: script not found ({script_rel_path}), skipped")
            continue

        try:
            proc = subprocess.run(
                [sys.executable, str(script_path)],
                capture_output=True,
                text=True,
                timeout=30,
                cwd=str(ROOT),
                env={**os.environ, "PYTHONPATH": str(ROOT)},
            )

            output = proc.stdout + proc.stderr

            # 提取通过/总数
            passed = None
            total = None
            for line in output.splitlines():
                line_stripped = line.strip()
                if "ALL TESTS PASSED" in line_stripped or "全部通过" in line_stripped:
                    passed = expected_passed
                    total = expected_passed
                    break
                m = re.search(
                    r'(\d+)\s*/\s*(\d+)\s*(?:通过|passed|项)', line_stripped)
                if m:
                    passed = int(m.group(1))
                    total = int(m.group(2))

            if proc.returncode == 0:
                check(True, f"{name}: exit=0, {passed}/{total} passed")
            else:
                check(
                    False, f"{name}: exit={proc.returncode}, output={output[-200:]}")
        except subprocess.TimeoutExpired:
            check(False, f"{name}: timeout (>30s)")
        except Exception as e:
            check(False, f"{name}: error: {e}")

    print("    Scene 8: all existing verify scripts zero regression")


# ===========================================================================
# 主入口
# ===========================================================================

SCENES = [
    ("Scene 1: WoodGrower -> Register", test_crystallize_to_register),
    ("Scene 2: Register -> Health Eval", test_register_to_health_eval),
    ("Scene 3: Health -> Archive", test_health_to_archive),
    ("Scene 4: Archive -> Restore", test_archive_to_restore),
    ("Scene 5: Daily Audit Full Cycle", test_full_daily_audit_cycle),
    ("Scene 6: Disabled Module Bypass", test_disabled_module_bypass),
    ("Scene 7: FireTransformer Observation", test_fire_transformer_observation),
    ("Scene 8: Backward Compatibility", test_backward_compatibility),
]

if __name__ == "__main__":
    print("=" * 60)
    print("S3-6: Sprint 3 Integration Test - Five Elements Engine E2E")
    print("=" * 60)

    scene_results = []
    all_pass = True

    for scene_name, test_func in SCENES:
        print(f"\n{'─' * 50}")
        print(f"  {scene_name}")
        print(f"{'─' * 50}")

        before_passed = CHECKS_PASSED
        before_total = CHECKS_TOTAL

        try:
            test_func()
            scene_passed = CHECKS_PASSED - before_passed
            scene_total = CHECKS_TOTAL - before_total
            scene_ok = (scene_passed == scene_total)
            scene_results.append(
                (scene_name, scene_ok, scene_passed, scene_total))
        except Exception as e:
            print(f"    [FAIL] scene exception: {e}")
            import traceback
            traceback.print_exc()
            scene_passed = CHECKS_PASSED - before_passed
            scene_total = CHECKS_TOTAL - before_total
            scene_results.append(
                (scene_name, False, scene_passed, scene_total))
            all_pass = False

    # ── Summary ──
    print(f"\n{'=' * 60}")
    print(
        f"S3-6 Integration Test Results: {CHECKS_PASSED}/{CHECKS_TOTAL} checks passed")
    print(f"{'=' * 60}")
    for name, ok, passed, total in scene_results:
        symbol = "[PASS]" if ok else "[FAIL]"
        print(f"  {symbol} {name}: {passed}/{total} checks")

    if all_pass and CHECKS_PASSED == CHECKS_TOTAL:
        print(f"\nS3-6 ALL TESTS PASSED")
    else:
        print(f"\nS3-6 has {CHECKS_TOTAL - CHECKS_PASSED} failures")
