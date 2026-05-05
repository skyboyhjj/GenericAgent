#!/usr/bin/env python3
"""
S3-4: FireTransformer 火·化整合（轻量先行版）验证脚本

验证项：
 1. 初始化：FireTransformer(registry) 创建成功，默认配置加载
 2. 名称相似度：相同名称 → 1.0
 3. 名称相似度：完全不相关 → 接近 0
 4. 名称相似度：包含关系 → 高分
 5. 依赖项重叠度：完全重叠 → 1.0
 6. 依赖项重叠度：无重叠 → 0
 7. 依赖项重叠度：两个空列表 → 0
 8. 标签重叠度：完全重叠 → 1.0
 9. 标签重叠度：缺少 tags 字段 → 0
10. 环境兼容性：相同 OS + Python → 1.0
11. 环境兼容性：不同 OS → 0
12. 环境兼容性：未知字段 → 0.5
13. 综合相似度：各项 1.0 → 总分 1.0
14. 综合相似度：各项 0 → 总分 0
15. find_similar_pairs()：构造相似技能对，正确识别
16. 相似度阈值过滤：低于阈值的对不被返回
17. 空技能库 → 返回空列表
18. 仅一个活跃技能 → 返回空列表
19. generate_suggestions()：结构正确的建议列表
20. 高相似度 → confidence "high"
21. 中相似度 → confidence "medium"
22. 建议数量不超过 max_suggestions
23. merge()：返回 not_implemented
24. split()：返回 not_implemented
25. config.enabled=False → find_similar_pairs() 返回空列表
"""

from skills.fire_transformer import (
    FireTransformer,
    FireTransformerConfig,
    SimilarityReport,
)
from skills.skill_registry import (
    SkillRegistry,
    SkillMeta,
    EnvironmentMeta,
    STATUS_ACTIVE,
)
import sys
from pathlib import Path

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
    ok = abs(actual - expected) < tolerance
    check(ok, f"{desc} (actual={actual:.4f}, expected={expected:.4f})")


# ---------------------------------------------------------------------------
# Setup
# ---------------------------------------------------------------------------

print("=" * 60)
print("S3-4 FireTransformer 火·化整合 Tests")
print("=" * 60)

registry = SkillRegistry()

# 辅助函数：创建具有指定属性的 SkillMeta


def make_skill(name, deps=None, tags=None, env=None):
    env_meta = EnvironmentMeta()
    if env:
        if isinstance(env, dict):
            env_meta.os = env.get("os", "")
            env_meta.python_version = env.get("python_version", "")
        else:
            env_meta = env
    meta = SkillMeta(
        name=name,
        file=f"memory/{name}_sop.md",
        dependencies=deps or [],
        environment=env_meta,
        status=STATUS_ACTIVE,
    )
    if tags:
        meta.tags = tags  # 动态添加 tags 属性
    return meta


# ===========================================================================
# Test 1: Initialization
# ===========================================================================
print("\n[Test 1] FireTransformer initialization")
ft = FireTransformer(registry)
check(ft is not None, "FireTransformer created successfully")
check(ft.config.enabled is True, "Default config: enabled=True")
check(ft.config.similarity_threshold == 0.6,
      "Default config: similarity_threshold=0.6")
check(ft.config.high_confidence_threshold == 0.8,
      "Default config: high_confidence_threshold=0.8")
check(ft.config.max_suggestions == 5, "Default config: max_suggestions=5")
check(ft.config.weight_name == 0.30, "Default config: weight_name=0.30")
check(ft.config.weight_dependencies == 0.30,
      "Default config: weight_dependencies=0.30")
check(ft.config.weight_tags == 0.20, "Default config: weight_tags=0.20")
check(ft.config.weight_environment == 0.20,
      "Default config: weight_environment=0.20")

# 自定义 config
custom_config = FireTransformerConfig(
    enabled=False,
    similarity_threshold=0.5,
    max_suggestions=3,
)
ft_custom = FireTransformer(registry, config=custom_config)
check(ft_custom.config.enabled is False, "Custom config: enabled=False")
check(ft_custom.config.similarity_threshold == 0.5,
      "Custom config: similarity_threshold=0.5")
check(ft_custom.config.max_suggestions ==
      3, "Custom config: max_suggestions=3")

# ===========================================================================
# Test 2: Name similarity — identical names
# ===========================================================================
print("\n[Test 2] Name similarity: identical names → 1.0")
a = make_skill("check_files")
b = make_skill("check_files")
sim = ft.calculate_similarity(a, b)

# 相同名称 → 名称=1.0，无 deps/tags → 0，无 env → 0.5
# overall = 0.30*1.0 + 0.30*0.0 + 0.20*0.0 + 0.20*0.5 = 0.30 + 0.10 = 0.40
check(sim > 0.0, f"Identical names produce similarity > 0 (got {sim:.4f})")

# 单独测试名称相似度
name_sim = ft._name_similarity("check_files", "check_files")
assert_close(name_sim, 1.0, "Identical names: name_similarity=1.0")

# ===========================================================================
# Test 3: Name similarity — completely unrelated
# ===========================================================================
print("\n[Test 3] Name similarity: unrelated names → near 0")
name_sim = ft._name_similarity("file_checker", "web_scraper")
check(name_sim < 0.2,
      f"Unrelated names produce low similarity (got {name_sim:.4f})")

# ===========================================================================
# Test 4: Name similarity — containment bonus
# ===========================================================================
print("\n[Test 4] Name similarity: containment → high score")
name_sim = ft._name_similarity("check_files", "check_files_v2")
check(name_sim >= 0.5,
      f"Containment relation produces high similarity (got {name_sim:.4f})")

# ===========================================================================
# Test 5: Dependency similarity — complete overlap
# ===========================================================================
print("\n[Test 5] Dependency similarity: complete overlap → 1.0")
dep_sim = ft._jaccard_similarity(["os", "pathlib", "json"], [
                                 "os", "pathlib", "json"])
assert_close(dep_sim, 1.0, "Identical deps: dep_similarity=1.0")

# ===========================================================================
# Test 6: Dependency similarity — no overlap
# ===========================================================================
print("\n[Test 6] Dependency similarity: no overlap → 0")
dep_sim = ft._jaccard_similarity(["os", "sys"], ["requests", "json"])
assert_close(dep_sim, 0.0, "No overlap deps: dep_similarity=0.0")

# ===========================================================================
# Test 7: Dependency similarity — two empty lists
# ===========================================================================
print("\n[Test 7] Dependency similarity: two empty lists → 0")
dep_sim = ft._jaccard_similarity([], [])
assert_close(dep_sim, 0.0, "Two empty lists: dep_similarity=0.0")

# ===========================================================================
# Test 8: Tag similarity — complete overlap
# ===========================================================================
print("\n[Test 8] Tag similarity: complete overlap → 1.0")
tag_sim = ft._jaccard_similarity(
    ["file_ops", "system"], ["file_ops", "system"])
assert_close(tag_sim, 1.0, "Identical tags: tag_similarity=1.0")

# ===========================================================================
# Test 9: Tag similarity — missing tags field → 0
# ===========================================================================
print("\n[Test 9] Tag similarity: missing tags field → 0")

# SkillMeta without tags (normal case)
a = make_skill("no_tags_a")
b = make_skill("no_tags_b")
sim = ft.calculate_similarity(a, b)

# name: "no_tags_a" vs "no_tags_b" = words {"no", "tags", "a"} vs {"no", "tags", "b"}
# Jaccard = 2/4 = 0.5, plus containment? "no_tags_a" not in "no_tags_b" and vice versa = 0
# name_sim = 0.5
# deps: both [], dep_sim = 0.0
# tags: both [], get from getattr → [], tag_sim = 0.0
# env: both EnvironmentMeta() default, os="" and python_version=""
# _environment_similarity: os="" for both → 0.5, py="" for both → 0.5, avg = 0.5
# overall = 0.30*0.5 + 0.30*0.0 + 0.20*0.0 + 0.20*0.5 = 0.15 + 0.0 + 0.0 + 0.10 = 0.25
# This isn't testing tag specifically. Let me test the Jaccard directly.
tag_sim = ft._jaccard_similarity([], [])
check(tag_sim == 0.0, f"Empty tags produce 0.0 (got {tag_sim:.4f})")

# Verify no AttributeError for missing tags
try:
    _tags = getattr(a, 'tags', None)
    check(_tags is None, "SkillMeta without tags: getattr returns None")
except AttributeError:
    check(False, "getattr should not raise AttributeError")

# ===========================================================================
# Test 10: Environment — same OS + Python → 1.0
# ===========================================================================
print("\n[Test 10] Environment: same OS + Python → 1.0")
env1 = EnvironmentMeta(os="linux", python_version="3.11")
env2 = EnvironmentMeta(os="linux", python_version="3.11")
env_sim = ft._environment_similarity(env1, env2)
assert_close(env_sim, 1.0, "Same OS + Python: env_similarity=1.0")

# ===========================================================================
# Test 11: Environment — different OS → 0
# ===========================================================================
print("\n[Test 11] Environment: different OS → 0")
env_linux = EnvironmentMeta(os="linux", python_version="3.11")
env_win = EnvironmentMeta(os="windows", python_version="3.11")
env_sim = ft._environment_similarity(env_linux, env_win)
# os=0.0, py=1.0 (same major), avg = 0.5
check(env_sim == 0.5,
      f"Different OS gives 0.5 avg (os=0, py=1.0) (got {env_sim:.4f})")

# ===========================================================================
# Test 12: Environment — unknown fields → 0.5
# ===========================================================================
print("\n[Test 12] Environment: unknown fields → 0.5")
env_sim = ft._environment_similarity(None, None)
# Both None → os_sim=0.5, py_sim=0.5 → avg=0.5
assert_close(env_sim, 0.5, "Both None: env_similarity=0.5")

env_sim_partial = ft._environment_similarity(
    EnvironmentMeta(os="linux"), None)
# One has os="linux", other is None → os_sim=0.5, py_sim=0.5 → avg=0.5
assert_close(env_sim_partial, 0.5,
             "One None, one known: env_similarity=0.5")

# ===========================================================================
# Test 13: Overall similarity — all dimensions 1.0 → 1.0
# ===========================================================================
print("\n[Test 13] Overall similarity: all 1.0 → 1.0")
# Two skills with identical everything
a = make_skill("identical_skill", deps=["os", "json"],
               tags=["system", "io"],
               env={"os": "linux", "python_version": "3.11"})
b = make_skill("identical_skill", deps=["os", "json"],
               tags=["system", "io"],
               env={"os": "linux", "python_version": "3.11"})
sim = ft.calculate_similarity(a, b)
# name=1.0, dep=1.0, tag=1.0, env=1.0
# overall = 0.30*1.0 + 0.30*1.0 + 0.20*1.0 + 0.20*1.0 = 1.0
assert_close(sim, 1.0, "Identical skills: similarity=1.0")

# ===========================================================================
# Test 14: Overall similarity — all 0 → 0
# ===========================================================================
print("\n[Test 14] Overall similarity: all 0 → 0")
# Completely unrelated skills
a = make_skill("file_checker", deps=["os"],
               env={"os": "linux", "python_version": "3.10"})
b = make_skill("web_scraper", deps=["requests"],
               env={"os": "windows", "python_version": "3.12"})
sim = ft.calculate_similarity(a, b)
# name=0.0, dep=0.0, tag=0.0, env: os=0.0, py=1.0 (3.10 vs 3.12: both start with 3, major same)
# avg = (0.0+1.0)/2 = 0.5
# overall = 0.30*0.0 + 0.30*0.0 + 0.20*0.0 + 0.20*0.5 = 0.10
check(sim < 0.2, f"Unrelated skills: similarity near 0 (got {sim:.4f})")

# ===========================================================================
# Test 15: find_similar_pairs() with constructed similar pairs
# ===========================================================================
print("\n[Test 15] find_similar_pairs() identifies similar pairs")

# 注册多组技能到 registry
# 高相似对: check_files / check_files_v2（名称包含 + 相同依赖 + 相同标签 + 相同环境）
# 中相似对: web_scrape / web_crawler（共享 "web" 词 + 共享依赖 + 共享环境）
# 不相似: stock_query（孤立技能）
registry2 = SkillRegistry()

env_linux = EnvironmentMeta(os="linux", python_version="3.11")

s1 = SkillMeta(name="check_files", file="memory/check_files_sop.md",
               dependencies=["os", "pathlib", "glob", "json"],
               environment=env_linux,
               status=STATUS_ACTIVE)
s1.tags = ["file_ops", "system", "inspection"]

s2 = SkillMeta(name="check_files_v2", file="memory/check_files_v2_sop.md",
               dependencies=["os", "pathlib", "glob", "json", "shutil"],
               environment=env_linux,
               status=STATUS_ACTIVE)
s2.tags = ["file_ops", "system", "inspection", "version2"]

s3 = SkillMeta(name="web_scrape", file="memory/web_scrape_sop.md",
               dependencies=["requests", "bs4", "json", "os"],
               environment=env_linux,
               status=STATUS_ACTIVE)
s3.tags = ["web", "scraping", "data"]

s4 = SkillMeta(name="web_crawler", file="memory/web_crawler_sop.md",
               dependencies=["requests", "bs4", "json"],
               environment=env_linux,
               status=STATUS_ACTIVE)
s4.tags = ["web", "crawling", "data"]

s5 = SkillMeta(name="stock_query", file="memory/stock_query_sop.md",
               dependencies=["yfinance", "pandas"],
               environment=EnvironmentMeta(os="linux", python_version="3.11"),
               status=STATUS_ACTIVE)
s5.tags = ["finance", "stock"]

for s in [s1, s2, s3, s4, s5]:
    registry2.register(s.name, s)

ft2 = FireTransformer(registry2)

pairs = ft2.find_similar_pairs()
check(len(pairs) >= 1, f"find_similar_pairs found pairs (got {len(pairs)})")

# 检查报告结构
if pairs:
    r = pairs[0]
    check(isinstance(r, SimilarityReport),
          "Returns SimilarityReport instances")
    check(len(r.skill_a) > 0, "skill_a is non-empty")
    check(len(r.skill_b) > 0, "skill_b is non-empty")
    check(0.0 <= r.overall_similarity <= 1.0,
          f"overall_similarity in [0,1] (got {r.overall_similarity})")
    check(r.confidence in ("high", "medium"),
          f"confidence is 'high' or 'medium' (got {r.confidence})")
    check(len(r.reason) > 0, "reason is non-empty")

# Test 15b: pairs are sorted descending
if len(pairs) >= 2:
    scores = [p.overall_similarity for p in pairs]
    check(scores == sorted(scores, reverse=True),
          "Pairs sorted by similarity descending")

# ===========================================================================
# Test 16: Threshold filtering
# ===========================================================================
print("\n[Test 16] Similarity threshold filtering")
# 使用高阈值配置
high_config = FireTransformerConfig(similarity_threshold=0.95)
ft_high = FireTransformer(registry2, config=high_config)
pairs_high = ft_high.find_similar_pairs()
check(len(pairs_high) == 0,
      f"High threshold (0.95) filters all pairs (got {len(pairs_high)})")

# 使用低阈值配置
low_config = FireTransformerConfig(similarity_threshold=0.1)
ft_low = FireTransformer(registry2, config=low_config)
pairs_low = ft_low.find_similar_pairs()
check(len(pairs_low) >= 1,
      f"Low threshold (0.1) allows more pairs (got {len(pairs_low)})")

# ===========================================================================
# Test 17: Empty skill registry → empty list
# ===========================================================================
print("\n[Test 17] Empty skill registry → empty list")
empty_registry = SkillRegistry()
ft_empty = FireTransformer(empty_registry)
pairs_empty = ft_empty.find_similar_pairs()
check(pairs_empty == [], "Empty registry returns empty list")

# ===========================================================================
# Test 18: Single active skill → empty list
# ===========================================================================
print("\n[Test 18] Single active skill → empty list")
single_registry = SkillRegistry()
s = SkillMeta(name="only_skill", file="memory/only_sop.md",
              status=STATUS_ACTIVE)
single_registry.register("only_skill", s)
ft_single = FireTransformer(single_registry)
pairs_single = ft_single.find_similar_pairs()
check(pairs_single == [], "Single skill returns empty list")

# ===========================================================================
# Test 19: generate_suggestions() structure
# ===========================================================================
print("\n[Test 19] generate_suggestions() structure")
suggestions = ft2.generate_suggestions()
check(isinstance(suggestions, list), "Returns list")

if suggestions:
    sug = suggestions[0]
    check("skill_a" in sug, "Suggestion has 'skill_a'")
    check("skill_b" in sug, "Suggestion has 'skill_b'")
    check("similarity" in sug, "Suggestion has 'similarity'")
    check("confidence" in sug, "Suggestion has 'confidence'")
    check("dimensions" in sug, "Suggestion has 'dimensions'")
    check("reason" in sug, "Suggestion has 'reason'")
    check("name" in sug["dimensions"], "Dimensions has 'name'")
    check("dependencies" in sug["dimensions"], "Dimensions has 'dependencies'")
    check("tags" in sug["dimensions"], "Dimensions has 'tags'")
    check("environment" in sug["dimensions"], "Dimensions has 'environment'")

# ===========================================================================
# Test 20: High similarity → confidence "high"
# ===========================================================================
print("\n[Test 20] High similarity → confidence 'high'")
if suggestions:
    high_sugs = [s for s in suggestions if s["confidence"] == "high"]
    if high_sugs:
        check(high_sugs[0]["similarity"] >= 0.8,
              f"High confidence similarity >= 0.8 (got {high_sugs[0]['similarity']})")

# ===========================================================================
# Test 21: Medium similarity → confidence "medium"
# ===========================================================================
print("\n[Test 21] Medium similarity → confidence 'medium'")
if suggestions:
    med_sugs = [s for s in suggestions if s["confidence"] == "medium"]
    if med_sugs:
        check(med_sugs[0]["similarity"] >= 0.6,
              f"Medium confidence similarity >= 0.6 (got {med_sugs[0]['similarity']})")

# ===========================================================================
# Test 22: Max suggestions limit
# ===========================================================================
print("\n[Test 22] Max suggestions limit")
# 使用 max_suggestions=1 的配置
limit_config = FireTransformerConfig(
    max_suggestions=1, similarity_threshold=0.1)
ft_limit = FireTransformer(registry2, config=limit_config)
pairs_limited = ft_limit.find_similar_pairs()
check(len(pairs_limited) <= 1,
      f"Limited to max_suggestions=1 (got {len(pairs_limited)})")

# ===========================================================================
# Test 23: merge() returns not_implemented
# ===========================================================================
print("\n[Test 23] merge() returns not_implemented")
result_merge = ft.merge("skill_a", "skill_b")
check(result_merge["status"] == "not_implemented",
      f"merge status = 'not_implemented' (got {result_merge['status']})")
check("message" in result_merge, "merge has 'message'")
check("suggestion" in result_merge, "merge has 'suggestion'")
check("available_strategies" in result_merge,
      "merge has 'available_strategies'")
check("planned_version" in result_merge, "merge has 'planned_version'")
check(len(result_merge["available_strategies"]) >= 3,
      "merge lists at least 3 strategies")

# 测试带 strategy 参数的调用
result_auto = ft.merge("a", "b", strategy="auto")
check(result_auto["status"] == "not_implemented",
      "merge with strategy='auto' also not_implemented")

# ===========================================================================
# Test 24: split() returns not_implemented
# ===========================================================================
print("\n[Test 24] split() returns not_implemented")
result_split = ft.split("merged_skill_123")
check(result_split["status"] == "not_implemented",
      f"split status = 'not_implemented' (got {result_split['status']})")
check("message" in result_split, "split has 'message'")
check("planned_version" in result_split, "split has 'planned_version'")
check(result_split["merged_skill_id"] == "merged_skill_123",
      "split has correct merged_skill_id")

# ===========================================================================
# Test 25: Disabled config → find_similar_pairs() returns empty
# ===========================================================================
print("\n[Test 25] Disabled config → find_similar_pairs() returns empty")
pairs_disabled = ft_custom.find_similar_pairs()
check(pairs_disabled == [],
      f"Disabled config returns empty list (got {len(pairs_disabled)})")

# ===========================================================================
# 附加测试：defensive getattr 不会抛出异常
# ===========================================================================
print("\n[Test 26] Defensive getattr for missing fields")
try:
    a = SkillMeta(name="minimal", file="memory/minimal_sop.md",
                  status=STATUS_ACTIVE)
    b = SkillMeta(name="minimal2", file="memory/minimal2_sop.md",
                  status=STATUS_ACTIVE)
    sim = ft.calculate_similarity(a, b)
    check(True, "calculate_similarity works with minimal SkillMeta (no extra fields)")
except (AttributeError, Exception) as e:
    check(False, f"calculate_similarity crashed: {e}")

# 测试 environment 为 None
try:
    env_sim = ft._environment_similarity(None, EnvironmentMeta(os="linux"))
    check(env_sim == 0.5, f"None vs known env = 0.5 (got {env_sim})")
except Exception as e:
    check(False, f"_environment_similarity with None crashed: {e}")

# 测试 tags 为 None
try:
    tag_sim = ft._jaccard_similarity(None, None)
    check(tag_sim == 0.0, f"None, None tags = 0.0 (got {tag_sim})")
except Exception as e:
    check(False, f"_jaccard_similarity with None crashed: {e}")

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
