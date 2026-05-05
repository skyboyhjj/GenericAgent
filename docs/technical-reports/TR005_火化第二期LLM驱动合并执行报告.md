# 火·化第二期 — LLM驱动合并执行报告

> **报告编号**：TR-2026-005  
> **范围**：FireTransformer v2.0 完整LLM驱动合并能力  
> **依赖**：Sprint 3（含轻量先行版 FireTransformer v1.0）已完成  
> **版本**：v1.0（工作计划 + 技术方案）  
> **日期**：2026-05-04  
> **状态**：技术方案完成，待执行

---

## 一、项目背景

### 1.1 当前基线（v1.0 轻量先行版）

| 模块                         | 状态   | 可用能力                                                                                         |
| ---------------------------- | ------ | ------------------------------------------------------------------------------------------------ |
| `skills/fire_transformer.py` | ✅ v1.0 | 四维度程序化相似度计算（名称/依赖/标签/环境），`find_similar_pairs()` + `generate_suggestions()` |
| `skills/skill_registry.py`   | ✅      | 技能注册、查询、版本管理                                                                         |
| `skills/wood_grower.py`      | ✅      | `post_validate()` 产物校验（R1-R4）                                                              |
| `skills/root_auditor.py`     | ✅      | 预留 `fire_transformer` 参数，可触发火·化动作                                                    |

### 1.2 缺失能力（v2.0 待补充）

- LLM 语义相似度判断（三层漏斗 Layer 3）
- LLM 驱动 SOP 合并执行（替换占位实现）
- 合并产物专属校验（R5/R6/R7）
- 拆分回退（`split()`）
- `merged_from` 和 `merge_history` 元数据字段

---

## 二、工作目标

为 FireTransformer 补全完整的 LLM 驱动合并能力：

1. **精准发现**：在程序化相似度上引入 LLM 语义判断作为第三层漏斗
2. **安全合并**：LLM 自动合并两个相似 SOP 为通用版本，产物通过全部质量校验
3. **可逆操作**：支持拆分回退，恢复被合并的原始技能
4. **完整追溯**：在 SkillRegistry 中记录合并历史

---

## 三、技术架构

### 3.1 整体架构（v2.0目标）

```
FireTransformer v2.0
│
├── [v1.0] calculate_similarity()      — 四维度程序化相似度
├── [v1.0] find_similar_pairs()        — 程序化扫描 + 阈值过滤
├── [v1.0] generate_suggestions()      — 合并建议输出
│
├── [新增] _llm_semantic_judge()       — Layer 3: LLM语义相似度判断
├── [新增] merge()                     — 执行合并（替换占位实现）
├── [新增] _generate_merged_sop()      — 调用LLM生成合并后SOP
├── [新增] _validate_merge_completeness()— R5/R6/R7 合并产物校验
├── [新增] split()                     — 拆分回退
│
└── [新增] MergeCandidate/MergeProposal/MergeResult — 合并数据流
```

### 3.2 三层漏斗相似度检测

```
Layer 1: 标签快筛（零成本）
  计算所有技能对的 Jaccard tag_similarity
  过滤 < 0.2 的对
  ↓
Layer 2: 工具交叉验证（低成本）
  计算候选对的 tool_overlap
  过滤 < 0.3 的对
  ↓
Layer 3: LLM语义判断（高成本，仅对少量候选对）
  调用LLM进行语义相似度判断
  综合三信号：similarity = 0.25×tag + 0.35×tool + 0.40×semantic
  similarity ≥ 0.7 → 进入合并流程
```

### 3.3 合并数据流

```
find_similar_pairs()
  → _llm_semantic_judge() [仅对候选对]
    → MergeProposal（含策略、收益评估）
      → [用户确认 / auto_merge]
        → merge()
          ├── _generate_merged_sop()      [LLM生成合并产物]
          ├── WoodGrower.post_validate()  [R1-R4标准校验]
          ├── _validate_merge_completeness() [R5-R7合并专属校验]
          ├── 写入新SOP文件
          ├── 更新SkillRegistry（旧→merged, 新→active）
          ├── 旧SOP归档至 archive/merge_history/
          └── 更新L1索引
        → MergeResult → 返回新 skill_id
```

---

## 四、核心实现设计

### 4.1 LLM语义相似度判断（Layer 3）

```python
SEMANTIC_JUDGMENT_PROMPT = """
你正在评估两个技能SOP是否应该合并。

【SOP A】
{sop_a}

【SOP B】
{sop_b}

请评估它们的语义相似度（0.0到1.0）：
- 0.0 = 完全无关
- 0.3 = 同领域但操作不同
- 0.5 = 有重叠操作但关注点不同
- 0.7 = 非常相似，仅在参数或范围上不同
- 1.0 = 几乎完全相同

同时回答：
1. 是否可以合并为一个更通用的SOP？（yes/no）
2. 推荐合并策略：absorb_a / absorb_b / create_new
3. 合并后的收益是什么？

输出JSON：
{"similarity": 0.0-1.0, "mergeable": true/false, 
 "merge_strategy": "absorb_a|absorb_b|create_new", 
 "merge_benefit": "一句话说明"}
"""
```

### 4.2 LLM SOP合并执行

```python
MERGE_SOP_PROMPT = """
你正在合并两个功能相似的SOP为一个更通用的版本。

【SOP A（将被{action_a}）】
{sop_a}

【SOP B（将被{action_b}）】
{sop_b}

【合并策略】：{strategy}

合并规则：
1. 保留所有关键操作步骤，不允许遗漏
2. 如果两SOP有不同操作方式，使用条件分支（"若...则..."）而非二选一
3. 去除重复的通用描述，保留各SOP特有的上下文要求
4. 不包含任何绝对路径、日期、用户目录等易变状态
5. 不包含任何API密钥、密码等敏感信息
6. 新SOP的目标是：两个原始SOP能覆盖的所有场景，合并后都能处理

输出：直接输出合并后的完整SOP内容（Markdown格式）。
"""
```

### 4.3 合并策略

| 策略       | 适用条件                 | 操作                      |
| ---------- | ------------------------ | ------------------------- |
| absorb_a   | A是B的超集               | A吸收B的差异化内容，B归档 |
| absorb_b   | B是A的超集               | B吸收A，A归档             |
| create_new | A和B交叉，各自有独特内容 | 创建新SOP，两者均归档     |

### 4.4 合并产物专属校验（R5-R7）

在 WoodGrower 标准校验（R1-R4）之后增加：

| 规则           | 检测方式                                           | 依据              |
| -------------- | -------------------------------------------------- | ----------------- |
| R5: 信息完整性 | 调用LLM对比合并产物与原始SOP，检测关键步骤是否丢失 | 合并不应丢信息    |
| R6: 无矛盾指令 | 调用LLM检测合并产物中是否有相互矛盾的步骤          | 两个SOP可能有冲突 |
| R7: 通用性提升 | 调用LLM判断合并产物是否比原始SOP覆盖更多场景       | 合并不是简单拼接  |

### 4.5 拆分回退（split）

```
split(merged_skill_id)
  → 从SkillRegistry读取 merged_from 字段
    → 从 archive/merge_history/ 恢复原始SOP文件
      → SkillRegistry恢复原始技能条目（status → active）
        → 删除合并产物SOP
          → 移除合并产物在SkillRegistry中的条目
            → 更新L1索引
              → 记录拆分历史
```

### 4.6 合并历史的目录结构

```
memory/archive/merge_history/
  └── 2026-05-20_stock_query+fund_query/
      ├── stock_query_sop.md       # 原始SOP A
      ├── fund_query_sop.md        # 原始SOP B
      └── merge_record.yaml        # 合并记录
```

**merge_record.yaml**：
```yaml
merge_id: "2026-05-20_stock_query+fund_query"
merged_at: "2026-05-20T14:30:00"
source_skills:
  - skill_id: stock_query
    similarity_contribution: 0.75
  - skill_id: fund_query
    similarity_contribution: 0.72
merged_skill_id: finance_query
merge_strategy: create_new
merge_benefit: "统一了股票和基金的查询流程"
completeness_check: passed
restorable: true
```

---

## 五、集成到 RootAuditor

在 weekly 审计中增加合并建议执行逻辑：

```python
# RootAuditor.audit(period="weekly")
if self.fire_transformer and self.fire_transformer.config.enabled:
    suggestions = self.fire_transformer.generate_suggestions()
    for s in suggestions:
        if s["confidence"] == "high" and self.fire_transformer.config.auto_merge:
            # 高置信度 + 自动合并开关 → 自动执行
            result = self.fire_transformer.merge(s["skill_a"], s["skill_b"])
        else:
            # 否则仅输出建议
            report.warnings.append({"type": "merge_suggestion", **s})
```

**默认 `auto_merge = False`**——避免自动执行高风险操作。

---

## 六、任务分解

| 编号 | 任务                          | 优先级 | 产出文件                              |
| ---- | ----------------------------- | ------ | ------------------------------------- |
| F2-1 | 设计LLM合并提示词模板         | P0     | `skills/merge_prompts.py`（新增）     |
| F2-2 | 实现 `merge()` 核心逻辑       | P0     | `skills/fire_transformer.py`（扩展）  |
| F2-3 | 实现合并产物专属校验（R5-R7） | P0     | `skills/fire_transformer.py` 新增方法 |
| F2-4 | 实现 `split()` 拆分回退       | P0     | `skills/fire_transformer.py`（扩展）  |
| F2-5 | 扩展 SkillRegistry 元数据字段 | P0     | `skills/skill_registry.py`（修改）    |
| F2-6 | 集成到 RootAuditor 审计流程   | P1     | `skills/root_auditor.py`（修改）      |
| F2-7 | 端到端验证与测试              | P0     | `skills/verify_f2.py`（新增）         |

---

## 七、验收标准

| #   | 验收项          | 判定标准                                    |
| --- | --------------- | ------------------------------------------- |
| 1   | LLM语义判断     | Layer 3正确调用LLM，返回结构化JSON          |
| 2   | merge()执行     | 成功生成合并产物，通过R1-R7全部校验         |
| 3   | 合并历史        | SkillRegistry中新增 merged_from 字段        |
| 4   | split()拆分     | 拆分后原始SOP与合并前完全一致（逐字符比对） |
| 5   | RootAuditor集成 | weekly审计输出合并建议                      |
| 6   | 验证脚本        | verify_f2.py 全部通过                       |
| 7   | 历史测试兼容    | S3-1~S3-6全部431项测试零回归                |

---

## 八、关键约束

- 不改动 GenericAgent 核心文件
- `merge()` 和 `split()` 默认需用户确认（`auto_merge` 默认关闭）
- LLM调用失败时有明确的错误处理和降级策略
- 所有已有431项测试保持通过

---

> **设计依据**：《慧惠五行流转引擎-方案设计书 v1.1》第六·4节  
> **详细计划**：`docs/火·化第二期_LLM驱动合并执行_工作计划与技术方案.md`  
> **代码位置**：`d:\GenericAgent\skills\fire_transformer.py`（v1.0, 541行）
