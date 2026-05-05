"""P忠恕算法集成桥接 — 将 SAD 算法集成到慧惠技能流转流程中。

本模块提供:
1. P忠恕分数的便捷计算接口
2. 主观/客观权重管理（与 SkillRegistry / RootAuditor 联动）
3. SAD 分析结果持久化支持
"""

from __future__ import annotations

from typing import Optional

from algorithms.pzhongshu_analyzer import (
    PZhongshuDimensions,
    PZhongshuScore,
    PZhongshuConfig,
    SADReport,
    SADConfig,
    PZhongshuScoreCalculator,
    SADAnalyzer,
    HawkinsEnergyMapper,
    DEFAULT_WEIGHTS,
)

# ===========================================================================
# 全局单例
# ===========================================================================

_calculator: Optional[PZhongshuScoreCalculator] = None
_analyzer: Optional[SADAnalyzer] = None


def get_calculator() -> PZhongshuScoreCalculator:
    """获取 P忠恕 分数计算器单例。"""
    global _calculator
    if _calculator is None:
        _calculator = PZhongshuScoreCalculator()
    return _calculator


def get_analyzer() -> SADAnalyzer:
    """获取 SAD 分析器单例。"""
    global _analyzer
    if _analyzer is None:
        _analyzer = SADAnalyzer()
    return _analyzer


# ===========================================================================
# 便捷函数
# ===========================================================================

def calculate_pzhongshu(
    temporal: float,
    spatial: float,
    cognitive: float,
    causal: float,
    weights: Optional[tuple[float, float, float, float]] = None,
) -> PZhongshuScore:
    """便捷计算 P忠恕 分数。

    Args:
        temporal: 时位分数 (1-10)
        spatial:  宇位分数 (1-10)
        cognitive: 识位分数 (1-10)
        causal:   缘位分数 (1-10)
        weights:  自定义权重，默认 (0.2, 0.2, 0.3, 0.3)

    Returns:
        PZhongshuScore 对象
    """
    calc = get_calculator()
    if weights:
        calc.update_weights(weights)
    dims = PZhongshuDimensions(
        temporal=temporal,
        spatial=spatial,
        cognitive=cognitive,
        causal=causal,
    )
    return calc.calculate(dims)


def analyze_sad(
    subjective_weights: tuple[float, float, float, float],
    objective_weights: tuple[float, float, float, float],
) -> SADReport:
    """便捷执行 SAD 偏离度分析。

    Args:
        subjective_weights: 用户自定义的 (T, S, C, R) 权重
        objective_weights:  行为数据推导的 (T, S, C, R) 权重

    Returns:
        SADReport 分析报告
    """
    return get_analyzer().analyze(subjective_weights, objective_weights)


def infer_objective_weights(
    temporal_score: float,
    spatial_score: float,
    cognitive_score: float,
    causal_score: float,
) -> tuple[float, float, float, float]:
    """从四维分数反推客观权重分布。

    将各维度分数归一化，生成行为侧客观权重。
    原理：分数越高的维度，说明用户在实际行为中越倚重。

    Args:
        temporal_score ~ causal_score: 行为侧四维分数 (1-10)

    Returns:
        归一化后的客观权重 (T, S, C, R)
    """
    scores = [temporal_score, spatial_score, cognitive_score, causal_score]
    total = sum(scores)
    if total == 0:
        return DEFAULT_WEIGHTS
    return tuple(round(s / total, 4) for s in scores)
