# S3-2: WoodGrower（木·生增强）执行规格

> **版本**：v1.0.0  
> **日期**：2026-05-03  
> **状态**：待执行  
> **依赖**：S3-1 已完成（SkillRegistry + 版本管理可用）  
> **设计依据**：《慧惠五行流转引擎-方案设计书v1.0_imaBot》第六·1节


## 一、任务信息

| 属性 | 值 |
|:---|:---|
| 任务编号 | S3-2 |
| 任务名称 | WoodGrower 木·生增强——程序化结晶触发 + 产物质量校验 |
| 优先级 | P0 |
| 预估工作量 | 2天 |
| 依赖 | S3-1 完成（`skills/skill_registry.py` 可用） |

## 二、任务背景与设计理念

### 2.1 要解决的真实问题

我们在 2026-05-03 的自动化测试中发现：

| 问题 | 数据 | 根因 |
|:---|:---|:---|
| GA 自发结晶触发率极低 | 0/5（修正后） | LLM 默认倾向“不记”，需显式指令才触发 |
| 产物质量不可控 | SOP 含绝对路径和日期 | LLM 能读懂 L0 公理但不保证执行 |

### 2.2 核心设计理念：硬触发 + 硬校验

**不依赖 LLM 自觉，用程序化机制保障。**

- **硬触发**：Agent Loop 结束时若满足条件，自动在消息队列中追加蒸馏指令，要求 LLM 调用 `start_long_term_update`
- **硬校验**：SOP 写入后，用正则表达式检测易变状态，违反则自动修复，修复失败则标记为 `validation_failed`
- **后置筛选**：“成功即记录”放宽结晶门槛，筛选（金·克）放在后续阶段。不在收割时判断哪颗谷子值得留，先全部收进来

### 2.3 与 GA 原生机制的关系

WoodGrower 不修改 GA 的结晶逻辑，而是在其外部增加：
- **触发层**：Agent Loop 结束时的自动判断与指令注入
- **校验层**：SOP 写入后的程序化质量检查
- **注册层**：将校验通过的 SOP 登记到 SkillRegistry


## 三、当前代码状态

| 模块 | 状态 | 可用接口 |
|:---|:---|:---|
| `skills/skill_registry.py` | ✅ | `SkillRegistry`（注册、查询、持久化）、`SkillVersionManager`（快照、回滚） |
| GA 结晶机制 | ✅ | `start_long_term_update` 工具、L0 公理、五层记忆架构 |
| `agent_loop.py` | ✅ | Agent Loop 退出点（模型无工具调用时 break） |

## 四、操作文件

| 文件 | 操作 | 说明 |
|:---|:---|:---|
| `skills/wood_grower.py` | **新建** | WoodGrower 完整实现 |
| `skills/verify_s3_2.py` | **新建** | S3-2 专项验证脚本 |

**不修改已有文件**（S3-2 阶段仅实现模块本身，集成点到 S3-5 统一处理）。

## 五、WoodGrower 完整设计

### 5.1 配置数据结构

```python
@dataclass
class WoodGrowerConfig:
    """木·生增强的配置"""
    enabled: bool = True                # 总开关
    min_tool_calls: int = 3             # 最少成功工具调用次数（低于此值不触发蒸馏）
    max_sop_lines: int = 100            # SOP 最大行数（超过则警告）
    post_validate: bool = True          # 是否启用产物自动校验
    auto_fix: bool = True               # 是否自动修复可修复的校验问题
```

### 5.2 核心类与公开方法

```python
class WoodGrower:
    """
    木·生增强：确保技能结晶的触发确定性和产物质量。
    
    设计依据：
    - 验证报告：GA 自发结晶触发率 0/5，LLM 默认倾向“不记”
    - 方案设计书：硬触发 + 硬校验，不依赖 LLM 自觉
    """
    
    def __init__(self, registry: SkillRegistry, config: WoodGrowerConfig = None):
        """初始化。config 为 None 时使用默认配置。"""
        ...
    
    def should_trigger_distill(self, turn_history: list) -> bool:
        """
        判断是否应该触发蒸馏。
        条件：成功的工具调用次数 ≥ config.min_tool_calls
        turn_history 中每项包含 'type' 字段，'type' == 'tool_call' 且无错误标记视为成功。
        """
        ...
    
    def build_distill_prompt(self) -> str:
        """
        构造蒸馏指令。指令中同时包含“做什么”（必须调用工具）和“怎么做”（遵守公理、禁止易变状态）。
        """
        ...
    
    def post_validate(self, sop_path: str) -> ValidationResult:
        """
        SOP 写入后调用。用正则检测易变状态，自动修复可修复的问题。
        若 auto_fix 关闭，仅检测不修改。
        """
        ...
```

### 5.3 蒸馏指令模板

`build_distill_prompt()` 返回如下文本，将被追加到对话消息中：

```
Task completed. System instruction:

You MUST call start_long_term_update to crystallize this execution path.

When writing the SOP:
- Do NOT include absolute paths (like D:\...)
- Do NOT include dates (like 2026-05-03)
- DO include references to successful tool call results
- Follow memory_management_sop.md Axiom 1 and Axiom 3 strictly
```

### 5.4 产物校验规则

文件新增 `skills/validation_rules.py`，定义校验规则集：

```python
# skills/validation_rules.py

@dataclass
class ValidationRule:
    id: str            # 规则编号：R1/R2/R3/R4
    name: str          # 规则名称
    pattern: str       # 正则表达式
    severity: str      # "error"（自动修复或报错）/ "warning"（仅提示）
    auto_fix: str      # 自动修复方式描述
    violation_message: str  # 违规时的提示信息

DEFAULT_RULES: list[ValidationRule] = [
    ValidationRule(
        id="R1", name="禁止绝对路径",
        pattern=r'[A-Za-z]:\\\S+',                # 匹配 D:\... 等 Windows 绝对路径
        severity="error", auto_fix="replace_with_relative",
        violation_message="SOP 含绝对路径，违反 L0 公理3"
    ),
    ValidationRule(
        id="R2", name="禁止日期",
        pattern=r'\d{4}-\d{2}-\d{2}',              # 匹配 2026-05-03 等日期格式
        severity="error", auto_fix="delete_line",
        violation_message="SOP 含日期，违反 L0 公理3"
    ),
    ValidationRule(
        id="R3", name="禁止环境特定值",
        pattern=r'(/home/\S+|/Users/\S+|C:\\Users\\\S+)',  # Unix/Windows 用户目录
        severity="error", auto_fix="replace_with_generic",
        violation_message="SOP 含环境特定路径，违反 L0 公理3"
    ),
    ValidationRule(
        id="R4", name="应有行动验证引用",
        pattern=r'(tool_call|executed|verified|confirmed|returned|output)',  # 行动验证关键词
        severity="warning", auto_fix="none",
        violation_message="SOP 缺少行动验证引用，建议补充"
    ),
]
```

**自动修复方式说明**：
- `replace_with_relative`：将绝对路径替换为 `<项目目录>/...` 等通用描述
- `delete_line`：删除含有日期的整行
- `replace_with_generic`：将用户目录路径替换为 `<用户目录>/...`
- `none`：标记为 warning，不自动修改

### 5.5 校验结果数据结构

```python
@dataclass
class ValidationResult:
    passed: bool                          # 是否通过（无 error 级别违规）
    violations: list[dict]                # 违规列表 [{"rule_id": "R1", "line": 3, "content": "..."}]
    auto_fixed: list[dict]                # 已自动修复的列表
    warnings: list[dict]                  # 警告列表（warning 级别）
    original_sop: str                     # 校验前 SOP 内容
    fixed_sop: str                        # 自动修复后 SOP 内容（如无修复则与 original_sop 相同）
```

### 5.6 供后续集成使用的预留能力

`WoodGrower` 本身不负责文件系统的变更（写入 SOP、移动文件等），这些操作由 GA 原生机制完成。WoodGrower 提供以下能力供集成层（S3-5 RootAuditor）使用：

1. `should_trigger_distill()` — 判断是否需要注入蒸馏指令
2. `build_distill_prompt()` — 返回可追加到消息队列的文本
3. `post_validate()` — 校验已生成的 SOP，返回 `ValidationResult`

在 S3-5 时，集成层将：
- 在 Agent Loop 结束时调用 `should_trigger_distill()`
- 若返回 True，将 `build_distill_prompt()` 追加到消息队列
- 监控 `memory/` 目录是否有新 `*_sop.md` 生成
- 对新 SOP 调用 `post_validate()`
- 若通过校验，调用 `SkillRegistry.register()` 登记

但以上集成行为**不是 S3-2 的范围**，S3-2 只实现 WoodGrower 模块本身及单元验证。


## 六、验证脚本

`skills/verify_s3_2.py` 需覆盖：

1. 初始化：`WoodGrower(registry)` 创建成功，默认配置加载
2. `should_trigger_distill` — 成功工具调用次数 ≥3 时返回 True
3. `should_trigger_distill` — 成功工具调用次数 <3 时返回 False
4. `should_trigger_distill` — 空历史返回 False
5. `build_distill_prompt` — 返回非空字符串，含关键指令词
6. `post_validate` — 无违规的 SOP 通过校验
7. `post_validate` — 含绝对路径的 SOP 被检测并自动修复（auto_fix=True）
8. `post_validate` — 含日期的 SOP 被检测并自动修复
9. `post_validate` — 缺少行动验证引用的 SOP 标记为 warning（不阻止通过）
10. `post_validate` — 关闭 auto_fix 时仅检测不修改
11. `post_validate` — 多违规同时存在时全部检测并分类
12. `post_validate` — 修复后的 SOP 不含违规内容
13. 禁用开关：`config.enabled = False` 时 `should_trigger_distill()` 始终返回 False
14. 产物质量：所有自动修复后的 SOP 行数 ≤ 100 行（max_sop_lines）
15. 与 SkillRegistry 兼容：`WoodGrower` 可接受 `SkillRegistry` 实例作为参数（S3-5 集成时使用）

## 七、验收标准

| # | 验收项 | 判定标准 |
|:---|:---|:---|
| 1 | 文件创建 | `skills/wood_grower.py` 存在，含完整 WoodGrower 类 |
| 2 | 触发判断 | `should_trigger_distill` 在 ≥3 次成功工具调用时返回 True，<3 次返回 False |
| 3 | 蒸馏指令 | `build_distill_prompt` 返回非空指令文本 |
| 4 | 产物校验 | R1/R2/R3 自动检测并修复，R4 标记 warning |
| 5 | 自动修复 | 修复后 SOP 不含被检测的违规内容 |
| 6 | 禁用开关 | `config.enabled = False` 时所有方法返回安全默认值 |
| 7 | 验证脚本 | `verify_s3_2.py` 全部 15 项通过 |
| 8 | 历史测试兼容 | 所有已有验证脚本通过 |

## 八、关键约束

- 不改动 GenericAgent 核心文件
- 不修改 GA 原有的 `start_long_term_update` 逻辑
- 本阶段仅实现 WoodGrower 模块本身，集成到 AgentLoop 由 S3-5 统一处理
- 与 SkillRegistry 的对接通过构造函数传入实例，不硬编码路径