# S3-5: RootAuditor（归根审计）执行规格

> **版本**：v1.0.0
> **日期**：2026-05-03
> **状态**：待执行
> **依赖**：S3-1、S3-2、S3-3 已完成
> **设计依据**：《慧惠五行流转引擎-方案设计书 v1.0》第六·4节


## 一、任务信息

| 属性 | 值 |
|:---|:---|
| 任务编号 | S3-5 |
| 任务名称 | RootAuditor 归根审计——五行流转总调度 + GA集成 |
| 优先级 | P0 |
| 预估工作量 | 2天 |
| 依赖 | S3-1、S3-2、S3-3 均已完成 |

## 二、任务背景与设计理念

### 2.1 要解决的真实问题

S3-1、S3-2、S3-3 已将“木·生”和“金·克”的能力就位，但它们是**独立的静态模块**，缺少一个将它们串联起来的调度器。技能的生命周期应该是自动流转的，而非等待人工逐个调用。

### 2.2 核心设计理念：静为躁君

RootAuditor 是五行流转的“总调度”——它静默地在后台运行，周期性地触发木·生和金·克的审计动作，让技能生态自己维持健康平衡。**用户无感，技能自衡。**

### 2.3 本阶段集成范围

这是 Sprint 3 的关键集成点。RootAuditor 实现后，五行引擎将首次具备自动调度能力：

| 五行 | 对应模块 | 本阶段集成方式 |
|:---|:---|:---|
| **木·生** | `WoodGrower` | Agent Loop 结束时自动判断并注入蒸馏指令 |
| **金·克** | `MetalRestrainer` | 每日审计时自动评估并归档低健康度技能 |
| **火·化** | `FireTransformer` | 预留接口，第二期实现 |
| **水·变** | `WaterAdapter`（占位） | 占位模块，不执行实际操作 |
| **土·通** | `EarthConnector`（占位） | 占位模块，不执行实际操作 |


## 三、当前代码状态

| 模块 | 状态 | 可用接口 |
|:---|:---|:---|
| `skills/skill_registry.py` | ✅ | `SkillRegistry` 全部 CRUD + 版本管理 |
| `skills/wood_grower.py` | ✅ | `WoodGrower` 硬触发 + 硬校验 |
| `skills/metal_restrainer.py` | ✅ | `MetalRestrainer` 健康度评估 + 归档 |
| `agent_loop.py` | ✅ | Agent Loop 退出点（模型无工具调用时 break） |
| `launch_huihui.pyw` | ✅ | 慧惠启动入口 |

## 四、操作文件

| 文件 | 操作 | 说明 |
|:---|:---|:---|
| `skills/root_auditor.py` | **新建** | RootAuditor 核心实现（调度器 + 审计逻辑） |
| `skills/water_adapter.py` | **新建** | 水·变占位模块 |
| `skills/earth_connector.py` | **新建** | 土·通占位模块 |
| `launch_huihui.pyw` | **修改** | 增加五行引擎初始化 + 审计触发器 |
| `skills/verify_s3_5.py` | **新建** | S3-5 专项验证脚本 |

**不修改 GenericAgent 核心文件**。`agent_loop.py` 在当前阶段暂不修改，集成到 `launch_huihui.pyw` 中通过审计触发器实现。若后续需要更紧密的 Agent Loop 集成（如在每轮对话后自动触发木·生），可在第二期通过钩子方式实现。

## 五、RootAuditor 完整设计

### 5.1 核心类与公开方法

```python
class RootAuditor:
    """
    归根·审计：五行流转总调度器。
    
    职责：
    - 管理所有五行模块的生命周期
    - 按周期自动触发审计动作
    - 生成审计报告
    - 静默执行，不阻塞用户对话
    
    设计原则：
    - "静为躁君"：在后台安静地维护技能生态健康
    - "动善时"：按周期触发，不频繁打扰
    """
    
    def __init__(self, registry: SkillRegistry,
                 wood_grower: WoodGrower = None,
                 metal_restrainer: MetalRestrainer = None,
                 fire_transformer=None,
                 water_adapter=None,
                 earth_connector=None):
        """
        初始化五行引擎总调度器。
        
        wood_grower 和 metal_restrainer 若不传，将使用默认配置创建。
        fire_transformer、water_adapter、earth_connector 暂时传入 None（占位）。
        """
        ...
    
    def audit(self, period: str = "manual") -> AuditReport:
        """
        执行一轮审计。
        
        period 参数：
          - "manual"：手动触发，执行全部审计动作
          - "daily"：每日审计，仅执行金·克评估
          - "weekly"：每周审计，执行金·克评估 + 产物质量抽检
          - "monthly"：每月审计，执行全五行流转 + 健康度趋势分析
        
        返回：AuditReport 包含本轮审计的全部动作摘要。
        """
        ...
    
    def get_last_audit_time(self) -> Optional[str]:
        """返回上次审计的 ISO 8601 时间戳，从未审计则返回 None。"""
        ...
    
    def get_audit_history(self, limit: int = 10) -> list[dict]:
        """返回最近 N 次审计记录的摘要列表。"""
        ...
```

### 5.2 审计调度逻辑

```python
def audit(self, period: str = "manual") -> AuditReport:
    actions = []
    warnings = []
    
    if period in ("daily", "weekly", "monthly", "manual"):
        # === 金·克：评估所有活跃技能的健康度 ===
        reports = self.metal_restrainer.evaluate_all()
        for r in reports:
            if r.recommendation == "archive":
                self.metal_restrainer.archive(r.skill_id)
                actions.append({
                    "type": "archive",
                    "skill_id": r.skill_id,
                    "health": round(r.health_score, 2),
                    "reason": r.reason
                })
            elif r.recommendation == "warn":
                warnings.append({
                    "type": "low_health",
                    "skill_id": r.skill_id,
                    "health": round(r.health_score, 2)
                })
    
    if period in ("weekly", "monthly", "manual"):
        # === 产物质量抽检：随机选 20% 的活跃 SOP 做 post_validate ===
        if self.wood_grower:
            active_skills = self.registry.get_active_skills()
            sample_size = max(1, len(active_skills) // 5)
            sampled = random.sample(active_skills, min(sample_size, len(active_skills)))
            for skill in sampled:
                result = self.wood_grower.post_validate(skill.file)
                if not result.passed:
                    warnings.append({
                        "type": "quality_issue",
                        "skill_id": skill.name,
                        "detail": str(result.violations)
                    })
    
    if period in ("monthly", "manual"):
        # === 健康度趋势分析 ===
        # 记录当前健康度分布：活跃技能数、平均健康度、低健康度技能数
        ...
    
    return AuditReport(
        period=period,
        timestamp=datetime.now(timezone.utc).isoformat(),
        actions=actions,
        warnings=warnings,
        active_count=len(self.registry.get_active_skills()),
        archived_count=len(self.metal_restrainer.get_archived_skills())
    )
```

### 5.3 审计报告数据结构

```python
@dataclass
class AuditReport:
    period: str                         # "manual" / "daily" / "weekly" / "monthly"
    timestamp: str                      # ISO 8601
    actions: list[dict]                 # 已执行的归档等动作
    warnings: list[dict]                # 发现的警告（低健康度、质量问题等）
    active_count: int                   # 当前活跃技能数
    archived_count: int                 # 当前已归档技能数
```

### 5.4 审计触发机制（集成到 launch_huihui.pyw）

在 `launch_huihui.pyw` 中增加以下逻辑：

1. **启动时初始化五行引擎**：
   ```python
   from skills.skill_registry import SkillRegistry
   from skills.wood_grower import WoodGrower
   from skills.metal_restrainer import MetalRestrainer
   from skills.root_auditor import RootAuditor
   
   registry = SkillRegistry()
   wood_grower = WoodGrower(registry)
   metal_restrainer = MetalRestrainer(registry)
   root_auditor = RootAuditor(registry, wood_grower, metal_restrainer)
   ```

2. **启动时检查是否需要审计**：
   - 读取上次审计时间（存储在 `memory/last_audit.txt`）
   - 若距上次审计超过 24 小时，触发 `audit(period="daily")`
   - 若距上次审计超过 7 天，触发 `audit(period="weekly")`

3. **审计后更新审计时间**，写入 `memory/last_audit.txt`

4. **Gemini 循环中集成木·生**：
   - 在慧惠的对话循环中，每次 Agent 完成任务后调用 `wood_grower.should_trigger_distill()`
   - 若返回 True，将 `wood_grower.build_distill_prompt()` 追加到消息队列

### 5.5 占位模块设计

```python
# skills/water_adapter.py
class WaterAdapter:
    """水·变——技能更新（占位模块，第二期实现）"""
    def __init__(self, registry=None):
        self.registry = registry
    def check_and_update(self, skill_id: str) -> dict:
        return {"status": "placeholder", "message": "第二期实现"}

# skills/earth_connector.py
class EarthConnector:
    """土·通——技能迁移（占位模块，第三期实现）"""
    def __init__(self, registry=None):
        self.registry = registry
    def check_compatibility(self, skill_id: str, target_env: dict) -> dict:
        return {"status": "placeholder", "message": "第三期实现"}
```

## 六、验证脚本

`skills/verify_s3_5.py` 需覆盖：

### 调度器基本功能
1. RootAuditor 初始化成功，所有模块注入正确
2. `audit(period="daily")` 返回有效 AuditReport
3. `audit(period="weekly")` 包含质量抽检动作
4. `audit(period="manual")` 执行全部审计动作

### 金·克集成
5. 审计时低健康度技能被自动归档
6. 审计报告中的 actions 包含已归档技能的信息
7. 审计报告中的 warnings 包含低健康度但未达归档阈值的技能

### 白名单保护
8. 白名单技能在审计中不被归档

### 状态持久化
9. `get_last_audit_time()` 初始返回 None
10. 审计后 `get_last_audit_time()` 返回有效时间戳
11. 审计历史记录正确（`get_audit_history()`）

### 占位模块
12. `WaterAdapter` 导入成功，方法返回占位信息
13. `EarthConnector` 导入成功，方法返回占位信息

### 禁用开关
14. 任一模块的 `enabled = False` 时，审计跳过该模块

## 七、验收标准

| # | 验收项 | 判定标准 |
|:---|:---|:---|
| 1 | 文件创建 | `skills/root_auditor.py`、`skills/water_adapter.py`、`skills/earth_connector.py` 存在 |
| 2 | 审计调度 | `audit()` 按 period 参数执行对应的审计动作 |
| 3 | 金·克集成 | 低健康度技能在审计时被自动归档，报告含详情 |
| 4 | 白名单保护 | 白名单技能在审计中不被归档 |
| 5 | 占位模块 | WaterAdapter 和 EarthConnector 可导入，方法不抛异常 |
| 6 | 审计历史 | `get_last_audit_time()` 和 `get_audit_history()` 正常工作 |
| 7 | launch_huihui.pyw 集成 | 启动时五行引擎初始化，审计检查逻辑正常 |
| 8 | 验证脚本 | `verify_s3_5.py` 全部通过 |
| 9 | 历史测试兼容 | 所有已有验证脚本通过 |
| 10 | 零侵入 | 不改动 GenericAgent 核心文件 |

## 八、关键约束

- 不改动 GenericAgent 核心文件（`agentmain.py`, `agent_loop.py`, `ga.py`）
- 审计过程不阻塞用户对话（异步或在后台线程执行）
- 审计报告存储为本地 JSON（`memory/audit_log.json`）
- 占位模块不执行任何实际操作，仅提供接口骨架
- 白名单至少包含 `memory_management_sop`