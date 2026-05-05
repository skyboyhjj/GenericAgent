"""P忠恕权重偏离度分析器 (Score Anomaly Detection — SAD)

实现四维 P忠恕分数计算、主客观权重偏离度检测、霍金斯能量层级映射。

核心公式:
    P忠恕 = (T × w_T) + (S × w_S) + (C × w_C) + (R × w_R)
    其中 T=时位, S=宇位, C=识位, R=缘位, 各维度 1-10

SAD 偏离度:
    对比用户主观权重分布与行为客观权重分布，识别自我认知盲区。
    识位 SAD 高 → 用户可能高估理性; 缘位 SAD 低 → 用户清晰知道价值取向。

设计依据:
    - docs/个人地图能力集演化等5份设计书20260504.md §五
    - docs/五份设计文档_工作安排20260504.md §二·SAD
    - requst/道境知行系统_袭明每日镜鉴_完整资料.md §四
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from enum import Enum
from typing import Optional


# ===========================================================================
# 常量
# ===========================================================================

# 默认 P忠恕 权重 (T, S, C, R)
DEFAULT_WEIGHTS: tuple[float, float, float, float] = (0.20, 0.20, 0.30, 0.30)

# 偏离度等级阈值
DEVIATION_NORMAL: float = 0.10     # ≤10% 正常
DEVIATION_MILD: float = 0.20       # ≤20% 轻微
DEVIATION_MODERATE: float = 0.35   # ≤35% 中等
DEVIATION_SEVERE: float = float("inf")  # >35% 严重

# 维度名称
DIM_TEMPORAL = "时位"
DIM_SPATIAL = "宇位"
DIM_COGNITIVE = "识位"
DIM_CAUSAL = "缘位"

DIMENSION_NAMES: tuple[str, str, str, str] = (
    DIM_TEMPORAL, DIM_SPATIAL, DIM_COGNITIVE, DIM_CAUSAL,
)

# 高/低 SAD 的修行含义
SAD_INTERPRETATIONS: dict[str, dict[str, str]] = {
    DIM_TEMPORAL: {
        "high": "用户可能高估自己对时机的掌控力，逆势而动而不自知",
        "low": "用户清晰感知天时节奏，知进知退",
    },
    DIM_SPATIAL: {
        "high": "用户可能低估资源分配的公平性需求，占有囤积倾向未察觉",
        "low": "用户清楚自己的资源位置，损有余而补不足",
    },
    DIM_COGNITIVE: {
        "high": "用户可能高估自己的理性与认知清晰度，心随境转而不自知",
        "low": "用户清楚自己的认知状态，涤除玄鉴如明镜",
    },
    DIM_CAUSAL: {
        "high": "用户可能高估关系中的互惠程度，自我中心倾向未察觉",
        "low": "用户清晰知道自己的价值取向，常与善人",
    },
}


# ===========================================================================
# 数据模型
# ===========================================================================

class DeviationLevel(str, Enum):
    """偏离度等级"""
    NORMAL = "normal"
    MILD = "mild"
    MODERATE = "moderate"
    SEVERE = "severe"


@dataclass
class PZhongshuDimensions:
    """P忠恕 四维分数 (每维 1-10)"""

    temporal: float     # 时位: 知进知退 vs 逆势而动
    spatial: float       # 宇位: 损有余补不足 vs 占有囤积
    cognitive: float     # 识位: 涤除玄鉴 vs 心随境转
    causal: float        # 缘位: 常与善人 vs 自我中心

    def __post_init__(self):
        for name in ("temporal", "spatial", "cognitive", "causal"):
            v = getattr(self, name)
            if not (1.0 <= v <= 10.0):
                raise ValueError(f"{name} 必须在 [1.0, 10.0] 范围内，实际值: {v}")

    def to_tuple(self) -> tuple[float, float, float, float]:
        return (self.temporal, self.spatial, self.cognitive, self.causal)

    def as_dict(self) -> dict[str, float]:
        return {
            DIM_TEMPORAL: self.temporal,
            DIM_SPATIAL: self.spatial,
            DIM_COGNITIVE: self.cognitive,
            DIM_CAUSAL: self.causal,
        }


@dataclass
class PZhongshuScore:
    """P忠恕 综合分数及元信息"""

    total: float                          # P忠恕综合分 (1-10)
    dimensions: PZhongshuDimensions       # 四维原始分
    weights: tuple[float, float, float, float]  # 当前权重
    weighted_components: dict[str, float]       # 各维度加权分量
    hawkins_level: str = ""               # Hawkins能量等级
    hawkins_color: str = ""               # Hawkins颜色码

    def __post_init__(self):
        self.total = round(self.total, 4)


@dataclass
class PZhongshuConfig:
    """P忠恕 计算配置"""

    weights: tuple[float, float, float, float] = DEFAULT_WEIGHTS

    def __post_init__(self):
        s = sum(self.weights)
        if not math.isclose(s, 1.0, rel_tol=1e-6):
            raise ValueError(f"权重之和必须为 1.0，实际: {s}")
        for i, w in enumerate(self.weights):
            if w < 0:
                raise ValueError(f"权重[{i}] 不能为负数: {w}")


@dataclass
class SADConfig:
    """SAD 分析器配置"""

    mild_threshold: float = DEVIATION_MILD
    moderate_threshold: float = DEVIATION_MODERATE


@dataclass
class DimensionDeviation:
    """单一维度的偏离详情"""

    dimension: str                # 维度名称
    subjective_weight: float      # 用户主观权重
    objective_weight: float       # 行为客观权重
    deviation: float              # 绝对偏离值
    deviation_ratio: float        # 相对偏离比率
    level: DeviationLevel         # 偏离等级
    interpretation: str           # 修行含义解读


@dataclass
class SADReport:
    """SAD 偏离度分析报告"""

    overall_deviation: float                        # 整体偏离度 (0-1)
    level: DeviationLevel                           # 整体偏离等级
    dimension_details: dict[str, DimensionDeviation]  # 各维度详情
    primary_blindspot: Optional[str] = None          # 最大盲区维度
    summary: str = ""                                # 自然语言摘要
    suggestions: list[str] = field(default_factory=list)  # 修行建议

    def __post_init__(self):
        self.overall_deviation = round(self.overall_deviation, 4)

    def to_dict(self) -> dict:
        return {
            "overall_deviation": self.overall_deviation,
            "level": self.level.value,
            "primary_blindspot": self.primary_blindspot,
            "summary": self.summary,
            "suggestions": self.suggestions,
            "dimension_details": {
                k: {
                    "dimension": v.dimension,
                    "subjective_weight": v.subjective_weight,
                    "objective_weight": v.objective_weight,
                    "deviation": v.deviation,
                    "deviation_ratio": v.deviation_ratio,
                    "level": v.level.value,
                    "interpretation": v.interpretation,
                }
                for k, v in self.dimension_details.items()
            },
        }


# ===========================================================================
# P忠恕 分数计算器
# ===========================================================================

class PZhongshuScoreCalculator:
    """P忠恕 综合分数计算器。

    用法:
        dims = PZhongshuDimensions(temporal=7, spatial=6, cognitive=8, causal=5)
        calc = PZhongshuScoreCalculator()
        score = calc.calculate(dims)
        print(f"P忠恕 = {score.total}, Hawkins: {score.hawkins_level}")
    """

    def __init__(self, config: Optional[PZhongshuConfig] = None):
        self.config = config or PZhongshuConfig()

    # ------------------------------------------------------------------
    # 公共方法
    # ------------------------------------------------------------------

    def calculate(self, dimensions: PZhongshuDimensions) -> PZhongshuScore:
        """计算 P忠恕 综合分数。

        公式: Σ(dim_i × weight_i), i ∈ {T, S, C, R}
        """
        w = self.config.weights
        t, s, c, r = dimensions.to_tuple()

        w_t = t * w[0]
        w_s = s * w[1]
        w_c = c * w[2]
        w_r = r * w[3]

        total = w_t + w_s + w_c + w_r
        level, color = HawkinsEnergyMapper.map(total)

        return PZhongshuScore(
            total=min(total, 10.0),
            dimensions=dimensions,
            weights=w,
            weighted_components={
                DIM_TEMPORAL: round(w_t, 4),
                DIM_SPATIAL: round(w_s, 4),
                DIM_COGNITIVE: round(w_c, 4),
                DIM_CAUSAL: round(w_r, 4),
            },
            hawkins_level=level,
            hawkins_color=color,
        )

    def update_weights(self, new_weights: tuple[float, float, float, float]):
        """动态更新权重配置。"""
        self.config = PZhongshuConfig(weights=new_weights)


# ===========================================================================
# SAD 偏离度分析器
# ===========================================================================

class SADAnalyzer:
    """P忠恕 权重偏离度分析器 (Self-Awareness Deviation)。

    对比用户主观权重与行为客观权重，识别各维度的认知盲区。

    主观权重: 用户显式定义的各维度重要性
    客观权重: 从行为数据中统计推断的各维度实际权重

    用法:
        analyzer = SADAnalyzer()
        report = analyzer.analyze(
            subjective_weights=(0.15, 0.15, 0.40, 0.30),
            objective_weights=(0.22, 0.18, 0.25, 0.35),
        )
        print(f"主盲区: {report.primary_blindspot}")
        for dim, d in report.dimension_details.items():
            print(f"  {dim}: 偏离 {d.deviation_ratio:.1%} [{d.level.value}]")
    """

    def __init__(self, config: Optional[SADConfig] = None):
        self.config = config or SADConfig()

    # ------------------------------------------------------------------
    # 公共方法
    # ------------------------------------------------------------------

    def analyze(
        self,
        subjective_weights: tuple[float, float, float, float],
        objective_weights: tuple[float, float, float, float],
    ) -> SADReport:
        """执行完整的 SAD 分析。

        Args:
            subjective_weights: 用户自定义的 (T, S, C, R) 权重
            objective_weights:  行为数据推导的 (T, S, C, R) 权重

        Returns:
            SADReport 包含整体与各维度的偏离分析
        """
        self._validate_weights(subjective_weights, "主观权重")
        self._validate_weights(objective_weights, "客观权重")

        details = {}
        dim_deviations: list[float] = []

        for i, dim_name in enumerate(DIMENSION_NAMES):
            subj = subjective_weights[i]
            obj = objective_weights[i]
            dev = abs(subj - obj)

            # 相对偏离比率: 偏离 / max(主观,客观)，避免除零
            max_w = max(subj, obj, 1e-6)
            dev_ratio = dev / max_w
            dim_deviations.append(dev_ratio)

            level = self._classify(dev_ratio)
            interp = self._interpret(dim_name, dev_ratio)

            details[dim_name] = DimensionDeviation(
                dimension=dim_name,
                subjective_weight=round(subj, 4),
                objective_weight=round(obj, 4),
                deviation=round(dev, 4),
                deviation_ratio=round(dev_ratio, 4),
                level=level,
                interpretation=interp,
            )

        # 整体偏离度: 各维度偏离的平均值
        overall = sum(dim_deviations) / len(dim_deviations)
        overall_level = self._classify(overall)

        # 主盲区: 偏离最大的维度
        max_dim = max(dim_deviations)
        primary_idx = dim_deviations.index(max_dim)
        primary_name = DIMENSION_NAMES[primary_idx]

        # 生成摘要和建议
        summary = self._generate_summary(details, primary_name, overall)
        suggestions = self._generate_suggestions(details)

        return SADReport(
            overall_deviation=overall,
            level=overall_level,
            dimension_details=details,
            primary_blindspot=primary_name,
            summary=summary,
            suggestions=suggestions,
        )

    def quick_check(
        self,
        subjective_weights: tuple[float, float, float, float],
        objective_weights: tuple[float, float, float, float],
    ) -> bool:
        """快速检查是否存在显著偏离（任一维度超过中等阈值）。

        Returns:
            True 如果存在需要关注的偏离
        """
        for i in range(4):
            subj = subjective_weights[i]
            obj = objective_weights[i]
            max_w = max(subj, obj, 1e-6)
            if abs(subj - obj) / max_w > self.config.moderate_threshold:
                return True
        return False

    # ------------------------------------------------------------------
    # 内部方法
    # ------------------------------------------------------------------

    @staticmethod
    def _validate_weights(weights: tuple, label: str):
        if len(weights) != 4:
            raise ValueError(f"{label} 必须包含4个值，实际: {len(weights)}")
        s = sum(weights)
        if not math.isclose(s, 1.0, rel_tol=1e-4):
            raise ValueError(f"{label} 之和必须为 1.0，实际: {s}")

    def _classify(self, deviation_ratio: float) -> DeviationLevel:
        """根据偏离比率判定等级。"""
        if deviation_ratio <= DEVIATION_NORMAL:
            return DeviationLevel.NORMAL
        elif deviation_ratio <= DEVIATION_MILD:
            return DeviationLevel.MILD
        elif deviation_ratio <= DEVIATION_MODERATE:
            return DeviationLevel.MODERATE
        else:
            return DeviationLevel.SEVERE

    @staticmethod
    def _interpret(dim_name: str, dev_ratio: float) -> str:
        """根据偏离方向和程度生成修行解读。"""
        interp = SAD_INTERPRETATIONS.get(dim_name, {})
        if dev_ratio <= DEVIATION_MILD:
            return interp.get("low", "用户对该维度的自我认知与行为一致")
        else:
            return interp.get("high", "用户对该维度的自我认知与行为存在显著偏差")

    @staticmethod
    def _generate_summary(
        details: dict[str, DimensionDeviation],
        primary: str,
        overall: float,
    ) -> str:
        """生成自然语言摘要。"""
        level_desc = {
            DeviationLevel.NORMAL: "自我认知与行为高度一致，四维权重无显著偏离。",
            DeviationLevel.MILD: "存在轻微认知偏差，整体尚在健康范围内。",
            DeviationLevel.MODERATE: "部分维度认知偏差较明显，建议关注。",
            DeviationLevel.SEVERE: "存在显著认知盲区，某维度自我认知与行为严重偏离。",
        }
        primary_detail = details[primary]
        base = level_desc.get(primary_detail.level, "")
        return (
            f"{base} 主要盲区在「{primary}」维度"
            f"（偏离 {primary_detail.deviation_ratio:.1%}）。"
        )

    @staticmethod
    def _generate_suggestions(
        details: dict[str, DimensionDeviation],
    ) -> list[str]:
        """生成修行建议。"""
        suggestions: list[str] = []
        for dim_name, d in details.items():
            if d.level in (DeviationLevel.MODERATE, DeviationLevel.SEVERE):
                if d.subjective_weight > d.objective_weight:
                    suggestions.append(
                        f"「{dim_name}」：你比实际行为更看重此维度，"
                        f"可以反思是否高估了它的重要性"
                    )
                else:
                    suggestions.append(
                        f"「{dim_name}」：你的行为比你自认为的更倚重此维度，"
                        f"它可能是你未被察觉的力量来源"
                    )
        if not suggestions:
            suggestions.append("四维平衡良好，无需特别调整。保持当前觉察即可。")
        return suggestions


# ===========================================================================
# 霍金斯能量层级映射器
# ===========================================================================

class HawkinsEnergyMapper:
    """P忠恕分数 → Hawkins 能量层级映射。"""

    # (下限, 上限, 等级名, 颜色)
    _MAP: tuple[tuple[float, float, str, str], ...] = (
        (0.0,  3.0,  "恐惧",     "#FF6B6B"),
        (3.0,  5.0,  "欲望",     "#FFA500"),
        (5.0,  6.0,  "勇气",     "#FFD700"),
        (6.0,  7.0,  "中立",     "#90EE90"),
        (7.0,  8.0,  "主动",     "#87CEEB"),
        (8.0,  9.0,  "宽容",     "#DDA0DD"),
        (9.0, 10.01, "平和",     "#98FB98"),
    )

    @classmethod
    def map(cls, score: float) -> tuple[str, str]:
        """映射 P忠恕 分数至 Hawkins 能量等级。

        Returns:
            (等级名称, 颜色码)
        """
        score = max(0.0, min(10.0, score))
        for lo, hi, name, color in cls._MAP:
            if lo <= score < hi:
                return name, color
        return "平和", "#98FB98"

    @classmethod
    def get_level_index(cls, level_name: str) -> int:
        """获取能量等级的序号 (0-based)。"""
        for i, (_, _, name, _) in enumerate(cls._MAP):
            if name == level_name:
                return i
        return -1

    @classmethod
    def all_levels(cls) -> list[dict]:
        """返回所有能量等级信息。"""
        return [
            {"name": name, "range": f"{lo}-{hi}", "color": color}
            for lo, hi, name, color in cls._MAP
        ]
