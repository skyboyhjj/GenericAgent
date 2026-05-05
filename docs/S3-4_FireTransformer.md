# S3-4: FireTransformer（火·化整合 — 轻量先行版）执行规格

> **版本**：v1.0.0  
> **日期**：2026-05-03  
> **状态**：待执行  
> **依赖**：S3-1（SkillRegistry）已完成  
> **设计依据**：《慧惠五行流转引擎-方案设计书 v1.1》第六·4节  
> **策略**：轻量先行——本期只做纯程序化的相似度计算与合并建议，LLM驱动的合并执行留待第二期


## 一、任务信息

| 属性 | 值 |
|:---|:---|
| 任务编号 | S3-4 |
| 任务名称 | FireTransformer 火·化整合（轻量先行版） |
| 优先级 | P1 |
| 预估工作量 | 1天 |
| 依赖 | S3-1（SkillRegistry）已完成 |

## 二、任务背景与本期定位

### 2.1 要解决的问题

随着木·生不断结晶新技能，SkillRegistry中会积累大量技能。不同技能可能在功能上相似但表述不同，导致技能碎片化、知识冗余积累、通用范式未提炼。

### 2.2 本期策略：识别冗余，输出建议

本期聚焦于**把冗余可视化**。`FireTransformer` 使用纯程序化算法扫描所有活跃技能，计算相似度并输出合并建议报告。完整的LLM合并执行、拆分回退、三层漏斗中的语义判断层，均留到第二期实现。

### 2.3 与方案书v1.1的对应关系

| 方案书功能 | 本期实现 | 第二期 |
|:---|:---|:---|
| Layer 1: 标签快筛 | ✅ 本期 | — |
| Layer 2: 工具交叉验证 | ✅ 本期 | — |
| Layer 3: LLM语义判断 | ❌ 预留接口 | ✅ |
| `scan()` 全量扫描 | ✅ 本期 | — |
| `find_similar_pairs()` | ✅ 本期（纯程序化） | — |
| `generate_suggestions()` | ✅ 本期 | — |
| `merge()` 执行合并 | ❌ 预留接口+注释 | ✅ |
| `split()` 拆分回退 | ❌ | ✅ |
| 合并产物校验(R5/R6/R7) | ❌ | ✅ |


## 三、当前代码状态

| 模块 | 状态 | 可用接口 |
|:---|:---|:---|
| `skills/skill_registry.py` | ✅ | `SkillRegistry.get_active_skills()` 返回所有活跃技能元数据 |
| `skills/root_auditor.py` | ✅ | 预留 `fire_transformer` 参数接口 |
| `skills/wood_grower.py` | ✅ | `WoodGrower.post_validate()`（第二期合并产物校验时复用） |
| `skills/metal_restrainer.py` | ✅ | 健康度模型参考 |

## 四、操作文件

| 文件 | 操作 | 说明 |
|:---|:---|:---|
| `skills/fire_transformer.py` | **新建** | FireTransformer 完整实现（轻量先行版） |
| `skills/verify_s3_4.py` | **新建** | S3-4 专项验证脚本 |

**不修改已有文件。**

## 五、FireTransformer 完整设计

### 5.1 配置数据结构

```python
@dataclass
class FireTransformerConfig:
    """火·化整合的配置（轻量先行版）"""
    enabled: bool = True                    # 总开关
    similarity_threshold: float = 0.6       # 综合相似度阈值（超过此值建议合并）
    high_confidence_threshold: float = 0.8  # 高置信度阈值（标记为强烈建议）
    max_suggestions: int = 5                # 单次审计最多输出的建议数
    
    # 四维度权重
    weight_name: float = 0.30               # 名称相似度权重
    weight_dependencies: float = 0.30       # 依赖项重叠度权重
    weight_tags: float = 0.20               # 标签重叠度权重
    weight_environment: float = 0.20        # 环境兼容性权重
```

### 5.2 核心类与公开方法

```python
class FireTransformer:
    """
    火·化整合（轻量先行版）：识别相似技能，输出合并建议。
    
    本期只做纯程序化的相似度计算与建议输出。
    完整的 LLM 驱动合并功能将在第二期实现（详见方案书v1.1第六·4节）。
    """
    
    def __init__(self, registry: SkillRegistry, config: FireTransformerConfig = None):
        """初始化。config 为 None 时使用默认配置。"""
        ...
    
    # === 本期实现 ===
    
    def calculate_similarity(self, skill_a: SkillMeta, skill_b: SkillMeta) -> float:
        """
        计算两个技能的综合相似度（0-1），纯程序化，不调用 LLM。
        
        四维度加权：
        - 名称相似度 (weight_name, 默认0.30)：基于单词重叠和公共子串
        - 依赖项重叠度 (weight_dependencies, 默认0.30)：dependencies 的 Jaccard 系数
        - 标签重叠度 (weight_tags, 默认0.20)：tags 的 Jaccard 系数
        - 环境兼容性 (weight_environment, 默认0.20)：os、python_version 等的一致性
        """
        ...
    
    def find_similar_pairs(self) -> list[SimilarityReport]:
        """
        扫描所有活跃技能，返回相似度超过阈值的技能对列表。
        按相似度降序排列（最相似的排最前），最多返回 max_suggestions 条。
        """
        ...
    
    def generate_suggestions(self) -> list[dict]:
        """
        生成合并建议列表，供 RootAuditor 和人工审核使用。
        
        返回格式：
        [
            {
                "skill_a": "check_files",
                "skill_b": "file_inspector",
                "similarity": 0.85,
                "confidence": "high",           # "high" (≥0.8) / "medium" (≥0.6)
                "dimensions": {
                    "name": 0.90,
                    "dependencies": 0.80,
                    "tags": 0.75,
                    "environment": 1.0
                },
                "reason": "名称高度相似，依赖项80%重叠，环境完全兼容"
            }
        ]
        """
        ...
    
    # === 第二期预留接口（本期仅返回占位信息） ===
    
    def merge(self, skill_a: str, skill_b: str, strategy: str = "auto") -> dict:
        """
        [第二期] 执行两个技能的合并。
        
        第二期将实现：
        1. 调用 LLM 进行语义相似度判断（三层漏斗 Layer 3）
        2. 生成 MergeProposal（含合并策略、收益评估、风险评估）
        3. 调用 LLM 合并两个 SOP 内容
        4. 使用 WoodGrower.post_validate() 校验合并产物
        5. 写入新 SOP，更新 SkillRegistry（merged_from 字段）
        6. 旧技能标记为 merged，旧 SOP 归档到 archive/merge_history/
        7. 更新 L1 索引
        
        策略选项（方案书第六·4.3节）：
        - "absorb_a": A 吸收 B 的差异化内容，B 归档
        - "absorb_b": B 吸收 A，A 归档
        - "create_new": 创建新 SOP，两者均归档
        
        当前版本返回提示信息，不执行实际操作。
        """
        return {
            "status": "not_implemented",
            "message": (
                "自动合并功能将在第二期（火·化完整版）中实现。"
                "届时将支持 LLM 驱动的语义判断、合并执行、拆分回退。"
                "当前请基于 generate_suggestions() 的建议手动审核。"
            ),
            "suggestion": f"建议手动合并 {skill_a} 和 {skill_b}",
            "available_strategies": ["absorb_a", "absorb_b", "create_new"],
            "planned_version": "v2.0.0"
        }
    
    def split(self, merged_skill_id: str) -> dict:
        """
        [第二期] 拆分已合并的技能，恢复原始技能。
        
        当前版本返回提示信息。
        """
        return {
            "status": "not_implemented",
            "message": "拆分回退功能将在第二期实现。",
            "planned_version": "v2.0.0"
        }
```

### 5.3 相似度计算详解（纯程序化，本期实现）

#### 名称相似度 (0.30)
```python
def _name_similarity(self, name_a: str, name_b: str) -> float:
    """
    基于单词重叠的简单文本匹配。
    - 去掉 _sop 后缀
    - 按下划线分词
    - 计算公共单词数与总单词数的比值
    - 额外加分：如果一个名称完全包含另一个名称
    """
```

#### 依赖项重叠度 (0.30)
```python
def _dependency_similarity(self, deps_a: list, deps_b: list) -> float:
    """
    Jaccard 系数 = |交集| / |并集|
    两个空列表 → 0.0（而非除以零）
    """
```

#### 标签重叠度 (0.20)
```python
def _tag_similarity(self, tags_a: list, tags_b: list) -> float:
    """
    同样使用 Jaccard 系数。
    如果 SkillMeta 中没有 tags 字段（向后兼容），返回 0.0。
    """
```

#### 环境兼容性 (0.20)
```python
def _environment_similarity(self, env_a: dict, env_b: dict) -> float:
    """
    比较多个子维度：
    - os：相同=1.0，不同=0.0，未知(null)=0.5
    - python_version：主版本号相同=1.0，不同=0.5，未知=0.5
    - 各项取平均
    如果 SkillMeta 中没有 environment 字段，返回 0.5（中性默认）。
    """
```

### 5.4 SimilarityReport 数据结构

```python
@dataclass
class SimilarityReport:
    skill_a: str                          # 技能A的ID
    skill_b: str                          # 技能B的ID
    overall_similarity: float             # 综合相似度 (0-1)
    name_similarity: float                # 名称相似度
    dependency_similarity: float          # 依赖项重叠度
    tag_similarity: float                 # 标签重叠度
    environment_similarity: float         # 环境兼容性
    confidence: str                       # "high" / "medium" / "low"
    reason: str                           # 可读的相似原因描述
```

### 5.5 与 RootAuditor 的集成预留

RootAuditor 已预留 `fire_transformer` 参数。在 weekly 审计中可调用：

```python
# 在 RootAuditor.audit() 的 weekly 分支中
if self.fire_transformer and self.fire_transformer.config.enabled:
    suggestions = self.fire_transformer.generate_suggestions()
    for s in suggestions:
        report.warnings.append({
            "type": "merge_suggestion",
            "skill_a": s["skill_a"],
            "skill_b": s["skill_b"],
            "similarity": s["similarity"],
            "confidence": s["confidence"]
        })
```

**本期不修改 RootAuditor**，此集成逻辑在 S3-6 集成测试或第二期时统一处理。

## 六、验证脚本

`skills/verify_s3_4.py` 需覆盖：

### 基本功能
1. 初始化：`FireTransformer(registry)` 创建成功，默认配置加载
2. 名称相似度：相同名称 → 1.0；完全不相关 → 接近 0；包含关系 → 高分
3. 依赖项重叠度：完全重叠 → 1.0；无重叠 → 0；两个空列表 → 0
4. 标签重叠度：完全重叠 → 1.0；无重叠 → 0；缺少 tags 字段 → 0
5. 环境兼容性：相同 OS + 相同 Python 版本 → 1.0；不同 OS → 0；未知字段 → 0.5
6. 综合相似度：各项均为 1.0 → 总分 1.0；各项均为 0 → 总分 0

### 相似对发现
7. `find_similar_pairs()`：构造相似技能对，正确识别并返回
8. 相似度阈值过滤：低于阈值的对不被返回
9. 空技能库：返回空列表，不抛异常
10. 仅一个活跃技能：返回空列表

### 建议输出
11. `generate_suggestions()`：返回结构正确的建议列表
12. 高相似度 (≥0.8) → confidence 为 "high"
13. 中相似度 (≥0.6) → confidence 为 "medium"
14. 建议数量不超过 max_suggestions

### 第二期预留接口
15. `merge()`：返回 `status: "not_implemented"` 和有效提示信息
16. `split()`：返回 `status: "not_implemented"` 和有效提示信息

### 边界与开关
17. `config.enabled = False`：`find_similar_pairs()` 返回空列表

## 七、验收标准

| # | 验收项 | 判定标准 |
|:---|:---|:---|
| 1 | 文件创建 | `skills/fire_transformer.py` 存在 |
| 2 | 相似度算法 | 四维度加权计算正确，边界情况处理完善 |
| 3 | 相似对发现 | `find_similar_pairs()` 正确识别相似技能 |
| 4 | 阈值过滤 | 低于阈值的对不被返回 |
| 5 | 建议输出 | `generate_suggestions()` 格式正确，原因描述可读 |
| 6 | 二期预留 | `merge()` 和 `split()` 返回占位信息，含详细注释说明第二期实现内容 |
| 7 | 禁用开关 | `config.enabled = False` 时返回安全默认值 |
| 8 | 验证脚本 | `verify_s3_4.py` 全部通过 |
| 9 | 历史测试兼容 | 所有已有验证脚本通过（S3-1 85项、S3-2 57项、S3-3 67项、S3-5 55项、S1系列） |

## 八、关键约束

- 不改动 GenericAgent 核心文件
- **本期不调用 LLM**——所有相似度计算纯程序化
- `merge()` 和 `split()` 方法完整保留，但仅返回占位信息，不执行实际操作
- 二期接口需包含充分的代码注释，说明未来版本的功能定位、参数含义、执行流程
- 与 SkillRegistry 的对接通过构造函数传入实例
- 兼容 SkillMeta 中可能不存在的字段（如 `tags`、`environment`、`dependencies`），使用 `getattr` 安全获取