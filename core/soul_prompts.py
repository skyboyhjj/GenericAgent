"""
慧惠 Soul → LLM System Prompt 注入层

职责：
1. 将 Soul 实例转换为 LLM 兼容的 system prompt 前缀
2. 提供 LLM 回复的道德边界检查
3. 注入匹配的场景模板作为语气/风格参考
"""

import json
from pathlib import Path
from typing import Any

from core.soul import get_soul
from core.scenario_matcher import ScenarioMatcher

# ---- 场景缓存 ----
_scenarios_cache: list[dict[str, Any]] | None = None
_scenarios_path: Path | None = None


def _load_scenarios() -> list[dict[str, Any]]:
    """加载场景模板文件，结果会被缓存以提升性能。

    Returns:
        场景模板列表；文件不存在时返回空列表
    """
    global _scenarios_cache, _scenarios_path

    path = Path(__file__).parent.parent / "prompts" / "scenarios.json"

    if _scenarios_cache is not None and _scenarios_path == path:
        return _scenarios_cache

    if path.exists():
        with open(path, "r", encoding="utf-8") as f:
            _scenarios_cache = json.load(f)
    else:
        _scenarios_cache = []

    _scenarios_path = path
    return _scenarios_cache


def inject_soul_prompt(
    base_prompt: str,
    user_input: str | None = None,
    memory_core=None,
) -> str:
    """将 Soul 的系统身份设定注入到 base_prompt 的最前面。

    每次调用都动态获取 Soul 实例，确保 prompt 反映最新的 Soul 状态。

    注入层级：
    1. [系统身份设定 - 最高优先级] — Soul 基线
    2. [场景参考] — 场景模板 few-shot（如有 user_input）
    3. [对你的理解] — MemoryCore L1+L2 记忆（如有 memory_core）
    4. {原始基础提示词}

    Args:
        base_prompt: 原始系统提示词
        user_input: 用户当前输入（可选，用于场景匹配）
        memory_core: MemoryCore 实例（可选，用于记忆注入）

    Returns:
        注入 Soul（及可选场景模板和记忆）后的完整 system prompt 字符串
    """
    soul = get_soul()
    soul_block = soul.to_system_prompt()

    result = (
        "[系统身份设定 - 最高优先级]\n"
        f"{soul_block}"
    )

    # ---- 场景模板注入 ----
    if user_input:
        scenarios = _load_scenarios()
        if scenarios:
            matcher = ScenarioMatcher(min_score=0.25)
            matched = matcher.match(user_input, scenarios, max_results=3)
            if matched:
                result += "\n\n[场景参考 - 仅供参考语气风格，非硬性要求]\n"
                result += "以下是与当前对话相关的场景示例，请参考其语气和风格：\n"
                for i, scene in enumerate(matched, 1):
                    result += f"{i}. {scene['response_example']}\n"

    # ---- 记忆上下文注入 ----
    if memory_core is not None and memory_core.has_memory:
        memory_block = _build_memory_block(memory_core)
        if memory_block:
            result += f"\n\n{memory_block}"

    result += f"\n\n{base_prompt}"
    return result


def _build_memory_block(memory_core) -> str:
    """构建 [对你的理解] 记忆注入文本块。

    格式：
    [对你的理解]
    最近修行趋势：{L2最新画像一句话总结}
    近期状态：{L1最近7天趋势描述}
    当前画像：{综合画像名称}
    """
    l2 = memory_core.get_l2_latest()
    l1_entries = memory_core.get_l1_recent(7)

    if not l2 and not l1_entries:
        return ""

    lines: list[str] = ["[对你的理解]"]

    # 最近修行趋势（来自 L2）
    if l2:
        trend_parts = [f"综合画像: {l2.portrait_combined}"]
        if l2.balance_diagnosis:
            trend_parts.append(f"({l2.balance_diagnosis})")
        trend_parts.append(
            f"修行{l2.total_days}天, 连续{l2.consecutive_days}天, "
            f"能量均分{l2.avg_energy_score}"
        )
        lines.append(f"最近修行趋势：{''.join(trend_parts)}")
    else:
        lines.append("最近修行趋势：暂无足够数据。")

    # 近期状态（来自 L1）
    if l1_entries:
        curves = [e.energy_curve for e in l1_entries if e.energy_curve]
        rising = curves.count("上升")
        falling = curves.count("下降")
        stable = curves.count("平稳")

        if rising > falling and rising > stable:
            l1_trend = "能量呈上升趋势"
        elif falling > rising and falling > stable:
            l1_trend = "能量偶有波动"
        else:
            l1_trend = "能量保持平稳"

        lines.append(f"近期状态：近{len(l1_entries)}日{l1_trend}。")
    else:
        lines.append("近期状态：暂无足够数据。")

    # 当前画像
    if l2 and l2.portrait_combined:
        lines.append(f"当前画像：{l2.portrait_combined}")
    elif l2:
        lines.append(f"当前画像：{l2.portrait_yang} / {l2.portrait_yin}")
    else:
        lines.append("当前画像：尚在探索中。")

    return "\n".join(lines)


def check_response(text: str) -> tuple[bool, str]:
    """检查 LLM 生成的回复是否越过道德边界。

    Args:
        text: LLM 生成的回复文本

    Returns:
        (True, text)   — 回复通过道德边界检查
        (False, msg)   — 回复被拒绝，msg 包含拒绝原因
    """
    soul = get_soul()
    if soul.check_moral_boundary(text):
        return (True, text)

    return (
        False,
        "[系统拒绝] 此回复越过道德边界，已被拦截。请重新生成。",
    )
