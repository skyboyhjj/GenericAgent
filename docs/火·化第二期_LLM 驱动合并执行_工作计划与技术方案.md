# 火·化第二期：LLM 驱动合并执行 — 工作计划与技术方案

> **版本**：v1.0.0  
> **日期**：2026-05-04  
> **状态**：待执行  
> **依赖**：Sprint 3（含轻量先行版 FireTransformer）已完成  
> **设计依据**：《慧惠五行流转引擎-方案设计书 v1.1》第六·4节


## 一、当前基线

| 模块 | 状态 | 可用能力 |
|:---|:---|:---|
| `skills/fire_transformer.py` | ✅ v1.0 | 四维度纯程序化相似度计算（名称/依赖项/标签/环境），`find_similar_pairs()` + `generate_suggestions()` |
| `skills/skill_registry.py` | ✅ | 技能注册、查询、版本管理 |
| `skills/wood_grower.py` | ✅ | `post_validate()` 产物校验（R1-R4） |
| `skills/root_auditor.py` | ✅ | 预留 `fire_transformer` 参数，可触发火·化动作 |

**缺失能力**：LLM 语义相似度判断（三层漏斗 Layer 3）、LLM 驱动 SOP 合并执行、合并产物专属校验（R5/R6/R7）、拆分回退、`merged_from` 和 `merge_history` 元数据字段。


## 二、工作目标

为 `FireTransformer` 补全完整的 LLM 驱动合并能力，使慧惠具备：
1. **精准发现**：在程序化相似度的基础上，引入 LLM 语义判断作为第三层漏斗，提升相似度判断准确率
2. **安全合并**：调用 LLM 自动合并两个相似 SOP 为通用版本，且合并产物通过质量校验
3. **可逆操作**：支持拆分回退，恢复被合并的原始技能
4. **完整追溯**：在 SkillRegistry 中记录合并历史，支持审计和人工复查


## 三、任务分解

| 编号 | 任务 | 预估工时 | 优先级 | 产出文件 |
|:---|:---|:---|:---|:---|
| **F2-1** | 设计 LLM 合并提示词模板 | 0.5天 | P0 | `skills/merge_prompts.py`（新增） |
| **F2-2** | 实现 `merge()` 核心逻辑 | 1天 | P0 | `skills/fire_transformer.py`（扩展） |
| **F2-3** | 实现合并产物专属校验（R5/R6/R7） | 1天 | P0 | `skills/fire_transformer.py` 内新增方法 |
| **F2-4** | 实现 `split()` 拆分回退 | 0.5天 | P0 | `skills/fire_transformer.py`（扩展） |
| **F2-5** | 扩展 SkillRegistry 元数据字段 | 0.5天 | P0 | `skills/skill_registry.py`（修改） |
| **F2-6** | 集成到 RootAuditor 审计流程 | 0.5天 | P1 | `skills/root_auditor.py`（修改） |
| **F2-7** | 端到端验证与测试 | 1天 | P0 | `skills/verify_f2.py`（新增） |


## 四、技术方案

### 4.1 整体架构

```
FireTransformer v2.0（火·化第二期）
│
├── [现有] calculate_similarity()        — 四维度程序化相似度
├── [现有] find_similar_pairs()          — 程序化扫描 + 阈值过滤
├── [现有] generate_suggestions()        — 合并建议输出
│
├── [新增] _llm_semantic_judge()         — Layer 3: LLM 语义相似度判断
├── [新增] merge()                       — 执行合并（替换占位实现）
├── [新增] _generate_merged_sop()        — 调用 LLM 生成合并后 SOP
├── [新增] _validate_merge_completeness()— R5/R6/R7 合并产物校验
├── [新增] split()                       — 拆分回退（替换占位实现）
│
└── [新增] MergeCandidate / MergeProposal / MergeResult — 合并数据流
```

### 4.2 数据流设计

```
find_similar_pairs()
    ↓ 程序化筛选（相似度 ≥ merge_threshold）
_llm_semantic_judge()  ← 仅对候选对调用 LLM
    ↓ 
MergeProposal（含合并策略、收益评估）
    ↓ 用户确认（或 auto_merge=True）
merge()
    ├── _generate_merged_sop()      ← 调用 LLM 生成合并产物
    ├── WoodGrower.post_validate()  ← 标准校验 R1-R4
    ├── _validate_merge_completeness() ← 合并专属校验 R5-R7
    ├── 写入新 SOP 文件
    ├── 更新 SkillRegistry（旧技能标记 merged，新技能注册）
    ├── 旧 SOP 归档至 archive/merge_history/
    └── 更新 L1 索引（如有）
    ↓
MergeResult → 返回新 skill_id
```

### 4.3 LLM 调用设计

**语义相似度判断（Layer 3）**

```python
# 新增提示词模板
SEMANTIC_JUDGMENT_PROMPT = """
你正在评估两个技能 SOP 是否应该合并。

【SOP A】
{sop_a}

【SOP B】
{sop_b}

请评估它们的语义相似度（0.0 到 1.0）：
- 0.0 = 完全无关
- 0.3 = 同领域但操作不同
- 0.5 = 有重叠操作但关注点不同
- 0.7 = 非常相似，仅在参数或范围上不同
- 1.0 = 几乎完全相同

同时回答：
1. 是否可以合并为一个更通用的 SOP？（yes/no）
2. 如果可以，推荐合并策略：absorb_a（A吸收B）/ absorb_b（B吸收A）/ create_new（创建新SOP）
3. 合并后的收益是什么？

输出 JSON：
{
  "similarity": 0.0-1.0,
  "mergeable": true/false,
  "merge_strategy": "absorb_a" | "absorb_b" | "create_new",
  "merge_benefit": "一句话说明"
}
"""
```

**LLM SOP 合并**

```python
MERGE_SOP_PROMPT = """
你正在合并两个功能相似的 SOP 为一个更通用的版本。

【SOP A（将被{action_a}）】
{sop_a}

【SOP B（将被{action_b}）】
{sop_b}

【合并策略】：{strategy}
- absorb_a：A吸收B的差异化内容，B归档
- absorb_b：B吸收A，A归档
- create_new：创建新SOP，两者均归档

合并规则：
1. 保留所有关键操作步骤，不允许遗漏
2. 如果两SOP在相同步骤上有不同操作方式，使用条件分支（"若...则..."）而非二选一
3. 去除重复的通用描述，但保留各SOP特有的上下文要求
4. 不包含任何绝对路径、日期、用户目录等易变状态
5. 不包含任何API密钥、密码等敏感信息
6. 新SOP的目标是：两个原始SOP能覆盖的所有场景，合并后都能处理

输出格式：直接输出合并后的完整 SOP 内容（Markdown 格式）。
"""
```

### 4.4 合并产物专属校验

在 WoodGrower 标准校验（R1-R4）之后，增加三个合并专属校验规则：

| 规则 | 检测方式 | 依据 |
|:---|:---|:---|
| **R5: 信息完整性** | 调用 LLM 对比合并产物与原始 SOP，检测关键步骤是否丢失 | 合并不应丢信息 |
| **R6: 无矛盾指令** | 调用 LLM 检测合并产物中是否有相互矛盾的步骤描述 | 两个 SOP 可能有冲突 |
| **R7: 通用性提升** | 调用 LLM 判断合并产物是否比原始 SOP 覆盖更多场景 | 合并不是简单拼接 |

```python
# R5 实现示例
COMPLETENESS_CHECK_PROMPT = """
检查合并产物是否保留了原始 SOP 的所有关键步骤。

【原始 SOP A】
{sop_a}

【原始 SOP B】
{sop_b}

【合并产物】
{merged_sop}

列出合并产物中**缺失的**原始关键步骤。如果没有缺失，回答"无缺失"。
以 JSON 格式输出：
{
  "complete": true/false,
  "missing_steps": ["步骤描述1", "步骤描述2"]  // 无缺失时为空数组
}
"""
```

### 4.5 合并历史与拆分回退

**SkillRegistry 元数据扩展**

```yaml
  finance_query:
    # ... 现有字段 ...
    status: active
    merged_from:                      # 新增：合并来源
      - skill_id: stock_query
        merged_at: "2026-05-20T14:30:00"
        original_file: "archive/merge_history/20260520_stock_query+fund_query/stock_query_sop.md"
      - skill_id: fund_query
        merged_at: "2026-05-20T14:30:00"
        original_file: "archive/merge_history/20260520_stock_query+fund_query/fund_query_sop.md"

  stock_query:
    status: merged                    # 新增状态：merged ≠ archived
    merged_into: finance_query
    merged_at: "2026-05-20T14:30:00"
```

**拆分回退逻辑**

```
split(merged_skill_id)
    ↓
从 SkillRegistry 读取 merged_from 字段
    ↓
从 archive/merge_history/ 恢复原始 SOP 文件
    ↓
在 SkillRegistry 中恢复原始技能条目（status → active）
    ↓
删除合并产物 SOP
    ↓
移除合并产物在 SkillRegistry 中的条目
    ↓
更新 L1 索引（如有）
    ↓
记录拆分历史
```

### 4.6 集成到 RootAuditor

在 weekly 审计中增加合并建议执行逻辑：

```python
# RootAuditor.audit(period="weekly")
if self.fire_transformer and self.fire_transformer.config.enabled:
    suggestions = self.fire_transformer.generate_suggestions()
    for s in suggestions:
        if s["confidence"] == "high" and self.fire_transformer.config.auto_merge:
            # 高置信度 + 自动合并开关开启 → 自动执行合并
            result = self.fire_transformer.merge(s["skill_a"], s["skill_b"])
            report.actions.append({
                "type": "merge",
                "skill_a": s["skill_a"],
                "skill_b": s["skill_b"],
                "new_skill_id": result.new_skill_id,
                "success": result.success
            })
        else:
            # 否则仅输出建议
            report.warnings.append({"type": "merge_suggestion", **s})
```

**默认 `auto_merge = False`**，避免自动执行高风险操作。用户可通过审计报告手动确认。


## 五、实施计划

| 阶段 | 任务 | 产出 | 验收标准 |
|:---|:---|:---|:---|
| **第1天** | F2-1 设计提示词模板 + F2-5 扩展 SkillRegistry | `merge_prompts.py`，`SkillMeta` 新增字段 | 提示词模板符合格式要求；YAML 可正确读写新字段 |
| **第2天** | F2-2 实现 `merge()` 核心逻辑 + F2-3 合并专属校验 | FireTransformer 扩展 | 两个测试技能可成功合并，产物通过 R1-R7 校验 |
| **第3天** | F2-4 实现 `split()` + F2-6 集成到 RootAuditor | 拆分回退可用，审计触发合并建议 | 拆分后原始技能完全恢复；审计报告含合并建议 |
| **第4天** | F2-7 端到端验证 | `verify_f2.py` 全部通过 | 从相似度检测→合并→拆分，全流程闭环 |

| 里程碑 | 完成标准 |
|:---|:---|
| M1: 合并可用 | 两个测试技能可通过 LLM 合并为一个新 SOP，产物通过全部校验 |
| M2: 拆分可用 | 合并后的技能可拆分为原始两个技能，文件完全恢复 |
| M3: 第二期交付 | 端到端验证通过，历史测试零回归 |


## 六、验收标准

| # | 验收项 | 判定标准 |
|:---|:---|:---|
| 1 | LLM 语义判断 | Layer 3 正确调用 LLM，返回结构化 JSON，相似度在 0-1 区间 |
| 2 | `merge()` 执行 | 成功生成合并产物，产物通过 R1-R7 全部校验 |
| 3 | 合并历史 | SkillRegistry 中新增 `merged_from` 字段，旧技能标记为 `merged` |
| 4 | `split()` 拆分 | 拆分后原始 SOP 文件与合并前完全一致（逐字符比对） |
| 5 | RootAuditor 集成 | weekly 审计输出合并建议，auto_merge 开关正常 |
| 6 | 验证脚本 | `verify_f2.py` 全部通过 |
| 7 | 历史测试兼容 | S3-1 ~ S3-6 全部 431 项测试零回归 |


## 七、关键约束

- 不改动 GenericAgent 核心文件
- `merge()` 和 `split()` 默认需要用户确认（`auto_merge` 默认关闭）
- 合并操作记录完整审计日志
- LLM 调用失败时有明确的错误处理和降级策略
- 所有已有 431 项测试保持通过

---

请确认是否按此方案启动火·化第二期开发？我将按 F2-1 开始起草 Qoder-ready 执行规格。