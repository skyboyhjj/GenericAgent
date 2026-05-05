# S2-2: XiMingPipeline 蒸馏管道执行规格（Qoder-ready）

> **版本**：v1.0.0  
> **日期**：2026-05-03  
> **状态**：待执行  
> **依赖**：S2-1 系列全部完成  

---

## 一、任务信息

| 属性 | 值 |
|:---|:---|
| 任务编号 | S2-2 |
| 任务名称 | 实现 XiMingPipeline 蒸馏管道 |
| 优先级 | P0 |
| 预估工作量 | 2天 |
| 依赖 | S2-1 系列已完成 |

## 二、任务目标

实现慧惠的记忆蒸馏管道，将从道境感知网关接收的原始修行数据，逐层提炼为慧惠可用的洞察与记忆。管道遵循“为道日损”原则——从繁多的原始记录中层层蒸馏出最核心的成长脉络。

## 三、当前代码状态

| 模块 | 状态 | 可复用接口 |
|:---|:---|:---|
| `memory/gateway/dao_gateway.py` | ✅ | `DaoGateway.sync_all()` 返回 `List[SyncResult]` |
| `memory/gateway/adapters/ximing_adapter.py` | ✅ | `SyncResult.data` 含 `NormalizedDailyData` 列表 |
| `memory/gateway/formula_registry.py` | ✅ | `verify_p_score()`, `get_formula()`, `check_compatibility()` |
| `memory/fusion/fusion_engine.py` | ✅ | `DataFusionEngine.fuse()` → `MultiModalEventStream` |

## 四、操作文件

| 文件 | 操作 | 说明 |
|:---|:---|:---|
| `memory/ximing_pipeline.py` | **新建** | 蒸馏管道核心实现 |
| `memory/memory_core.py` | **新建** | 五层记忆系统骨架（L4/L3/L2/L1） |
| `memory/verify_s2_2.py` | **新建** | 蒸馏管道专项验证脚本 |

**不修改已有文件。**

## 五、蒸馏管道架构

```
MultiModalEventStream (来自 DaoGateway)
    ↓
┌───────────────────────────────────────┐
│          XiMingPipeline               │
│                                       │
│  process_daily(daily_data)            │
│       │                               │
│       ├── L4Archiver.archive()        │ → 全量向量化存档
│       │                               │
│       ├── L3PatternRecognizer.recognize() │ → 周期性/趋势/关联模式
│       │                               │
│       ├── L2MetricCalculator.calculate() │ → 核心指标 + 阴阳画像
│       │                               │
│       └── L1InsightGenerator.generate() │ → 每日/每周摘要
│                                       │
└───────────────────────────────────────┘
    ↓
输出：DailyInsight → 供 AgentLoop 使用
```

## 六、各层实现要求

### 6.1 L4 原始归档层 (L4Archiver)

```python
class L4Archiver:
    """原始归档层——无损存储，向量化索引"""
    
    def __init__(self, archive_path: str = "./memory/l4_archive"):
        self.archive_path = archive_path
    
    async def archive_daily(self, daily_data: NormalizedDailyData) -> str:
        """
        以日为单位归档原始数据。
        返回归档文档的唯一标识符。
        """
        ...
    
    async def archive_stream(self, stream: MultiModalEventStream) -> List[str]:
        """归档多模态事件流中的所有事件"""
        ...
    
    def search(self, query: str, top_k: int = 5) -> List[dict]:
        """向量相似度检索"""
        ...
```

**实现要点**：
- 对事件描述进行向量化（使用简单的TF-IDF或本地轻量模型，避免引入重型依赖）
- 以JSON文件形式按日期存储（`l4_archive/YYYY-MM-DD.json`）
- 检索结果按相似度降序排列

### 6.2 L3 模式识别层 (L3PatternRecognizer)

```python
@dataclass
class RecognizedPattern:
    """识别出的模式"""
    type: str          # "cyclic" / "trend" / "correlation"
    description: str
    confidence: float  # 0.0 - 1.0
    evidence: list     # 支持此模式的事件ID列表

class L3PatternRecognizer:
    """模式识别层——从历史数据中发现规律"""
    
    def __init__(self, formula_registry=None):
        self.formula_registry = formula_registry
    
    def recognize(self, events: List[NormalizedEvent]) -> List[RecognizedPattern]:
        """
        从事件列表中识别模式。
        返回识别出的所有模式（按置信度降序）。
        """
        patterns = []
        
        # 1. 周期性模式（如每周末能量层级偏高）
        cyclic = self._detect_cyclic(events)
        patterns.extend(cyclic)
        
        # 2. 趋势模式（如识位分数连续上升）
        trends = self._detect_trend(events)
        patterns.extend(trends)
        
        # 3. 关联模式（如亲密关系事件能量层级高于均值）
        correlations = self._detect_correlation(events)
        patterns.extend(correlations)
        
        return sorted(patterns, key=lambda p: p.confidence, reverse=True)
    
    def _detect_cyclic(self, events) -> List[RecognizedPattern]:
        """检测周期性模式（按星期几分组比较能量均值）"""
        ...
    
    def _detect_trend(self, events) -> List[RecognizedPattern]:
        """检测趋势模式（连续N天上升/下降）"""
        ...
    
    def _detect_correlation(self, events) -> List[RecognizedPattern]:
        """检测关联模式（事件描述关键词与能量层级的关系）"""
        ...
```

**实现要点**：
- `_detect_cyclic`：按星期几分组，比较各组P忠恕均值差异，差异>1.0则报告模式
- `_detect_trend`：连续3天以上同方向变化，报告为趋势
- `_detect_correlation`：提取事件描述中的关键词（如“争执”、“共情”），分析与能量层级的关系
- 置信度计算：基于样本量和差异显著度

### 6.3 L2 指标计算层 (L2MetricCalculator)

```python
@dataclass
class L2Metrics:
    """L2层核心修行指标"""
    total_days: int = 0              # 修行天数
    total_events: int = 0            # 总事件数
    avg_energy_score: float = 0.0   # 平均P忠恕分
    consecutive_days: int = 0        # 连续修行天数
    dimension_balance: dict = None   # 四维均分 {temporal, spatial, wisdom, causality}
    energy_distribution: dict = None # 能量层级分布 {层级名: 次数}
    portrait_yang: str = ""          # 阳的形态：行者型/悟者型/习者型
    portrait_yin: str = ""           # 阴的质地：清明之境/砥砺之境/蓄养之境
    portrait_combined: str = ""      # 综合画像：如"笃行的清明者"

class L2MetricCalculator:
    """指标计算层——生成修行画像与核心指标"""
    
    def calculate(self, events: List[NormalizedEvent]) -> L2Metrics:
        """从事件列表计算核心指标与阴阳画像"""
        ...
    
    def _calc_yang_type(self, events) -> str:
        """计算阳气形态：行者型/悟者型/习者型"""
        ...
    
    def _calc_yin_state(self, events) -> str:
        """计算阴气质地：清明之境/砥砺之境/蓄养之境"""
        ...
```

**阴阳画像判定规则**：

| 阳气形态 | 判定标准 |
|:---|:---|
| 行者型 | 连续修行天数 ≥ 7，事件记录规律（间隔方差小） |
| 悟者型 | 平均P忠恕分 ≥ 7.5，但记录频率较低 |
| 习者型 | 各项指标均衡发展，稳步积累 |

| 阴气质地 | 判定标准 |
|:---|:---|
| 清明之境 | P忠恕标准差 < 1.0，四维平衡度 > 0.7 |
| 砥砺之境 | P忠恕标准差 ≥ 1.5，某维度明显为短板 |
| 蓄养之境 | P忠恕标准差在 [1.0, 1.5) 之间，逐步积累 |

**综合画像** = 阳气形态 + 阴气质地，共9种组合。如“行者型”+“清明之境”=“笃行的清明者”。

**动态平衡诊断**：

| 状态 | 判定 |
|:---|:---|
| 阳盛阴清 | 记录频率高（日均≥3件）+ P忠恕标准差<1.0 |
| 阳亢阴浊 | 记录频率高 + P忠恕标准差≥1.5 |
| 阳弱阴凝 | 记录频率低（日均≤1件）+ P忠恕均值较高 |
| 阳散阴晦 | 记录频率低 + P忠恕均值<5.0 |

### 6.4 L1 洞察生成层 (L1InsightGenerator)

```python
@dataclass
class DailyInsight:
    """每日修行洞察"""
    date: str
    energy_curve: str         # 今日能量变化描述（上升/平稳/下降）
    highlight_events: list    # 关键事件（能量显著偏离基线）
    alignment_score: float    # 意图-事件-反思一致度 (0-1)
    suggestion: str           # 慧惠的关怀建议（≤100 tokens）

class L1InsightGenerator:
    """洞察生成层——生成每日/每周摘要"""
    
    def generate_daily(self, daily_data: NormalizedDailyData, 
                       l2_metrics: L2Metrics) -> DailyInsight:
        """
        基于今日数据和L2指标，生成每日洞察。
        suggestion 长度 ≤100 tokens。
        """
        ...
    
    def generate_weekly(self, recent_daily_insights: List[DailyInsight],
                        l2_metrics: L2Metrics) -> str:
        """基于最近7天的洞察和L2指标，生成每周成长报告"""
        ...
    
    def _identify_key_events(self, events, baseline_score) -> list:
        """识别能量显著偏离基线（≥1.5分）的关键事件"""
        ...
    
    def _analyze_alignment(self, morning_intent, events, evening_reflection) -> float:
        """分析晨间定志、日间事件、晚间回顾之间的关联度"""
        ...
```

**实现要点**：
- 关键事件识别：P忠恕分与L2均分差异≥1.5分的事件
- 意图-事件-反思一致度：简单的关键词重叠率计算
- 建议生成：基于诊断结果映射到预设模板（如“阳亢阴浊” → 引导减少形式化记录）
- 每周报告：汇总7日的关键趋势

## 七、管道集成

`XiMingPipeline` 作为顶层调度器：

```python
class XiMingPipeline:
    """慧惠记忆蒸馏管道——为道日损"""
    
    def __init__(self):
        self.l4_archiver = L4Archiver()
        self.l3_recognizer = L3PatternRecognizer()
        self.l2_calculator = L2MetricCalculator()
        self.l1_generator = L1InsightGenerator()
    
    async def process_daily(self, daily_data: NormalizedDailyData) -> DailyInsight:
        """处理单日数据：L4归档 → L3模式识别 → L2指标更新 → L1洞察生成"""
        ...
    
    async def process_history(self, history: List[NormalizedDailyData]) -> L2Metrics:
        """处理全量历史数据，返回完整L2指标（用于首次同步后的初始化）"""
        ...
    
    async def process_stream(self, stream: MultiModalEventStream) -> DailyInsight:
        """处理融合后的多模态事件流"""
        ...
```

## 八、与已有模块的集成点

1.  **与 XiMingAdapter 的集成**：`XiMingAdapter.sync_history()` 和 `sync_today()` 返回的 `SyncResult.data` 直接传入 `process_daily()` 或 `process_history()`
2.  **与 formula_registry 的集成**：L3 模式识别时，当事件 `algorithm_version` 不一致时，使用 `check_compatibility()` 判断是否可比较
3.  **与 MemoryCore 的对接**（S2-3 实现）：管道输出的 `DailyInsight` 和 `L2Metrics` 将写入五层记忆系统，供 AgentLoop 检索

## 九、验证脚本

`memory/verify_s2_2.py` 需覆盖：

1. L4 归档功能正常（JSON文件写入 + 读取 + 检索）
2. L3 周期性模式识别正确
3. L3 趋势模式识别正确（连续上升/下降）
4. L3 关联模式识别正确
5. L2 核心指标计算正确（修行天数、均分、连续天数）
6. L2 阴阳画像生成正确（9种类型之一）
7. L2 动态平衡诊断正确
8. L1 每日洞察生成，suggestion ≤100 tokens
9. L1 关键事件识别正确
10. 管道处理全量历史数据正常
11. 管道处理单日数据正常

## 十、验收标准

| # | 验收项 | 判定标准 |
|:---|:---|:---|
| 1 | 文件创建 | `memory/ximing_pipeline.py` 和 `memory/memory_core.py` 存在 |
| 2 | L4 归档 | JSON 文件按时序存储，向量检索返回正确结果 |
| 3 | L3 模式识别 | 至少输出 1 种模式类型，置信度可计算 |
| 4 | L2 阴阳画像 | 可正确生成9种类型之一 |
| 5 | L2 动态平衡诊断 | 四种阴阳状态可正确判定 |
| 6 | L1 每日洞察 | `suggestion` 长度 ≤100 tokens |
| 7 | 管道集成 | `process_daily()` 和 `process_history()` 正常执行 |
| 8 | 验证脚本 | `verify_s2_2.py` 全部通过 |
| 9 | 历史测试兼容 | 所有已有验证脚本通过 |
| 10 | 零修改 | 不改动任何 S2-1 系列文件 |

## 十一、关键约束

- 不改动 GenericAgent 核心文件
- 不改动任何 S2-1 系列已有文件
- L4 归档使用纯 JSON 文件，不引入重型向量数据库依赖
- 所有计算使用 `formula_registry` 中的权重，确保算法版本一致性
- Token 预算：L1 suggestion ≤100 tokens

---

*规格结束。请以本文档为唯一执行依据。规格书中代码示例为设计意图参考，请在理解后适配实现，保持接口契约不变。*