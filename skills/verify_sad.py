#!/usr/bin/env python3
"""
SAD-001: calculate_sad() 验证脚本

验证项:
 1. 默认权重（无 YAML）→ 全零 SAD
 2. 自定义 formula_weights → 主观权重正确读取
 3. dimension_counts → 客观权重正确推导
 4. 主观与客观不同 → SAD 计算正确
 5. formula_weights 格式错误 → 回退默认
 6. YAML 文件不存在 → 优雅处理
 7. 返回 dict 格式正确
 8. calculate_sad 与现有方法兼容（注册/归档/恢复不受影响）
"""

import inspect
from skills.skill_registry import (
    SkillMeta,
    SkillRegistry,
    STATUS_ACTIVE,
    STATUS_ARCHIVED,
)
import sys
import os
import shutil
import tempfile
import yaml
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))


PASS = "[PASS]"
FAIL = "[FAIL]"
passed = 0
failed = 0


def check(condition, msg):
    global passed, failed
    if condition:
        passed += 1
        print(f"  {PASS}: {msg}")
    else:
        failed += 1
        print(f"  {FAIL}: {msg}")


# ===========================================================================
# Setup: 临时目录 + 测试注册表
# ===========================================================================
tmp_dir = tempfile.mkdtemp(prefix="sad_test_")
tmp_memory = Path(tmp_dir) / "memory"
tmp_memory.mkdir(parents=True, exist_ok=True)
test_registry_path = tmp_memory / "skill_registry.yaml"

print("=" * 60)
print("SAD-001: calculate_sad() 验证")
print("=" * 60)


# ===========================================================================
# Test 1: 默认权重——无 YAML 文件
# ===========================================================================
print("\n[Test 1] 默认权重——注册表文件不存在")
registry1 = SkillRegistry(str(test_registry_path))

# 注册一些测试技能
meta1 = SkillMeta(name="test_skill", file="test.md")
registry1.register("test_skill", meta1)

sad1 = registry1.calculate_sad()
check(isinstance(sad1, dict), "返回类型为 dict")
check("temporal_sad" in sad1, "包含 temporal_sad")
check("spatial_sad" in sad1, "包含 spatial_sad")
check("wisdom_sad" in sad1, "包含 wisdom_sad")
check("causality_sad" in sad1, "包含 causality_sad")
check("overall_sad" in sad1, "包含 overall_sad")

# 全零（因为主观=客观=默认）
check(sad1["temporal_sad"] == 0.0,
      f"temporal_sad = 0.0 (实际: {sad1['temporal_sad']})")
check(sad1["spatial_sad"] == 0.0, f"spatial_sad = 0.0")
check(sad1["wisdom_sad"] == 0.0, f"wisdom_sad = 0.0")
check(sad1["causality_sad"] == 0.0, f"causality_sad = 0.0")
check(sad1["overall_sad"] == 0.0, f"overall_sad = 0.0")


# ===========================================================================
# Test 2: 自定义 formula_weights——主观权重读入
# ===========================================================================
print("\n[Test 2] 自定义 formula_weights（主观权重读取）")

# 准备 YAML: 自定义 formula_weights，无 dimension_counts
yaml_data2 = {
    "formula_weights": {
        "temporal": 0.10,
        "spatial": 0.20,
        "wisdom": 0.40,
        "causality": 0.30,
    },
    "skills": [],
}
tmp_memory2 = Path(tmp_dir) / "memory2"
tmp_memory2.mkdir(parents=True, exist_ok=True)
reg_path2 = tmp_memory2 / "skill_registry.yaml"
with open(reg_path2, "w", encoding="utf-8") as f:
    yaml.safe_dump(yaml_data2, f, allow_unicode=True)

registry2 = SkillRegistry(str(reg_path2))
registry2.register("dummy", SkillMeta(name="dummy", file="dummy.md"))
sad2 = registry2.calculate_sad()

# 主观=自定义, 客观=默认 → 应有非零 SAD
# temporal: |0.10 - 0.20| = 0.10
# spatial:  |0.20 - 0.20| = 0.00
# wisdom:   |0.40 - 0.30| = 0.10
# causality:|0.30 - 0.30| = 0.00
# overall:  (0.10 + 0.00 + 0.10 + 0.00) / 4 = 0.05
check(abs(sad2["temporal_sad"] - 0.10) < 0.001,
      f"temporal_sad = 0.10 (实际: {sad2['temporal_sad']})")
check(abs(sad2["spatial_sad"] - 0.00) < 0.001,
      f"spatial_sad = 0.00 (实际: {sad2['spatial_sad']})")
check(abs(sad2["wisdom_sad"] - 0.10) < 0.001,
      f"wisdom_sad = 0.10 (实际: {sad2['wisdom_sad']})")
check(abs(sad2["causality_sad"] - 0.00) < 0.001,
      f"causality_sad = 0.00 (实际: {sad2['causality_sad']})")
check(abs(sad2["overall_sad"] - 0.05) < 0.001,
      f"overall_sad = 0.05 (实际: {sad2['overall_sad']})")


# ===========================================================================
# Test 3: dimension_counts——客观权重推导
# ===========================================================================
print("\n[Test 3] dimension_counts——客观权重推导")

yaml_data3 = {
    "formula_weights": {
        "temporal": 0.25,
        "spatial": 0.25,
        "wisdom": 0.25,
        "causality": 0.25,
    },
    "dimension_counts": {
        "temporal": 30,
        "spatial": 10,
        "wisdom": 40,
        "causality": 20,
    },
    "skills": [],
}
tmp_memory3 = Path(tmp_dir) / "memory3"
tmp_memory3.mkdir(parents=True, exist_ok=True)
reg_path3 = tmp_memory3 / "skill_registry.yaml"
with open(reg_path3, "w", encoding="utf-8") as f:
    yaml.safe_dump(yaml_data3, f, allow_unicode=True)

registry3 = SkillRegistry(str(reg_path3))
registry3.register("dummy3", SkillMeta(name="dummy3", file="dummy3.md"))
sad3 = registry3.calculate_sad()

# 总次数 = 30+10+40+20 = 100
# 客观 temporal: 30/100 = 0.30
# 客观 spatial:  10/100 = 0.10
# 客观 wisdom:   40/100 = 0.40
# 客观 causality: 20/100 = 0.20
# SAD temporal: |0.25 - 0.30| = 0.05
# SAD spatial:  |0.25 - 0.10| = 0.15
# SAD wisdom:   |0.25 - 0.40| = 0.15
# SAD causality:|0.25 - 0.20| = 0.05
# overall: (0.05+0.15+0.15+0.05)/4 = 0.10
check(abs(sad3["temporal_sad"] - 0.05) < 0.001,
      f"temporal_sad = 0.05 (实际: {sad3['temporal_sad']})")
check(abs(sad3["spatial_sad"] - 0.15) < 0.001,
      f"spatial_sad = 0.15 (实际: {sad3['spatial_sad']})")
check(abs(sad3["wisdom_sad"] - 0.15) < 0.001,
      f"wisdom_sad = 0.15 (实际: {sad3['wisdom_sad']})")
check(abs(sad3["causality_sad"] - 0.05) < 0.001,
      f"causality_sad = 0.05 (实际: {sad3['causality_sad']})")
check(abs(sad3["overall_sad"] - 0.10) < 0.001,
      f"overall_sad = 0.10 (实际: {sad3['overall_sad']})")


# ===========================================================================
# Test 4: 格式错误的 formula_weights → 回退默认
# ===========================================================================
print("\n[Test 4] 格式错误的 formula_weights → 回退默认权重")

# 4a: 缺少维度
yaml_data4a = {
    "formula_weights": {
        "temporal": 0.5,
        "spatial": 0.5,
        # 缺少 wisdom 和 causality
    },
    "skills": [],
}
tmp_memory4a = Path(tmp_dir) / "memory4a"
tmp_memory4a.mkdir(parents=True, exist_ok=True)
reg_path4a = tmp_memory4a / "skill_registry.yaml"
with open(reg_path4a, "w", encoding="utf-8") as f:
    yaml.safe_dump(yaml_data4a, f, allow_unicode=True)

registry4a = SkillRegistry(str(reg_path4a))
registry4a.register("dummy4a", SkillMeta(name="dummy4a", file="dummy4a.md"))
sad4a = registry4a.calculate_sad()
# 应回退默认 → SAD 全零
check(sad4a["overall_sad"] == 0.0,
      f"缺少维度 → overall_sad = 0.0 (实际: {sad4a['overall_sad']})")

# 4b: 权重和不为 1.0
yaml_data4b = {
    "formula_weights": {
        "temporal": 0.3,
        "spatial": 0.3,
        "wisdom": 0.3,
        "causality": 0.3,
    },
    "skills": [],
}
tmp_memory4b = Path(tmp_dir) / "memory4b"
tmp_memory4b.mkdir(parents=True, exist_ok=True)
reg_path4b = tmp_memory4b / "skill_registry.yaml"
with open(reg_path4b, "w", encoding="utf-8") as f:
    yaml.safe_dump(yaml_data4b, f, allow_unicode=True)

registry4b = SkillRegistry(str(reg_path4b))
registry4b.register("dummy4b", SkillMeta(name="dummy4b", file="dummy4b.md"))
sad4b = registry4b.calculate_sad()
check(sad4b["overall_sad"] == 0.0,
      f"权重和≠1 → overall_sad = 0.0 (实际: {sad4b['overall_sad']})")

# 4c: formula_weights 不是 dict
yaml_data4c = {
    "formula_weights": "not_a_dict",
    "skills": [],
}
tmp_memory4c = Path(tmp_dir) / "memory4c"
tmp_memory4c.mkdir(parents=True, exist_ok=True)
reg_path4c = tmp_memory4c / "skill_registry.yaml"
with open(reg_path4c, "w", encoding="utf-8") as f:
    yaml.safe_dump(yaml_data4c, f, allow_unicode=True)

registry4c = SkillRegistry(str(reg_path4c))
registry4c.register("dummy4c", SkillMeta(name="dummy4c", file="dummy4c.md"))
sad4c = registry4c.calculate_sad()
check(sad4c["overall_sad"] == 0.0,
      f"非 dict 类型 → overall_sad = 0.0 (实际: {sad4c['overall_sad']})")


# ===========================================================================
# Test 5: 仅 dimension_counts（无 formula_weights）
# ===========================================================================
print("\n[Test 5] 仅 dimension_counts（无 formula_weights）→ 主观使用默认")

yaml_data5 = {
    "dimension_counts": {
        "temporal": 50,
        "spatial": 30,
        "wisdom": 10,
        "causality": 10,
    },
    "skills": [],
}
tmp_memory5 = Path(tmp_dir) / "memory5"
tmp_memory5.mkdir(parents=True, exist_ok=True)
reg_path5 = tmp_memory5 / "skill_registry.yaml"
with open(reg_path5, "w", encoding="utf-8") as f:
    yaml.safe_dump(yaml_data5, f, allow_unicode=True)

registry5 = SkillRegistry(str(reg_path5))
registry5.register("dummy5", SkillMeta(name="dummy5", file="dummy5.md"))
sad5 = registry5.calculate_sad()

# 总次数 = 100
# 客观 temporal: 50/100 = 0.50, 主观默认 0.20 → SAD = 0.30
# 客观 spatial:  30/100 = 0.30, 主观默认 0.20 → SAD = 0.10
# 客观 wisdom:   10/100 = 0.10, 主观默认 0.30 → SAD = 0.20
# 客观 causality: 10/100 = 0.10, 主观默认 0.30 → SAD = 0.20
# overall: (0.30+0.10+0.20+0.20)/4 = 0.20
check(abs(sad5["temporal_sad"] - 0.30) < 0.001,
      f"temporal_sad = 0.30 (实际: {sad5['temporal_sad']})")
check(abs(sad5["spatial_sad"] - 0.10) < 0.001,
      f"spatial_sad = 0.10 (实际: {sad5['spatial_sad']})")
check(abs(sad5["wisdom_sad"] - 0.20) < 0.001,
      f"wisdom_sad = 0.20 (实际: {sad5['wisdom_sad']})")
check(abs(sad5["causality_sad"] - 0.20) < 0.001,
      f"causality_sad = 0.20 (实际: {sad5['causality_sad']})")
check(abs(sad5["overall_sad"] - 0.20) < 0.001,
      f"overall_sad = 0.20 (实际: {sad5['overall_sad']})")


# ===========================================================================
# Test 6: calculate_sad 不影响已有方法
# ===========================================================================
print("\n[Test 6] calculate_sad 与已有方法兼容")

yaml_data6 = {
    "formula_weights": {
        "temporal": 0.15,
        "spatial": 0.15,
        "wisdom": 0.35,
        "causality": 0.35,
    },
    "skills": [],
}
tmp_memory6 = Path(tmp_dir) / "memory6"
tmp_memory6.mkdir(parents=True, exist_ok=True)
reg_path6 = tmp_memory6 / "skill_registry.yaml"
with open(reg_path6, "w", encoding="utf-8") as f:
    yaml.safe_dump(yaml_data6, f, allow_unicode=True)

registry6 = SkillRegistry(str(reg_path6))
meta6 = SkillMeta(name="sad_compat", file="sad_compat.md")
registry6.register("sad_compat", meta6)

# 1. 先执行 calculate_sad（不应影响后续操作）
sad6a = registry6.calculate_sad()
check(sad6a["overall_sad"] >= 0.0, "calculate_sad 执行成功")

# 2. 注册新技能 → 正常
registry6.register("sad_compat2", SkillMeta(
    name="sad_compat2", file="sad_compat2.md"))
check(registry6.get_skill_count() == 2,
      f"注册后技能数 = 2 (实际: {registry6.get_skill_count()})")

# 3. 更新使用统计 → 正常
registry6.update_usage("sad_compat", success=True)
skill6 = registry6.get("sad_compat")
check(skill6 is not None, "get() 正常返回")
check(skill6.use_count == 1, f"use_count = 1 (实际: {skill6.use_count})")

# 4. 归档 → 正常
registry6.archive("sad_compat")
check(registry6.get("sad_compat").status == STATUS_ARCHIVED,
      "archive() 正常")

# 5. 再次 calculate_sad（归档后）
sad6b = registry6.calculate_sad()
check(sad6b["overall_sad"] >= 0.0, "归档后 calculate_sad 仍正常")

# 6. 保存+加载 → 正常
registry6.save()
registry7 = SkillRegistry(str(reg_path6))
loaded = registry7.load()
check(loaded, "load() 成功")
check(registry7.get_skill_count() == 2,
      f"加载后技能数 = 2 (实际: {registry7.get_skill_count()})")
sad6c = registry7.calculate_sad()
check(sad6c["overall_sad"] == sad6b["overall_sad"],
      f"save/load 后 SAD 一致 (加载: {sad6c['overall_sad']}, 原始: {sad6b['overall_sad']})")


# ===========================================================================
# Test 7: 类型注解和文档字符串
# ===========================================================================
print("\n[Test 7] 类型注解和文档字符串")

sig = inspect.signature(SkillRegistry.calculate_sad)
check(sig.return_annotation != inspect.Parameter.empty,
      "有返回类型注解")
check("Dict" in str(sig.return_annotation) or "dict" in str(sig.return_annotation),
      f"返回类型包含 Dict: {sig.return_annotation}")

doc = SkillRegistry.calculate_sad.__doc__
check(doc is not None and len(doc) > 100,
      f"文档字符串存在且足够长 (长度: {len(doc) if doc else 0})")
check("SAD" in doc or "偏离度" in doc,
      "文档字符串提到 SAD/偏离度")
check("temporal" in doc and "wisdom" in doc,
      "文档字符串提到四维度名称")


# ===========================================================================
# Test 8: 边界——空的 dimension_counts（全零）
# ===========================================================================
print("\n[Test 8] 边界——dimension_counts 全零")

yaml_data8 = {
    "formula_weights": {
        "temporal": 0.30,
        "spatial": 0.20,
        "wisdom": 0.30,
        "causality": 0.20,
    },
    "dimension_counts": {
        "temporal": 0,
        "spatial": 0,
        "wisdom": 0,
        "causality": 0,
    },
    "skills": [],
}
tmp_memory8 = Path(tmp_dir) / "memory8"
tmp_memory8.mkdir(parents=True, exist_ok=True)
reg_path8 = tmp_memory8 / "skill_registry.yaml"
with open(reg_path8, "w", encoding="utf-8") as f:
    yaml.safe_dump(yaml_data8, f, allow_unicode=True)

registry8 = SkillRegistry(str(reg_path8))
registry8.register("dummy8", SkillMeta(name="dummy8", file="dummy8.md"))
sad8 = registry8.calculate_sad()
# 总次数=0 → 客观回退默认 → 主观=自定义, 客观=默认
check(abs(sad8["temporal_sad"] - 0.10) < 0.001,
      f"全零 counts → temporal_sad 应基于默认客观权重 (实际: {sad8['temporal_sad']})")


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
    print("SAD-001 ALL TESTS PASSED")
    sys.exit(0)
else:
    print(f"SAD-001 FAILED: {failed} test(s)")
    sys.exit(1)
