"""
WoodGrower — 木·生增强：程序化结晶触发 + 产物质量校验

设计依据：
  - 验证报告：GA 自发结晶触发率 0/5，LLM 默认倾向"不记"
  - 方案设计书：硬触发 + 硬校验，不依赖 LLM 自觉
  - L0 公理3：禁止易变状态（绝对路径、日期、环境特定值）

WoodGrower 不修改 GA 的结晶逻辑，而是在其外部增加：
  - 触发层：Agent Loop 结束时的自动判断与指令注入
  - 校验层：SOP 写入后的程序化质量检查
  - 注册层：将校验通过的 SOP 登记到 SkillRegistry
"""

import re
from pathlib import Path
from dataclasses import dataclass, field
from typing import List, Optional

# ---------------------------------------------------------------------------
# 配置与数据结构
# ---------------------------------------------------------------------------


@dataclass
class WoodGrowerConfig:
    """木·生增强的配置"""
    enabled: bool = True                # 总开关
    min_tool_calls: int = 3             # 最少成功工具调用次数（低于此值不触发蒸馏）
    max_sop_lines: int = 100            # SOP 最大行数（超过则警告）
    post_validate: bool = True          # 是否启用产物自动校验
    auto_fix: bool = True               # 是否自动修复可修复的校验问题


@dataclass
class ValidationRule:
    """产物校验规则"""
    id: str                             # 规则编号：R1/R2/R3/R4
    name: str                           # 规则名称
    pattern: str                        # 正则表达式
    severity: str                       # "error"（自动修复或报错）/ "warning"（仅提示）
    auto_fix: str                       # 自动修复方式
    violation_message: str              # 违规时的提示信息


@dataclass
class ValidationResult:
    """校验结果"""
    passed: bool                        # 是否通过（无 error 级别违规）
    violations: list = field(default_factory=list)    # 违规列表
    auto_fixed: list = field(default_factory=list)    # 已自动修复的列表
    warnings: list = field(default_factory=list)      # 警告列表
    original_sop: str = ""              # 校验前 SOP 内容
    fixed_sop: str = ""                 # 自动修复后 SOP 内容


# ---------------------------------------------------------------------------
# 默认校验规则
# ---------------------------------------------------------------------------

DEFAULT_RULES: List[ValidationRule] = [
    ValidationRule(
        id="R1",
        name="禁止绝对路径",
        pattern=r'[A-Za-z]:\\\S+',       # 匹配 D:\... 等 Windows 绝对路径
        severity="error",
        auto_fix="replace_with_relative",
        violation_message="SOP 含绝对路径，违反 L0 公理3",
    ),
    ValidationRule(
        id="R2",
        name="禁止日期",
        pattern=r'\d{4}-\d{2}-\d{2}',    # 匹配 2026-05-03 等日期格式
        severity="error",
        auto_fix="delete_line",
        violation_message="SOP 含日期，违反 L0 公理3",
    ),
    ValidationRule(
        id="R3",
        name="禁止环境特定值",
        pattern=r'(/home/\S+|/Users/\S+|C:\\Users\\\S+)',  # Unix/Windows 用户目录
        severity="error",
        auto_fix="replace_with_generic",
        violation_message="SOP 含环境特定路径，违反 L0 公理3",
    ),
    ValidationRule(
        id="R4",
        name="应有行动验证引用",
        pattern=r'(tool_call|executed|verified|confirmed|returned|output)',
        severity="warning",
        auto_fix="none",
        violation_message="SOP 缺少行动验证引用，建议补充",
    ),
]

# ---------------------------------------------------------------------------
# 蒸馏指令模板
# ---------------------------------------------------------------------------

DISTILL_PROMPT_TEMPLATE = """Task completed. System instruction:

You MUST call start_long_term_update to crystallize this execution path.

When writing the SOP:
- Do NOT include absolute paths (like D:\\...)
- Do NOT include dates (like 2026-05-03)
- DO include references to successful tool call results
- Follow memory_management_sop.md Axiom 1 and Axiom 3 strictly"""


# ===========================================================================
# WoodGrower
# ===========================================================================

class WoodGrower:
    """
    木·生增强：确保技能结晶的触发确定性和产物质量。

    设计依据：
    - 验证报告 5.1：GA 自发结晶触发率 0/5，LLM 默认倾向"不记"
    - 方案设计书：硬触发 + 硬校验，不依赖 LLM 自觉

    供后续集成使用的能力：
    - should_trigger_distill() — 判断是否需要注入蒸馏指令
    - build_distill_prompt() — 返回可追加到消息队列的指令文本
    - post_validate() — 校验已生成的 SOP，返回 ValidationResult
    """

    def __init__(self, registry, config: Optional[WoodGrowerConfig] = None):
        """
        初始化 WoodGrower。

        Args:
            registry: SkillRegistry 实例（用于后续注册校验通过的技能）
            config: WoodGrower 配置，为 None 时使用默认配置
        """
        self._registry = registry
        self.config = config if config is not None else WoodGrowerConfig()
        self._rules = DEFAULT_RULES

    # ------------------------------------------------------------------
    # 触发判断
    # ------------------------------------------------------------------

    def should_trigger_distill(self, turn_history: list) -> bool:
        """
        判断是否应该触发蒸馏。

        条件：
        1. config.enabled 为 True
        2. 成功的工具调用次数 ≥ config.min_tool_calls

        turn_history 中每项包含 'type' 字段，
        'type' == 'tool_call' 且无错误标记视为成功。

        Args:
            turn_history: 本轮对话中所有工具调用的记录列表

        Returns:
            True 表示应触发蒸馏，False 表示不触发
        """
        if not self.config.enabled:
            return False

        success_count = 0
        for item in (turn_history or []):
            if not isinstance(item, dict):
                continue
            if item.get("type") == "tool_call":
                # 无错误标记视为成功
                if not item.get("error"):
                    success_count += 1

        return success_count >= self.config.min_tool_calls

    # ------------------------------------------------------------------
    # 蒸馏指令
    # ------------------------------------------------------------------

    def build_distill_prompt(self) -> str:
        """
        构造蒸馏指令。

        返回的文本包含"做什么"（必须调用 start_long_term_update）
        和"怎么做"（遵守公理、禁止易变状态），可追加到对话消息队列中。

        Returns:
            蒸馏指令文本；若 config.enabled 为 False 则返回空字符串
        """
        if not self.config.enabled:
            return ""
        return DISTILL_PROMPT_TEMPLATE

    # ------------------------------------------------------------------
    # 产物校验
    # ------------------------------------------------------------------

    def post_validate(self, sop_path: str) -> ValidationResult:
        """
        SOP 写入后调用。用正则检测易变状态，自动修复可修复的问题。

        若 config.post_validate 为 False，跳过校验直接返回通过。
        若 config.auto_fix 关闭，仅检测不修改。

        R1/R2/R3（error）：检测到违规 → 记录并尝试自动修复。
        R4（warning）：全文未匹配到行动验证关键词 → 添加警告。

        Args:
            sop_path: SOP 文件的绝对或相对路径

        Returns:
            ValidationResult 包含校验结果、违规列表、修复信息
        """
        # 读取 SOP 内容
        sop_file = Path(sop_path)
        if not sop_file.exists():
            return ValidationResult(
                passed=False,
                violations=[{"rule_id": "FILE", "line": 0,
                             "content": f"File not found: {sop_path}"}],
            )

        try:
            original_sop = sop_file.read_text(
                encoding="utf-8", errors="replace")
        except Exception as e:
            return ValidationResult(
                passed=False,
                violations=[{"rule_id": "FILE", "line": 0,
                             "content": f"Read error: {e}"}],
            )

        # 若关闭校验，直接返回通过
        if not self.config.post_validate:
            return ValidationResult(
                passed=True,
                original_sop=original_sop,
                fixed_sop=original_sop,
            )

        lines = original_sop.split("\n")
        violations: list = []
        auto_fixed: list = []
        warnings: list = []
        fixed_lines = list(lines)

        # R1/R2/R3: 逐行检测 error 级规则（匹配 → 违规）
        for i, line in enumerate(lines):
            line_num = i + 1
            for rule in self._rules:
                if rule.severity != "error":
                    continue  # R4 单独处理

                if not re.search(rule.pattern, line):
                    continue

                violation_entry = {
                    "rule_id": rule.id,
                    "line": line_num,
                    "content": line.strip()[:120],
                }
                violations.append(violation_entry)

                if self.config.auto_fix:
                    fixed_line = self._apply_fix(line, rule)
                    if fixed_line != line:
                        fixed_lines[i] = fixed_line
                        auto_fixed.append({
                            **violation_entry,
                            "fixed_to": fixed_line.strip()[:120],
                        })

        fixed_sop = "\n".join(fixed_lines)

        # R4: 全文检测 warning 级规则（末匹配 → 警告）
        for rule in self._rules:
            if rule.severity != "warning":
                continue
            if not re.search(rule.pattern, fixed_sop):
                warnings.append({
                    "rule_id": rule.id,
                    "line": 0,
                    "content": rule.violation_message,
                })

        # 判断是否通过：无未修复的 error 违规
        unfixed_errors = [
            v for v in violations
            if not any(
                v["rule_id"] == a["rule_id"] and v["line"] == a["line"]
                for a in auto_fixed
            )
        ]
        passed = len(unfixed_errors) == 0

        # 写入修复后的内容
        if auto_fixed and self.config.auto_fix:
            try:
                sop_file.write_text(
                    fixed_sop, encoding="utf-8", errors="replace")
            except Exception:
                pass  # 写入失败不影响结果返回

        return ValidationResult(
            passed=passed,
            violations=violations,
            auto_fixed=auto_fixed,
            warnings=warnings,
            original_sop=original_sop,
            fixed_sop=fixed_sop,
        )

    # ------------------------------------------------------------------
    # 自动修复
    # ------------------------------------------------------------------

    def _apply_fix(self, line: str, rule: ValidationRule) -> str:
        """
        对单行应用自动修复。

        Args:
            line: 原始行内容
            rule: 触发修复的规则

        Returns:
            修复后的行内容
        """
        fix_type = rule.auto_fix

        if fix_type == "delete_line":
            return ""

        if fix_type == "replace_with_relative":
            # 替换 Windows 绝对路径为通用相对描述
            return re.sub(
                rule.pattern,
                "<项目目录>/...",
                line,
            )

        if fix_type == "replace_with_generic":
            # 替换用户目录路径为通用描述
            return re.sub(
                rule.pattern,
                "<用户目录>/...",
                line,
            )

        # "none" 或不支持的修复方式：原样返回
        return line
