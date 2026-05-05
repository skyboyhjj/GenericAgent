"""Algorithms — 慧惠核心算法模块。

提供 P忠恕分数计算、SAD 偏离度分析、能量层级映射等核心算法。
"""

from algorithms.pzhongshu_analyzer import (
    PZhongshuDimensions,
    PZhongshuScore,
    PZhongshuConfig,
    SADReport,
    SADConfig,
    PZhongshuScoreCalculator,
    SADAnalyzer,
    HawkinsEnergyMapper,
    DEVIATION_NORMAL,
    DEVIATION_MILD,
    DEVIATION_MODERATE,
    DEVIATION_SEVERE,
)
from algorithms.integration import (
    get_calculator,
    get_analyzer,
    calculate_pzhongshu,
    analyze_sad,
    infer_objective_weights,
)

__all__ = [
    "PZhongshuDimensions",
    "PZhongshuScore",
    "PZhongshuConfig",
    "SADReport",
    "SADConfig",
    "PZhongshuScoreCalculator",
    "SADAnalyzer",
    "HawkinsEnergyMapper",
    "DEVIATION_NORMAL",
    "DEVIATION_MILD",
    "DEVIATION_MODERATE",
    "DEVIATION_SEVERE",
    "get_calculator",
    "get_analyzer",
    "calculate_pzhongshu",
    "analyze_sad",
    "infer_objective_weights",
]
