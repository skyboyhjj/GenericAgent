# S2-3: MemoryCore L2 层对接执行规格（Qoder-ready）

> **版本**：v1.0.0  
> **日期**：2026-05-03  
> **状态**：待执行  
> **依赖**：S2-2 已完成  

---

## 一、任务信息

| 属性 | 值 |
|:---|:---|
| 任务编号 | S2-3 |
| 任务名称 | MemoryCore L2 层对接——记忆写入与 AgentLoop 检索 |
| 优先级 | P0 |
| 预估工作量 | 2天 |
| 依赖 | S2-2 已完成 |

## 二、任务目标

将 S2-2 蒸馏管道产出的 `DailyInsight` 和 `L2Metrics` 正式写入五层记忆系统，并在 AgentLoop 中增加记忆检索与注入逻辑。完成后，慧惠能在对话中基于你的修行数据给出个性化回应。

## 三、当前代码状态

| 模块 | 状态 | 可复用接口 |
|:---|:---|:---|
| `memory/ximing_pipeline.py` | ✅ | `XiMingPipeline.process_daily()` → `DailyInsight`, `process_history()` → `L2Metrics` |
| `memory/memory_core.py` | ✅ | 骨架已有，需补全写入/检索方法 |
| `core/soul_prompts.py` | ✅ | `inject_soul_prompt(base_prompt, user_input=None)` 注入场景模板 |
| `agentmain.py` | ✅ | `get_system_prompt()` 已注入 Soul 基线 |

## 四、操作文件

| 文件 | 操作 | 说明 |
|:---|:---|:---|
| `memory/memory_core.py` | **修改** | 补全写入、检索、L1/L2 本地持久化方法 |
| `core/soul_prompts.py` | **修改** | 增加记忆上下文注入（在场景参考之后） |
| `memory/verify_s2_3.py` | **新建** | MemoryCore 对接专项验证 |

**不修改的文件**：
- `memory/ximing_pipeline.py` — 管道不变
- `agentmain.py` — 保持不变（由 soul_prompts 层间接调用）

## 五、MemoryCore 补全要求

### 5.1 数据结构

```python
@dataclass
class L1InsightEntry:
    """L1 洞察索引条目"""
    date: str
    energy_curve: str          # "上升" / "平稳" / "下降"
    highlight_summary: str     # 关键事件一句话摘要
    alignment_score: float     # 意图-事件-反思一致度
    suggestion: str            # 慧惠建议

@dataclass  
class L2PortraitSnapshot:
    """L2 修行画像快照"""
    date: str
    total_days: int
    avg_energy_score: float
    consecutive_days: int
    dimension_balance: dict    # {temporal, spatial, wisdom, causality}
    yang_type: str             # 行者型/悟者型/习者型
    yin_state: str             # 清明之境/砥砺之境/蓄养之境
    combined_portrait: str     # 综合画像
    balance_diagnosis: str     # 动态平衡诊断
```

### 5.2 写入方法

```python
class MemoryCore:
    def update_from_daily(self, insight: DailyInsight):
        """将每日洞察写入 L1 索引（保留最近30天）"""
        ...
    
    def update_from_metrics(self, metrics: L2Metrics):
        """将修行指标写入 L2 稳定知识（保留最近10个快照）"""
        ...
    
    def _prune_l1(self):
        """L1 保留最近30天，超量自动修剪最旧条目"""
        ...
    
    def _prune_l2(self):
        """L2 保留最近10个快照，超量自动修剪最旧快照"""
        ...
    
    def save_to_disk(self):
        """L1/L2 持久化到本地 JSON 文件"""
        ...
    
    def load_from_disk(self):
        """从本地 JSON 文件恢复 L1/L2"""
        ...
```

**持久化路径**：
- L1：`memory/l1_insights.json`
- L2：`memory/l2_portraits.json`

### 5.3 检索方法

```python
    def get_l1_context(self, max_tokens: int = 1000) -> str:
        """返回 L1 层修行摘要文本，供 AgentLoop 注入"""
        ...
    
    def get_l2_context(self, max_tokens: int = 500) -> str:
        """返回 L2 层画像摘要文本，供 AgentLoop 注入"""
        ...
    
    def get_relevant_context(self, user_input: str = None, 
                             max_tokens: int = 1500) -> str:
        """综合检索 L1+L2 记忆，按需返回最相关上下文"""
        ...
```

**检索优先级**：
1. L2 最新画像快照（当前修行阶段）
2. L1 最近 7 天洞察摘要（近期趋势）
3. L1 关键事件（与当前输入语义相似的事件）

### 5.4 自动修剪

- L1 保留最近 **30 天**，超量时自动删除最旧条目（“为道日损”）
- L2 保留最近 **10 个快照**，超量时自动删除最旧快照
- 修剪在 `update_*` 方法内自动触发

## 六、soul_prompts.py 修改要求

在 `inject_soul_prompt()` 中增加记忆上下文注入：

```python
def inject_soul_prompt(base_prompt: str, user_input: str = None,
                       memory_core=None) -> str:
    """
    注入层级：
    1. [系统身份设定 - 最高优先级] — Soul 基线
    2. [场景参考] — 场景模板 few-shot（如有 user_input）
    3. [对你的理解] — MemoryCore L1+L2 记忆（新增）
    4. {原始基础提示词}
    """
```

**注入格式**：
```
[对你的理解]
最近修行趋势：{L2最新画像一句话总结}
近期状态：{L1最近7天趋势描述}
当前画像：{综合画像名称}
```

**关键约束**：
- 记忆段总长度 ≤1500 tokens
- 若 `memory_core` 为 None（首次启动无数据），跳过记忆注入
- 向后兼容：不传 `memory_core` 时行为与原版完全一致

## 七、AgentLoop 集成点

在 `agentmain.py` 的 `get_system_prompt()` 调用中，将 `memory_core` 实例传入：

```python
# agentmain.py 第 69 行附近（当前实现）
# 原有：return inject_soul_prompt(prompt, user_input)
# 改为：return inject_soul_prompt(prompt, user_input, memory_core=self.memory_core)
```

**注意**：如果当前 `agentmain.py` 尚未初始化 `self.memory_core`，需在 `GeneraticAgent.__init__()` 中增加初始化：

```python
from memory.memory_core import MemoryCore

class GeneraticAgent:
    def __init__(self):
        ...
        self.memory_core = MemoryCore()
```

## 八、验证脚本

`memory/verify_s2_3.py` 需覆盖：

1. MemoryCore 初始化成功
2. L1 写入：`update_from_daily()` 正确存储 DailyInsight
3. L1 修剪：超过 30 条自动删除最旧
4. L2 写入：`update_from_metrics()` 正确存储 L2PortraitSnapshot
5. L2 修剪：超过 10 条自动删除最旧
6. L1/L2 持久化：`save_to_disk()` 写入 JSON，`load_from_disk()` 正确恢复
7. L1 检索：`get_l1_context()` 返回 ≤1000 tokens
8. L2 检索：`get_l2_context()` 返回 ≤500 tokens
9. 综合检索：`get_relevant_context()` 返回 ≤1500 tokens
10. soul_prompts 注入：`inject_soul_prompt()` 含记忆段，长度合规
11. soul_prompts 向后兼容：不传 `memory_core` 时行为不变
12. 管道输出到记忆写入的完整链路：`DailyInsight → update_from_daily → get_l1_context` 正常

## 九、验收标准

| # | 验收项 | 判定标准 |
|:---|:---|:---|
| 1 | L1 写入 + 修剪 | 写入成功，>30条自动修剪 |
| 2 | L2 写入 + 修剪 | 写入成功，>10个快照自动修剪 |
| 3 | 持久化 | `l1_insights.json` 和 `l2_portraits.json` 可读写 |
| 4 | 检索 Token 预算 | L1≤1000, L2≤500, 综合≤1500 |
| 5 | soul_prompts 记忆注入 | 含 `[对你的理解]` 段，带画像名称 |
| 6 | soul_prompts 向后兼容 | 不传 `memory_core` 时与原版一致 |
| 7 | AgentLoop 集成 | `get_system_prompt()` 正常调用新签名 |
| 8 | 验证脚本 | `verify_s2_3.py` 全部通过 |
| 9 | 历史测试兼容 | 所有已有验证脚本通过 |

## 十、关键约束

- 不改动 `memory/ximing_pipeline.py`
- 不改动 GenericAgent 核心文件（仅 agentmain.py 的 get_system_prompt 调用可微调）
- 记忆持久化为本地 JSON，数据主权 100% 本地
- 所有修剪自动静默执行，不阻塞对话
- Token 预算必须严格遵守

---

*规格结束。请以本文档为唯一执行依据。规格书中代码示例为设计意图参考，请在理解后适配实现，保持接口契约不变。*