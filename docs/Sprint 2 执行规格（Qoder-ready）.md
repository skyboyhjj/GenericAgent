# 慧惠 Sprint 2 执行规格（Qoder-ready）

> **版本**：v1.0.0  
> **日期**：2026-05-02  
> **状态**：待执行  
> **依赖**：Sprint 1 已完成  

---

## 一、Sprint 概览

| 属性 | 值 |
|:---|:---|
| Sprint 目标 | 记忆觉醒 + 理解管道 |
| 周期 | 2 周 |
| P0 任务 | 3 个 |
| P1 任务 | 3 个 |

**核心交付**：
1. 打通“每日袭明”小程序数据接口
2. 蒸馏管道完整运行
3. 慧惠能基于修行数据给出个性化回应

**验收总则**：
- 用户完成晚间回顾后，慧惠静默同步数据（用户无感）
- 次日清晨，慧惠的问候中包含对昨日修行状态的个性化反馈
- 阴阳画像“笃行的清明者”等9种类型可正确生成

---

## 二、已完成模块状态

| 模块 | 文件 | 提供能力 |
|:---|:---|:---|
| Soul | `core/soul.py` | `Soul` 类、`to_system_prompt()`、`check_moral_boundary()` |
| Soul 注入 | `core/soul_prompts.py` | `inject_soul_prompt(base_prompt, user_input=None)` |
| 场景匹配 | `core/scenario_matcher.py` | `ScenarioMatcher` 类 |
| 场景库 | `prompts/scenarios.json` | 22 个差异化场景模板 |
| 初见 | `core/initializer.py` | `InitializationHandler` |
| 启动 | `launch_huihui.pyw` | 慧惠专属入口 |

---

## 三、任务分解

| 编号 | 任务 | 优先级 | 工作量 | 产出文件 |
|:---|:---|:---|:---|:---|
| **S2-1** | 伴侣侧：实现 `XiMingClient.py` | P0 | 2天 | `memory/ximing_client.py` |
| **S2-2** | 实现 `XiMingPipeline.py`（蒸馏管道） | P0 | 4天 | `memory/ximing_pipeline.py` |
| **S2-3** | 实现 `MemoryCore.py` L2 层与小程序数据对接 | P0 | 2天 | `memory/memory_core.py` |
| S2-4 | 设计“慧惠懂你”的交互场景 | P1 | 2天 | `prompts/insight_scenes.json` |
| S2-5 | 修行数据同步授权交互设计 | P1 | 1天 | `core/auth_ritual.py` |
| S2-6 | 集成测试：完整数据流 | P1 | 1天 | `verify_s2_integration.py` |

---

## 四、S2-1: 实现 `XiMingClient.py`

### 4.1 任务信息

| 属性 | 值 |
|:---|:---|
| 文件 | `memory/ximing_client.py`（新建） |
| 依赖 | 无 |

### 4.2 任务目标

实现慧惠与“每日袭明”小程序的本地数据同步客户端，支持首次全量同步 + 后续增量同步 + 用户授权。

### 4.3 接口契约

**基地址**：`http://127.0.0.1:9876/api/v1`

| 端点 | 方法 | 说明 |
|:---|:---|:---|
| `/api/v1/history` | GET | 拉取全部历史修行数据 |
| `/api/v1/today` | GET | 拉取今日修行数据 |

**响应格式**：
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

### 4.4 实现要求

- 实现 `XiMingClient` 类
- `sync_history()` 方法：拉取全量历史数据
- `sync_today()` 方法：拉取今日数据
- `check_connectivity()` 方法：检测小程序 HTTP 服务是否可达
- 错误处理：连接超时(5s) → 静默降级；4xx → 记录日志；5xx → 指数退避重试(最多3次)

### 4.5 关键约束

- 首次同步需用户授权（由 S2-5 实现，此处预留 `requires_auth` 参数）
- 数据同步需标注 `data_date` 和 `algorithm_version`

### 4.6 验收标准

- `memory/ximing_client.py` 文件创建成功
- `check_connectivity()` 可检测小程序服务状态
- `sync_history()` 和 `sync_today()` 返回结构化数据
- 连接超时时不抛出异常，返回降级状态


## 五、S2-2: 实现 `XiMingPipeline.py`（蒸馏管道）

### 5.1 任务信息

| 属性 | 值 |
|:---|:---|
| 文件 | `memory/ximing_pipeline.py`（新建） |
| 依赖 | S2-1 已完成 |

### 5.2 任务目标

实现数据蒸馏管道，将“每日袭明”的原始修行数据逐层提炼为慧惠可用的洞察与记忆。

### 5.3 管道架构

```
原始数据 (XiMingClient)
    ↓
L4 归档器：全量向量化存档
    ↓
L3 模式识别器：周期性/趋势/关联模式
    ↓
L2 指标计算器：核心指标 + 阴阳画像
    ↓
L1 洞察生成器：每日/每周摘要
```

### 5.4 各层实现要求

#### L4 归档器

- 以日为单位分块存储原始数据
- 对事件描述进行向量化（使用 `text-embedding-3-small` 或本地轻量模型）
- 支持按时间范围和语义相似度检索

#### L3 模式识别器

- 识别周期性模式（如“每周末能量层级偏高”）
- 识别趋势模式（如“识位分数连续7天上升”）
- 识别关联模式（如“亲密关系事件平均能量层级高于均值1.5分”）

#### L2 指标计算器

- 计算核心修行指标：修行天数、总能量分、平均能量、连续修行天数
- 计算四维平衡度：时/宇/识/缘四轴均分与趋势
- 生成阴阳画像：
  - **阳的形态**：行者型 / 悟者型 / 习者型
  - **阴的质地**：清明之境 / 砥砺之境 / 蓄养之境
  - **综合画像**：9 种类型（如“笃行的清明者”）
- 动态平衡诊断：阳盛阴清 / 阳亢阴浊 / 阳弱阴凝 / 阳散阴晦

#### L1 洞察生成器

- 生成每日修行摘要（≤100 tokens）
- 生成每周成长报告
- 识别关键事件（能量显著偏离基线的事件）

### 5.5 接口契约

```python
class XiMingPipeline:
    async def process_daily(self, raw_data: dict) -> DailyInsight
    async def process_full_history(self, history: list) -> dict
    def get_portrait(self) -> dict  # 返回当前用户画像
    def get_daily_insight(self, date: str) -> DailyInsight
```

### 5.6 验收标准

- `memory/ximing_pipeline.py` 文件创建成功
- L4 归档功能正常，原始数据可检索
- L3 模式识别输出至少 1 种模式类型
- L2 阴阳画像可正确生成 9 种类型之一
- L1 每日洞察长度 ≤100 tokens


## 六、S2-3: 实现 `MemoryCore.py` L2 层对接

### 6.1 任务信息

| 属性 | 值 |
|:---|:---|
| 文件 | `memory/memory_core.py`（新建） |
| 依赖 | S2-2 已完成 |

### 6.2 任务目标

实现慧惠的五层记忆系统，将修行衍生数据写入对应记忆层，供 AgentLoop 检索。

### 6.3 五层记忆结构

| 层级 | 名称 | 存储内容 | 注入 AgentLoop 方式 |
|:---|:---|:---|:---|
| L0 | 元规则 | Soul.py 核心价值观 | `soul_prompts.py` 注入 |
| L1 | 洞察索引 | 修行趋势摘要、四维短板标记 | 导航上下文（≤1000 tokens） |
| L2 | 稳定知识 | 修行指标、阴阳画像、维度档案 | 按相关性检索（≤500 tokens） |
| L3 | 可复用技能 | skills/ 目录 SOP 文件 | 命中 L1 后按需展开 |
| L4 | 原始归档 | 向量化全量修行轨迹 | 不直接进入上下文 |

### 6.4 与现有模块的集成

- L2 数据由 S2-2 的 `XiMingPipeline` 产出，`MemoryCore` 负责存储和检索
- `AgentLoop._think()` 调用 `MemoryCore.get_relevant_context()` 获取记忆
- 注入位置在场景参考之后、任务上下文之前

### 6.5 验收标准

- `memory/memory_core.py` 文件创建成功
- 五层记忆均可读写
- L1-L2 层检索延迟 < 100ms
- 记忆注入不导致上下文超 30K token


## 七、S2-4: “慧惠懂你”交互场景（P1）

### 7.1 任务信息

| 属性 | 值 |
|:---|:---|
| 文件 | `prompts/insight_scenes.json`（新建） |
| 依赖 | S2-3 已完成 |

### 7.2 任务目标

设计 ≥5 个基于修行数据的个性化关怀场景，与 `scenarios.json` 格式兼容。

### 7.3 必含场景

1. 缘位轴进步提醒
2. 连续修行里程碑祝贺
3. 能量波动安抚
4. 维度短板温柔提醒
5. 修行节奏尊重（阳弱阴凝型用户）

### 7.4 验收标准

- `prompts/insight_scenes.json` 创建成功
- ≥5 个场景，每个场景的 `value` 字段映射到阴阳画像状态之一


## 八、S2-5: 数据同步授权交互（P1）

### 8.1 任务信息

| 属性 | 值 |
|:---|:---|
| 文件 | `core/auth_ritual.py`（新建） |
| 依赖 | S2-1 已完成 |

### 8.2 任务目标

设计首次数据同步前的“授权仪式”，让用户在知情且自愿的前提下，授权慧惠读取修行数据。

### 8.3 实现要求

- 在 `InitializationHandler` 中增加可选的授权步骤（默认开启）
- 授权话术示例：“为了更好地陪伴你，我想读取你的修行记录。可以吗？”
- 用户同意 → 开始同步
- 用户拒绝 → 跳过同步，慧惠仍可正常对话

### 8.4 验收标准

- `core/auth_ritual.py` 创建成功
- 同意/拒绝两条路径均可正常运行


## 九、S2-6: 集成测试（P1）

### 9.1 任务信息

| 属性 | 值 |
|:---|:---|
| 文件 | `verify_s2_integration.py`（新建） |
| 依赖 | S2-1 ~ S2-5 全部完成 |

### 9.2 测试场景

1. 模拟首次同步全量历史数据
2. 模拟每日增量同步
3. 模拟同步失败降级
4. 验证蒸馏管道输出（L4→L3→L2→L1）
5. 验证阴阳画像生成正确
6. 验证记忆注入不超 Token 预算
7. 验证修行数据在对话中体现（“昨天你的缘位进步了”）

### 9.3 验收标准

- 全部 7 项测试通过
- 终端输出 "S2 ALL TESTS PASSED"


## 十、Sprint 2 验收总清单

- [ ] `memory/ximing_client.py` 可同步数据
- [ ] `memory/ximing_pipeline.py` 蒸馏管道完整运行
- [ ] `memory/memory_core.py` 五层记忆正常
- [ ] 阴阳画像 9 种类型可正确生成
- [ ] “慧惠懂你” 5 个场景可触发
- [ ] 授权仪式两条路径均可运行
- [ ] 集成测试全部通过
- [ ] 全部历史测试仍通过（verify_soul.py, verify_s1_2.py, verify_s1_3.py, verify_s1_4.py, verify_s1_5.py）

---

## 十一、关键约束

- 不改动 GenericAgent 核心文件
- 所有新增文件放在 `memory/` 目录下
- 数据仅在 127.0.0.1 本地传输
- 所有同步标注 `algorithm_version`
- 修行数据仅只读，永不回写小程序

---

*规格结束。请以本文档为唯一执行依据，如有歧义，优先参照《慧惠产品体验定义书》和《技术规格书 v0.3.0》的设计意图。*