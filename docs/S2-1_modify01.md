# S2-1: XiMingClient 执行规格（Qoder-ready）

> **版本**：v1.1.0  
> **日期**：2026-05-03  
> **状态**：待执行  
> **依赖**：Sprint 1 已完成


## 一、任务信息

| 属性 | 值 |
|:---|:---|
| 任务编号 | S2-1 |
| 任务名称 | 实现 XiMingAdapter 数据同步客户端 |
| 优先级 | P0 |
| 预估工作量 | 2天 |
| 依赖 | 无 |

## 二、任务目标

实现慧惠与“袭明每日镜鉴”小程序的本地数据同步客户端。将同步模块直接部署在最终目录 `memory/gateway/adapters/` 下，为后续重构为道境感知网关做好准备。数据结构需包含算法版本控制，支持未来P忠恕公式演进而无需迁移历史数据。

## 三、操作文件

| 文件 | 操作 | 说明 |
|:---|:---|:---|
| `memory/gateway/__init__.py` | 新建 | 空文件，标识为 Python 包 |
| `memory/gateway/adapters/__init__.py` | 新建 | 空文件，标识为 Python 包 |
| `memory/gateway/adapters/ximing_adapter.py` | 新建 | 核心实现：`XiMingAdapter` 类 |
| `memory/ximing_client.py` | 新建 | 兼容层：`from memory.gateway.adapters.ximing_adapter import XiMingAdapter as XiMingClient` |
| `memory/verify_s2_1.py` | 新建 | 验证脚本 |

## 四、API 接口契约

### 4.1 小程序侧

**基地址**：`http://127.0.0.1:9876/api/v1`

| 端点 | 方法 | 说明 |
|:---|:---|:---|
| `/api/v1/history` | GET | 拉取全部历史修行数据 |
| `/api/v1/today` | GET | 拉取今日修行数据 |

### 4.2 响应数据结构（小程序侧返回）

```json
{
  "date": "2026-04-29",
  "algorithm_version": "1.0.0",
  "morning_intent": "今日重点关注缘位轴",
  "events": [
    {
      "event_id": "evt_001",
      "timestamp": "2026-04-29T10:30:00",
      "description": "与同事发生争执后主动道歉",
      "dimension_scores": {
        "temporal": 7,
        "spatial": 6,
        "wisdom": 8,
        "causality": 9
      },
      "p_zhongshu_score": 7.7,
      "hawkins_level": "接纳"
    }
  ],
  "evening_reflection": "今天在缘位上有所突破"
}
```

## 五、数据结构（慧惠侧标准化格式）

### 5.1 NormalizedEvent

```python
@dataclass
class NormalizedEvent:
    event_id: str
    timestamp: str
    description: str
    dimension_scores: Dict[str, int]       # {temporal, spatial, wisdom, causality}
    p_zhongshu_score: float
    hawkins_level: str
    algorithm_version: str = "1.0.0"       # 记录计算此事件时的P忠恕算法版本
```

**关键设计**：`algorithm_version` 字段记录计算此事件时的P忠恕算法版本。慧惠侧维护一个公式注册表，当需要比较跨版本事件时，可通过 `dimension_scores` 和注册表中的权重反推验证一致性，无需在每条数据中冗余存储公式快照。

### 5.2 NormalizedDailyData

```python
@dataclass
class NormalizedDailyData:
    date: str
    algorithm_version: str                  # 当日使用的P忠恕算法版本
    morning_intent: Optional[str]
    events: List[NormalizedEvent]
    evening_reflection: Optional[str]
```

### 5.3 SyncResult

```python
@dataclass
class SyncResult:
    success: bool
    data: List[NormalizedDailyData]
    error_message: str = ""
    sync_type: str = ""                     # "history" 或 "today"
    synced_at: str = ""                     # ISO 8601
    data_date: str = ""                     # 数据日期
    algorithm_version: str = ""             # 数据所用算法版本
```

### 5.4 ConnectivityStatus

```python
@dataclass
class ConnectivityStatus:
    reachable: bool
    latency_ms: float
    error_message: str = ""
```

## 六、XiMingAdapter 类

```python
class XiMingAdapter:
    """袭明每日镜鉴数据同步适配器"""
    
    BASE_URL = "http://127.0.0.1:9876/api/v1"
    TIMEOUT = 5
    MAX_RETRIES = 3
    
    def __init__(self, base_url: str = None, timeout: int = None):
        ...
    
    async def check_connectivity(self) -> ConnectivityStatus:
        """检测小程序 HTTP 服务是否可达"""
        ...
    
    async def sync_history(self) -> SyncResult:
        """GET /api/v1/history，拉取全部历史数据"""
        ...
    
    async def sync_today(self) -> SyncResult:
        """GET /api/v1/today，拉取今日数据"""
        ...
    
    def _normalize_response(self, raw: dict) -> NormalizedDailyData:
        """将小程序原始响应标准化为慧惠侧格式，保留 algorithm_version"""
        ...
    
    def _should_retry(self, status_code: int) -> bool:
        """判断是否需要指数退避重试"""
        ...
```

## 七、错误处理规范

| 场景 | 行为 | 用户感知 |
|:---|:---|:---|
| 连接超时（5s） | 返回 `success=False`，不抛出异常 | 无感 |
| 4xx 错误（如 404） | 记录日志，返回空数据 | 无感 |
| 5xx 错误 | 指数退避重试（1s→2s→4s），最多3次 | 无感 |
| 响应格式错误 | 返回 `success=False`，记录解析错误日志 | 无感 |
| 小程序未启动 | `check_connectivity()` 返回 `reachable=False` | 无感 |

## 八、验证脚本

```python
"""S2-1 验证脚本 — XiMingAdapter 数据同步客户端"""

async def main():
    adapter = XiMingAdapter()
    
    # 测试 1: 连通性检测（服务可达）
    status = await adapter.check_connectivity()
    assert isinstance(status, ConnectivityStatus)
    print(f"[PASS] 1. check_connectivity() 返回 ConnectivityStatus")
    
    # 测试 2: 连通性检测（服务不可达时的降级行为）
    adapter_unreachable = XiMingAdapter(base_url="http://127.0.0.1:19999")
    status = await adapter_unreachable.check_connectivity()
    assert status.reachable == False
    print(f"[PASS] 2. 服务不可达时 reachable=False，不抛异常")
    
    # 测试 3: 数据格式标准化
    raw = { ... }  # 模拟小程序返回的原始数据
    normalized = adapter._normalize_response(raw)
    assert isinstance(normalized, NormalizedDailyData)
    assert normalized.date == "2026-04-29"
    assert normalized.algorithm_version == "1.0.0"
    print(f"[PASS] 3. _normalize_response() 正确标准化数据，保留 algorithm_version")
    
    # 测试 4: 指数退避逻辑
    assert adapter._should_retry(429) == True
    assert adapter._should_retry(500) == True
    assert adapter._should_retry(503) == True
    assert adapter._should_retry(400) == False
    assert adapter._should_retry(404) == False
    print(f"[PASS] 4. 重试逻辑正确")
    
    # 测试 5: SyncResult 数据结构
    result = SyncResult(success=True, sync_type="history", data_date="2026-04-29", algorithm_version="1.0.0")
    assert result.success == True
    assert result.sync_type == "history"
    assert result.algorithm_version == "1.0.0"
    print(f"[PASS] 5. SyncResult 数据结构正确，含 algorithm_version")
    
    # 测试 6: NormalizedEvent 含 algorithm_version
    event = NormalizedEvent(
        event_id="evt_001",
        timestamp="2026-04-29T10:30:00",
        description="测试事件",
        dimension_scores={"temporal": 7, "spatial": 6, "wisdom": 8, "causality": 9},
        p_zhongshu_score=7.7,
        hawkins_level="接纳",
        algorithm_version="1.0.0"
    )
    assert event.algorithm_version == "1.0.0"
    print(f"[PASS] 6. NormalizedEvent 含 algorithm_version 字段")
    
    print("\nS2-1 ALL TESTS PASSED")

if __name__ == "__main__":
    import asyncio
    asyncio.run(main())
```

## 九、验收标准

| # | 验收项 | 判定标准 |
|:---|:---|:---|
| 1 | 目录结构 | `memory/gateway/`、`memory/gateway/adapters/` 创建 |
| 2 | XiMingAdapter | `memory/gateway/adapters/ximing_adapter.py` 包含完整实现 |
| 3 | 兼容层 | `memory/ximing_client.py` 可正常导入 XiMingClient |
| 4 | 连通性检测 | 可达返回 True，不可达返回 False，不抛异常 |
| 5 | 数据标准化 | `_normalize_response()` 输出 `NormalizedDailyData`，保留 `algorithm_version` |
| 6 | algorithm_version | `NormalizedEvent` 和 `NormalizedDailyData` 均含此字段 |
| 7 | 错误处理 | 超时静默降级，5xx 指数退避，4xx 记录日志 |
| 8 | SyncResult 完整性 | 包含 `success`, `data`, `sync_type`, `synced_at`, `data_date`, `algorithm_version` |
| 9 | 验证脚本 | `verify_s2_1.py` 全部 6 项测试通过 |
| 10 | 历史测试兼容 | `verify_soul.py`, `verify_s1_2.py`, `verify_s1_3.py`, `verify_s1_5.py` 全部通过 |

## 十、关键约束

- 数据仅在 127.0.0.1 本地传输
- 所有同步请求标注小程序侧传入的 `algorithm_version`
- 修行数据只读，永不回写小程序
- 慧惠侧不重新计算 P忠恕分数，仅原样保留 `p_zhongshu_score` 和 `dimension_scores`
- 不改动 GenericAgent 核心文件

---

*规格结束。请以本文档为唯一执行依据。*