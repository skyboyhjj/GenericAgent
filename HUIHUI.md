# 慧惠（Huihui）

> 本仓库 = [上游 GenericAgent](https://github.com/lsdefine/GenericAgent) 的 fork + **慧惠定制层**。
> 本文件是慧惠与上游差异的官方说明；上游原版说明见 [README.md](README.md)。

## 慧惠是谁

慧惠是一个基于 GenericAgent 的数字伴侣。她在上游「最小自进化 Agent 框架」之上，叠加了两样上游没有的东西：

- **人格基线（Soul）**：定义她的本性——核心价值观、人格基线、道德边界。她是所有其他模块的北极星。
- **五行流转引擎**：以「木火土金水」五相，对技能（skill）的生命周期做循环治理。

她的设计哲学与主流 AI 相反：

> 世间 AI 都在帮你做加法，只有她，敢于帮你做减法。

## 与上游的关系

| 维度 | 说明 |
|:---|:---|
| 底座 | 复用上游 GenericAgent 的最小核心（约 3K 行：9 原子工具 + ~100 行 Agent Loop） |
| 设计原则 | **外挂增强，不改核心**——定制全部落在独立目录，尽量不侵入上游文件 |
| 启动入口 | `launch_huihui.pyw`（上游为 `launch.pyw`），提供专属初见仪式 + 五行/袭明启动流程 |
| 标识文件 | `huihui_initialized.flag` |

## 核心定制清单

### `core/` — 人格基线（Soul）

- `soul.py`：核心价值观、人格维度、道德边界（不伤害人类 / 不系统性欺骗 / 不侵犯隐私 / 不协助违法 / 不替用户做决定）。
- `soul_prompts.py`：将 Soul 编译为 LLM system prompt 片段，并注入到主循环。
- `scenario_matcher.py`：场景匹配。
- `initializer.py`：首次启动的初始化状态机。

### `skills/` — 五行流转引擎

| 模块 | 五行 | 职责 | 状态 |
|:---|:---|:---|:---|
| `wood_grower.py` | 木·生 | 程序化结晶触发 + 产物质量校验 | 已实现 |
| `fire_transformer.py` | 火·化 | 技能冗余识别与整合建议 | 轻量先行版 |
| `earth_connector.py` | 土·通 | 技能跨环境迁移 | 占位 |
| `metal_restrainer.py` | 金·克 | 健康度评估 + 自动归档（「为道日损」） | 已实现 |
| `water_adapter.py` | 水·变 | 技能更新/迁移检测 | 占位 |
| `skill_registry.py` | （中枢） | 技能注册、版本管理、健康评分 | 已实现 |
| `root_auditor.py` | （审计） | 周期审计与五行流转编排 | 已实现 |

### `algorithms/` — 五行算法

- `pzhongshu_analyzer.py`：忠恕/中和分析。
- `integration.py`、`verify_sad_energy.py`：五行能量与集成校验。

### 其他定制

- **多端前端**（`frontends/`）：钉钉 `dingtalkapp.py`、飞书 `fsapp.py`、企业微信 `wecomapp.py`、微信 `wechatapp.py`、QQ `qqapp.py`、Telegram `tgapp.py`、Discord `dcapp.py`、桌面 `qtapp.py`、终端 `tui_v3.py` 等，统一 `from agentmain import GeneraticAgent`。
- **袭明数据同步**：`memory/ximing_*`、`memory/memory_core.py`、`memory/greeting_engine.py`（记忆他人 / 问候引擎 / 每日镜鉴）。
- **插件**：`plugins/hooks.py`、`plugins/project_mode.py`。

## 启动方式

```bash
python launch_huihui.pyw
```

首次启动进入 INITIALIZING 状态机与初见仪式，再次启动直接进入常规 Agent Loop。

## 目录导航

- [core/](core/) · [skills/](skills/) · [algorithms/](algorithms/) · [plugins/](plugins/)
- [docs/UPSTREAM_SYNC.md](docs/UPSTREAM_SYNC.md) — 分叉治理与上游同步实录（含冲突热点与零冲突资产清单）
- [docs/requirements/](docs/requirements/) — 慧惠产品需求文档