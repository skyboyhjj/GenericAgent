# S3-6: Sprint 3 集成测试 — 五行流转引擎端到端验证

> **版本**：v1.0.0  
> **日期**：2026-05-03  
> **状态**：待执行  
> **依赖**：S3-1、S3-2、S3-3、S3-4、S3-5 全部完成


## 一、核心闭环

本次集成测试验证以下核心闭环：

```
木·生 (WoodGrower)
    ↓ 触发结晶，产物校验通过
SkillRegistry
    ↓ 注册技能，记录元数据
金·克 (MetalRestrainer)
    ↓ 健康度评估，低健康度自动归档
RootAuditor
    ↓ 周期审计，串联木·生与金·克
    ↓
技能生态自动维持健康平衡
```

### 1.2 火·化（FireTransformer）的处理策略

| 功能 | 本期测试策略 |
|:---|:---|
| `find_similar_pairs()` | 👁️ 纳入观测，验证输出格式和阈值过滤 |
| `generate_suggestions()` | 👁️ 纳入观测，验证建议结构 |
| `merge()` | ❌ 跳过（返回 `not_implemented`） |
| `split()` | ❌ 跳过（返回 `not_implemented`） |


## 二、当前代码状态

| 模块 | 文件 | 测试数 | 状态 |
|:---|:---|:---|:---|
| S3-1 SkillRegistry | `skills/skill_registry.py` | 85 | ✅ |
| S3-2 WoodGrower | `skills/wood_grower.py` | 57 | ✅ |
| S3-3 MetalRestrainer | `skills/metal_restrainer.py` | 67 | ✅ |
| S3-4 FireTransformer | `skills/fire_transformer.py` | 69 | ✅ |
| S3-5 RootAuditor | `skills/root_auditor.py` | 55 | ✅ |
| GA 核心 | `agentmain.py`, `agent_loop.py`, `ga.py` | — | 零修改 |

## 三、操作文件

| 文件 | 操作 | 说明 |
|:---|:---|:---|
| `skills/verify_s3_6.py` | **新建** | Sprint 3 集成测试脚本 |

## 四、测试场景设计

### 场景 1：木·生 → 注册（核心链路 A）

```
WoodGrower.should_trigger_distill() → True
    ↓
WoodGrower.build_distill_prompt() → 蒸馏指令文本
    ↓
（模拟新 SOP 被 GA 写入 memory/ 目录）
    ↓
WoodGrower.post_validate(sop_path) → ValidationResult
    ↓ 通过
SkillRegistry.register(sop_path) → skill_id
```

1. 构造含 3+ 次成功工具调用的 turn_history
2. 验证 should_trigger_distill 返回 True
3. 验证 build_distill_prompt 返回有效指令
4. 创建模拟 SOP 文件（无易变状态），验证 post_validate 通过
5. 调用 SkillRegistry.register()，验证注册成功
6. 验证 registry 中可查询到该技能

### 场景 2：注册 → 金·克评估（核心链路 B）

```
SkillRegistry.register() × N
    ↓
MetalRestrainer.evaluate_all()
    ↓
按健康度升序排列的 HealthReport 列表
```

1. 注册多个技能（含不同 last_used 时间、不同的 success_rate）
2. 调用 MetalRestrainer.evaluate_all()
3. 验证返回列表按健康度升序排列
4. 验证最近使用的技能健康度高于长期未用的技能
5. 验证成功率高的技能健康度高于成功率低的技能

### 场景 3：金·克评估 → 归档（核心链路 C）

```
MetalRestrainer.evaluate_all()
    ↓
识别健康度 < archive_threshold 的技能
    ↓
MetalRestrainer.archive(skill_id)
    ↓
SkillRegistry 中 status → archived
    ↓
get_active_skills() 不再包含该技能
```

1. 构造健康度明显低于 0.3 的技能（last_used: 120天前）
2. 调用 evaluate_all()，验证 recommendation 为 "archive"
3. 执行 archive()，验证返回值 True
4. 验证该技能在 get_active_skills() 中不再出现
5. 验证该技能在 get_archived_skills() 中出现

### 场景 4：归档 → 恢复

```
MetalRestrainer.restore(skill_id)
    ↓
SkillRegistry 中 status → active
    ↓
get_active_skills() 重新包含该技能
```

1. 对场景 3 中已归档的技能，调用 restore()
2. 验证返回值 True
3. 验证该技能重新出现在 get_active_skills() 中
4. 验证该技能从 get_archived_skills() 中移除

### 场景 5：每日审计全流程（端到端闭环）

```
RootAuditor.audit(period="daily")
    ↓
MetalRestrainer.evaluate_all()
    ↓
低健康度技能 → archive()
    ↓
AuditReport 含动作摘要
    ↓
审计时间更新
    ↓
get_audit_history() 可追溯
```

1. 注册多个不同健康度的技能
2. 调用 RootAuditor.audit(period="daily")
3. 验证 AuditReport 包含正确的 active_count 和 archived_count
4. 验证低健康度技能在审计中被自动归档
5. 验证审计后 get_last_audit_time() 更新
6. 验证 get_audit_history() 包含本次审计记录

### 场景 6：禁用开关

```
config.enabled = False
    ↓
各模块方法返回安全默认值
    ↓
审计跳过该模块
```

1. 关闭 WoodGrower：should_trigger_distill() → False
2. 关闭 MetalRestrainer：evaluate_all() → 空列表
3. 关闭 FireTransformer：find_similar_pairs() → 空列表
4. 验证所有模块在禁用状态下不抛异常

### 场景 7：火·化观测（👁️ 纳入但不验证 merge）

```
FireTransformer.find_similar_pairs()
    ↓
SimilarityReport 列表
    ↓
generate_suggestions()
    ↓
结构化建议列表（含 confidence 和 reason）
```

1. 注册两个相似技能（相同的 dependencies、相似的名称和 tags）
2. 调用 find_similar_pairs()
3. 验证返回的相似度 > 0.6
4. 验证 generate_suggestions() 包含该技能对
5. 验证 merge() 返回 "not_implemented"（不强制测试）
6. 验证 split() 返回 "not_implemented"（不强制测试）

### 场景 8：回归验证

1. S3-1 SkillRegistry: 85项全部通过
2. S3-2 WoodGrower: 57项全部通过
3. S3-3 MetalRestrainer: 67项全部通过
4. S3-4 FireTransformer: 69项全部通过
5. S3-5 RootAuditor: 55项全部通过
6. Sprint 1 系列: verify_soul.py 等全部通过

## 五、验证脚本结构

`skills/verify_s3_6.py`：

```python
"""
S3-6: Sprint 3 集成测试 — 五行流转引擎端到端验证

测试范围：
  ✅ 木·生 → 注册 → 金·克评估 → 归档 → 恢复 → 审计闭环
  ✅ 禁用开关
  👁️ 火·化相似度观测（merge/split 跳过）

测试策略：
  - 全程不调用 LLM，纯程序化验证
  - 使用模拟 turn_history 和 SOP 文件
  - 每个场景独立运行，确保状态隔离
"""

import sys, os, json, tempfile, shutil
from datetime import datetime, timezone, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from skills.skill_registry import SkillRegistry
from skills.wood_grower import WoodGrower, WoodGrowerConfig
from skills.metal_restrainer import MetalRestrainer, MetalRestrainerConfig
from skills.fire_transformer import FireTransformer, FireTransformerConfig
from skills.root_auditor import RootAuditor


def test_crystallize_to_register():
    """场景 1：木·生 → 注册"""
    ...

def test_register_to_health_eval():
    """场景 2：注册 → 金·克评估"""
    ...

def test_health_to_archive():
    """场景 3：金·克评估 → 归档"""
    ...

def test_archive_to_restore():
    """场景 4：归档 → 恢复"""
    ...

def test_full_daily_audit_cycle():
    """场景 5：每日审计全流程"""
    ...

def test_disabled_module_bypass():
    """场景 6：禁用开关"""
    ...

def test_fire_transformer_observation():
    """场景 7：火·化观测"""
    ...

def test_backward_compatibility():
    """场景 8：回归验证"""
    ...


if __name__ == "__main__":
    results = []
    
    for name, test_func in [
        ("场景1: 木·生→注册", test_crystallize_to_register),
        ("场景2: 注册→金·克评估", test_register_to_health_eval),
        ("场景3: 金·克→归档", test_health_to_archive),
        ("场景4: 归档→恢复", test_archive_to_restore),
        ("场景5: 每日审计全流程", test_full_daily_audit_cycle),
        ("场景6: 禁用开关", test_disabled_module_bypass),
        ("场景7: 火·化观测", test_fire_transformer_observation),
        ("场景8: 回归验证", test_backward_compatibility),
    ]:
        try:
            test_func()
            results.append((name, "PASSED", None))
        except AssertionError as e:
            results.append((name, "FAILED", str(e)))
        except Exception as e:
            results.append((name, "ERROR", str(e)))
    
    # 输出汇总报告
    passed = sum(1 for _, status, _ in results if status == "PASSED")
    total = len(results)
    print(f"\n{'='*60}")
    print(f"S3-6 集成测试结果: {passed}/{total} 通过")
    print(f"{'='*60}")
    for name, status, detail in results:
        symbol = "✅" if status == "PASSED" else "❌"
        print(f"  {symbol} {name}")
        if detail:
            print(f"     └─ {detail}")
    
    if passed == total:
        print(f"\n🎉 S3-6 ALL TESTS PASSED")
    else:
        print(f"\n⚠️  S3-6 {total - passed} FAILURES")
```

## 六、验收标准

| # | 验收项 | 判定标准 |
|:---|:---|:---|
| 1 | 场景 1：木·生→注册 | should_trigger_distill 正确触发，post_validate 校验通过，register 成功 |
| 2 | 场景 2：注册→金·克评估 | evaluate_all 按健康度升序排列，高活跃度高健康度 |
| 3 | 场景 3：金·克→归档 | 低健康度技能自动归档，get_active_skills 排除 |
| 4 | 场景 4：归档→恢复 | restore 成功，技能恢复为 active |
| 5 | 场景 5：每日审计全流程 | audit(period="daily") 完成，report 含动作摘要，审计时间更新 |
| 6 | 场景 6：禁用开关 | 各模块 disabled 时返回安全默认值 |
| 7 | 场景 7：火·化观测 | find_similar_pairs 正确识别相似对，generate_suggestions 格式正确 |
| 8 | 场景 8：回归验证 | S3-1~S3-5 + S1系列全部通过 |
| 9 | 零侵入 | GA 核心文件零修改 |

## 七、关键约束

- 不改动 GenericAgent 核心文件
- 全程不调用 LLM，纯程序化验证
- 每个测试场景使用独立的临时 SkillRegistry，确保状态隔离
- 集成测试结果输出为结构化的终端报告
- 所有已有验证脚本通过（S3-1 85项、S3-2 57项、S3-3 67项、S3-4 69项、S3-5 55项）