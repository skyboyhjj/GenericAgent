# S3-3: MetalRestrainer（金·克修剪）执行规格

> **版本**：v1.0.0
> **日期**：2026-05-03
> **状态**：待执行
> **依赖**：S3-1 已完成（SkillRegistry + 版本管理可用）
> **设计依据**：《慧惠五行流转引擎-方案设计书 v1.0》第六·3节


## 一、任务信息

| 属性 | 值 |
|:---|:---|
| 任务编号 | S3-3 |
| 任务名称 | MetalRestrainer 金·克修剪——健康度评估 + 自动归档 |
| 优先级 | P0 |
| 预估工作量 | 2天 |
| 依赖 | S3-1 完成（`skills/skill_registry.py` 可用） |

## 二、任务背景与设计理念

### 2.1 要解决的真实问题

GA 的技能管理存在一个结构性缺陷：**只会“生”，不会“克”**。技能只增不减，长期运行后将导致：

| 问题 | 影响 |
|:---|:---|
| 记忆膨胀 | L1 索引条目持续增长，检索效率下降 |
| 冗余积累 | 相似技能并存，Agent 选择困难 |
| 过期技能 | API 变更后旧 SOP 仍被引用，执行失败 |
| 无反馈闭环 | 使用频率和成功率不被追踪，无法判断技能价值 |

### 2.2 核心设计理念：为道日损

**“损”不是删除，而是归档。** MetalRestrainer 对技能进行健康度评估，将低健康度技能从活跃区移至归档区。归档不是终点——技能可随时恢复。

### 2.3 与 GA 原生机制的关系

MetalRestrainer 完全独立于 GA 核心，通过 SkillRegistry 读取和更新技能元数据。GA 核心代码零改动。


## 三、当前代码状态

| 模块 | 状态 | 可用接口 |
|:---|:---|:---|
| `skills/skill_registry.py` | ✅ | `SkillRegistry.get_active_skills()`、`SkillRegistry.archive()`、`SkillRegistry.recover()` |
| `skills/wood_grower.py` | ✅ | `WoodGrower.post_validate()` 提供 SOP 校验（可选集成） |
| GA 记忆目录 | ✅ | `memory/` 含 SOP 文件、L1 索引、L0 宪法 |

## 四、操作文件

| 文件 | 操作 | 说明 |
|:---|:---|:---|
| `skills/metal_restrainer.py` | **新建** | MetalRestrainer 完整实现（健康度模型 + 归档策略） |
| `skills/verify_s3_3.py` | **新建** | S3-3 专项验证脚本 |

**不修改已有文件。**

## 五、MetalRestrainer 完整设计

### 5.1 配置数据结构

```python
@dataclass
class MetalRestrainerConfig:
    """金·克修剪的配置"""
    enabled: bool = True                    # 总开关
    archive_threshold: float = 0.3          # 健康度低于此值触发归档
    warning_threshold: float = 0.5          # 健康度低于此值仅警告
    freshness_decay: float = 0.02           # 新鲜度衰减率 λ（半衰期约 35 天）
    weights: tuple = (0.4, 0.4, 0.2)       # (新鲜度权重, 可靠性权重, 复杂度权重)
    archive_dir: str = "memory/archive"     # 归档目录
    whitelist: tuple = (                    # 白名单：永不被修剪的核心技能
        "memory_management_sop",
    )
    dry_run: bool = False                  # 仅评估不执行（用于预览）
```

### 5.2 健康度计算模型

```python
def calculate_health(self, meta: SkillMeta) -> float:
    """
    健康度 = w1 × 新鲜度 + w2 × 可靠性 + w3 × 复杂度加分
    
    新鲜度(0-1) = exp(-λ × 距上次使用天数)
        35天不用 → 约0.5，90天不用 → 约0.17
    
    可靠性(0-1) = success_rate（use_count=0时默认0.5）
    
    复杂度加分(0-1) = min(tool_count / 5, 1.0)
    """
```

**边界情况处理**：

| 情况 | 处理方式 |
|:---|:---|
| `use_count = 0`（从未复用） | 新鲜度 = 1.0，可靠性 = 0.5（中性默认） |
| `success_rate = null` | 可靠性 = 0.5 |
| `last_used = null` | 新鲜度使用距创建天数计算 |
| 技能在白名单中 | 始终返回 1.0（永不修剪） |

### 5.3 核心类与公开方法

```python
class MetalRestrainer:
    """
    金·克修剪：评估技能健康度，自动归档低健康度技能。
    
    设计原则：
    - "为道日损"：修剪不是删除，而是归档——可恢复
    - 懒惰归档：只在健康度明确低于阈值时才行动
    - 白名单保护：核心技能永不修剪
    """
    
    def __init__(self, registry: SkillRegistry, config: MetalRestrainerConfig = None):
        """初始化。config 为 None 时使用默认配置。"""
        ...
    
    def evaluate(self, skill_id: str) -> HealthReport:
        """
        评估单个技能的健康度。
        返回 HealthReport 含评分和细分维度。
        """
        ...
    
    def evaluate_all(self) -> list[HealthReport]:
        """
        评估所有活跃技能的健康度。
        返回按健康度升序排列的报告列表（最危险的排最前）。
        跳过白名单技能。
        """
        ...
    
    def archive(self, skill_id: str) -> bool:
        """
        归档单个技能：
        1. 在 registry 中将 status 改为 archived，记录归档原因
        2. 返回 True 表示已归档，False 表示技能不存在或已是归档状态
        """
        ...
    
    def restore(self, skill_id: str) -> bool:
        """
        恢复已归档的技能：
        1. 在 registry 中将 status 改回 active
        2. 返回 True 表示已恢复
        """
        ...
    
    def get_archived_skills(self) -> list[dict]:
        """列出所有已归档的技能及其归档原因和健康度"""
        ...
```

### 5.4 评估报告数据结构

```python
@dataclass
class HealthReport:
    skill_id: str              # 技能标识
    health_score: float        # 综合健康度 (0-1)
    freshness: float           # 新鲜度得分
    reliability: float         # 可靠性得分
    complexity_bonus: float    # 复杂度加分
    days_since_last_use: int   # 距上次使用天数（-1 表示从未使用）
    use_count: int             # 被复用次数
    success_rate: float        # 成功率
    recommendation: str        # 建议："archive" / "warn" / "keep"
    reason: str                # 建议理由
```

**recommendation 判断逻辑**：
- `health_score < archive_threshold` → `"archive"`
- `health_score < warning_threshold` → `"warn"`
- 其他 → `"keep"`

### 5.5 供后续集成使用的预留能力

在 S3-5 时，RootAuditor 将调用 MetalRestrainer 进行周期审计：

1. `evaluate_all()` → 获取所有技能的评估报告
2. 对 `recommendation == "archive"` 的技能，调用 `archive()`
3. 生成审计报告，记录当日归档的技能及其健康度

但以上集成行为**不是 S3-3 的范围**，S3-3 只实现 MetalRestrainer 模块本身及单元验证。


## 六、验证脚本

`skills/verify_s3_3.py` 需覆盖：

1. 初始化：`MetalRestrainer(registry)` 创建成功，默认配置加载
2. 健康度计算：`evaluate()` 返回有效 HealthReport，且 `health_score ∈ [0, 1]`
3. 新鲜度衰减：距上次使用 90 天的技能健康度 < 0.5
4. 可靠性影响：`success_rate = 0.5` 的技能的可靠性得分 = 0.5
5. 复杂度加分：工具调用次数 ≥5 的技能获得满分复杂度加分
6. 边界情况：`use_count = 0` 的技能使用默认可靠性 0.5
7. `evaluate_all()` 返回所有活跃技能报告，跳过白名单
8. `evaluate_all()` 返回按健康度升序排列
9. `archive()` 后技能状态变为 archived
10. `archive()` 后 `get_active_skills()` 不再包含该技能
11. `restore()` 后技能恢复为 active
12. `get_archived_skills()` 返回正确列表
13. 白名单技能 `evaluate()` 返回健康度 1.0
14. 白名单技能 `archive()` 返回 False（拒绝归档）
15. `dry_run=True` 时 `archive()` 不实际归档
16. 禁用开关：`config.enabled = False` 时 `evaluate_all()` 返回空列表

## 七、验收标准

| # | 验收项 | 判定标准 |
|:---|:---|:---|
| 1 | 文件创建 | `skills/metal_restrainer.py` 存在，含完整 MetalRestrainer 类 |
| 2 | 健康度计算 | `evaluate()` 返回结果与公式计算结果误差 < 0.01 |
| 3 | 边界情况 | `use_count=0`、`success_rate=null` 等边界正确使用默认值 |
| 4 | 归档功能 | `archive()` 后 status 变为 archived，`get_active_skills()` 不再包含 |
| 5 | 恢复功能 | `restore()` 后 status 恢复为 active |
| 6 | 白名单保护 | 白名单技能永不被归档，健康度始终为 1.0 |
| 7 | 禁用开关 | `config.enabled = False` 时所有方法返回安全默认值 |
| 8 | 验证脚本 | `verify_s3_3.py` 全部通过 |
| 9 | 历史测试兼容 | 所有已有验证脚本通过 |

## 八、关键约束

- 不改动 GenericAgent 核心文件
- 不直接修改 GA 的 L1 索引文件（`global_mem_insight.txt`）
- 归档操作仅修改 SkillRegistry 中的元数据，不物理删除 SOP 文件
- 白名单至少包含 `memory_management_sop`
- 与 SkillRegistry 的对接通过构造函数传入实例