# S2-1-REFACTOR: 道境感知网关架构升级

> **版本**：v1.0.0  
> **日期**：2026-05-03  
> **状态**：待执行  
> **依赖**：S2-1 和 S2-1_modify01 均已完成

---

## 一、任务信息

| 属性 | 值 |
|:---|:---|
| 任务编号 | S2-1-REFACTOR |
| 任务名称 | 道境感知网关架构升级——抽象接口 + 总调度器 |
| 优先级 | P0 |
| 预估工作量 | 1天 |
| 依赖 | S2-1 和 S2-1_modify01 已完成 |

## 二、任务背景

当前 `XiMingAdapter` 已具备完整的数据同步与算法版本控制能力。根据《道境感知网关技术架构设计》，需要将其升级为可插拔的多模态感知系统，为未来接入可穿戴设备、VR/AR、IoT传感器等预留统一接口。

## 三、当前代码状态

| 文件 | 状态 | 说明 |
|:---|:---|:---|
| `memory/gateway/__init__.py` | ✅ | 包标记 |
| `memory/gateway/adapters/__init__.py` | ✅ | 包标记 |
| `memory/gateway/adapters/ximing_adapter.py` | ✅ | XiMingAdapter 完整实现，含 `algorithm_version` |
| `memory/gateway/formula_registry.py` | ✅ | 公式注册表 + 反推验证 |
| `memory/__init__.py` | ✅ | 包标记 |
| `memory/ximing_client.py` | ✅ | 兼容层 |
| `memory/verify_s2_1.py` | ✅ | 17项测试全部通过 |
| `memory/verify_s2_1_modify01.py` | ✅ | 11项测试全部通过 |

## 四、操作文件

| 文件 | 操作 | 说明 |
|:---|:---|:---|
| `memory/gateway/perception_source.py` | **新建** | 抽象接口 + 公共数据结构 + 枚举 |
| `memory/gateway/dao_gateway.py` | **新建** | DaoGateway 总调度器 |
| `memory/gateway/sync_policy.py` | **新建** | 同步策略管理器 |
| `memory/gateway/health_monitor.py` | **新建** | 感知源健康监控器 |
| `memory/fusion/__init__.py` | **新建** | 融合层包标记 |
| `memory/fusion/fusion_engine.py` | **新建** | DataFusionEngine + MultiModalEvent |
| `memory/gateway/adapters/ximing_adapter.py` | **修改** | 继承 PerceptionSource，增加两个方法 |
| `memory/verify_s2_1_refactor.py` | **新建** | 重构专项验证脚本 |

## 五、实现要求

### 5.1 新建 `perception_source.py` —— 抽象接口层

```python
from abc import ABC, abstractmethod
from enum import Enum
from dataclasses import dataclass, field
from typing import List, Dict, Any

class SyncMode(Enum):
    FULL = "full"
    INCREMENTAL = "incremental"
    RESYNC = "resync"

class SourceType(Enum):
    DAO_MING = "dao_ming"
    WEARABLE = "wearable"
    VR_AR = "vr_ar"
    IOT = "iot"
    BCI = "bci"

@dataclass
class ConnectivityStatus:
    reachable: bool
    latency_ms: float
    error_message: str = ""

@dataclass
class SyncResult:
    success: bool
    source_type: str = ""
    data: List[Any] = field(default_factory=list)
    error_message: str = ""
    synced_at: str = ""
    data_date: str = ""
    algorithm_version: str = ""

class PerceptionSource(ABC):
    @abstractmethod
    async def check_connectivity(self) -> ConnectivityStatus:
        ...
    
    @abstractmethod
    async def sync(self, mode: SyncMode) -> SyncResult:
        ...
    
    @abstractmethod
    def get_source_type(self) -> SourceType:
        ...
    
    @abstractmethod
    def get_data_schema(self) -> dict:
        ...
```

### 5.2 修改 `ximing_adapter.py` —— 仅三点改动

不改动 XiMingAdapter 的任何内部业务逻辑。仅：

1. 从 `perception_source` 导入基类和枚举
2. 类定义改为 `class XiMingAdapter(PerceptionSource):`
3. 新增两个方法：
   ```python
   def get_source_type(self) -> SourceType:
       return SourceType.DAO_MING
   
   def get_data_schema(self) -> dict:
       return {
           "dimensions": ["temporal", "spatial", "wisdom", "causality"],
           "metrics": ["p_zhongshu_score", "hawkins_level"],
           "daily_structure": ["morning_intent", "events", "evening_reflection"]
       }
   ```

### 5.3 新建 `dao_gateway.py` —— 总调度器

```python
class DaoGateway:
    def __init__(self):
        self.sources: Dict[SourceType, PerceptionSource] = {}
    
    def register_source(self, source: PerceptionSource):
        """注册感知源"""
        self.sources[source.get_source_type()] = source
    
    async def sync_all(self, mode: SyncMode = SyncMode.INCREMENTAL):
        """并发同步所有感知源，单个失败不阻塞其他"""
        ...
    
    async def _sync_with_fallback(self, source, mode):
        """先检查连通性，再同步，失败自动降级"""
        ...
```

### 5.4 新建 `fusion_engine.py` —— 数据融合层

```python
@dataclass
class MultiModalEvent:
    timestamp: datetime
    source_type: SourceType
    event_type: str
    data: dict
    normalized: dict

class MultiModalEventStream:
    def __init__(self):
        self.events: List[MultiModalEvent] = []
    ...

class DataFusionEngine:
    async def fuse(self, results: List[SyncResult]) -> MultiModalEventStream:
        """将多源数据融合为统一事件流（当前版本：时间对齐）"""
        ...
```

### 5.5 新建 `verify_s2_1_refactor.py`

验收脚本需覆盖：

1. PerceptionSource 抽象接口定义正确
2. XiMingAdapter 是 PerceptionSource 的子类
3. XiMingAdapter.get_source_type() 返回 SourceType.DAO_MING
4. XiMingAdapter.get_data_schema() 返回正确结构
5. DaoGateway 可注册感知源，sync_all() 返回有效结果
6. DataFusionEngine 可包装多源数据为 MultiModalEventStream
7. 单个感知源失败不阻塞其他源同步

## 六、关键约束

- XiMingAdapter 内部业务逻辑**零修改**
- 不改动 GenericAgent 核心文件
- 所有已有验证脚本必须全部通过：
  - `verify_s2_1.py` (17项)
  - `verify_s2_1_modify01.py` (11项)
  - `verify_soul.py`
  - `verify_s1_2.py`
  - `verify_s1_3.py`
  - `verify_s1_4.py`
  - `verify_s1_5.py`

## 七、验收标准

| # | 验收项 | 判定标准 |
|:---|:---|:---|
| 1 | 抽象接口 | `PerceptionSource` 正确定义 |
| 2 | 继承关系 | `XiMingAdapter` 继承 `PerceptionSource` |
| 3 | 类型返回 | `get_source_type()` → `SourceType.DAO_MING` |
| 4 | 数据模式 | `get_data_schema()` 返回符合规格的结构 |
| 5 | 总调度 | `DaoGateway` 可注册源并并发同步 |
| 6 | 数据融合 | `DataFusionEngine` 输出 `MultiModalEventStream` |
| 7 | 降级处理 | 单源失败不阻塞其他源 |
| 8 | 新测试 | `verify_s2_1_refactor.py` 全部通过 |
| 9 | 历史测试 | 全部已有验证脚本通过 |
| 10 | 零修改 | `XiMingAdapter` 内部代码零修改 |

## 八、关于规格书中代码示例的重要说明
规格书中的Python代码片段（如PerceptionSource抽象基类、DaoGateway类、DataFusionEngine类等），并非要求你逐字复制。它们是用于说明设计意图、接口契约和数据结构的参考框架。

请在理解这些设计意图后，遵循以下原则进行实现：

适配而非复制：你需要基于项目现有的代码风格、导入路径和模块结构，进行适配性实现。如果规格书中的代码与项目实际上下文不完全一致，以项目上下文为准，但保持接口契约不变。

保证可运行：所有新建模块必须与已有的XiMingAdapter、formula_registry.py、verify_s2_1.py等文件兼容，确保所有已有验证脚本无需修改即可通过。

接口优先：规格书中定义的类名、方法名、方法签名是不可更改的接口契约（如PerceptionSource必须包含check_connectivity、sync、get_source_type、get_data_schema四个抽象方法）。实现细节可以灵活处理，但这些接口必须严格一致。

如有冲突请提出：如果你在实现过程中发现规格书的设计与现有代码存在不可调和的冲突，或者有更优的实现方案，请在开始编码前提出疑问，而不是采用会让已有测试失败的方案。

---

*规格结束。请以本文档为唯一执行依据。*