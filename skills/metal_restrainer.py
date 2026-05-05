"""
MetalRestrainer — 金·克修剪：健康度评估 + 自动归档

设计依据：
  - 《慧惠五行流转引擎-方案设计书 v1.0》第六·3节
  - 核心理念："为道日损"——修剪不是删除，而是归档
  - L0 公理2：已验证数据不可删改（只归档，不物理删除）

MetalRestrainer 不修改 GA 核心代码，通过 SkillRegistry 读取和更新技能元数据。
集成到 AgentLoop 的任务留到 S3-5（InternalAuditor）处理。
"""

import math
import os
from pathlib import Path
from datetime import datetime, timezone
from dataclasses import dataclass, field
from typing import List, Optional, Dict, Any

from .skill_registry import SkillRegistry, SkillMeta, STATUS_ACTIVE, STATUS_ARCHIVED

# ---------------------------------------------------------------------------
# 路径常量
# ---------------------------------------------------------------------------
ROOT = Path(__file__).resolve().parent.parent


# ===========================================================================
# 配置与数据结构
# ===========================================================================

@dataclass
class MetalRestrainerConfig:
    """金·克修剪的配置"""
    enabled: bool = True                    # 总开关
    archive_threshold: float = 0.3          # 健康度低于此值触发归档
    warning_threshold: float = 0.5          # 健康度低于此值仅警告
    freshness_decay: float = 0.02           # 新鲜度衰减率 λ（半衰期约 35 天）
    weights: tuple = (0.4, 0.4, 0.2)       # (新鲜度权重, 可靠性权重, 复杂度权重)
    archive_dir: str = "memory/archive"     # 归档目录（预留，S3-3 不操作文件）
    whitelist: tuple = (                    # 白名单：永不被修剪的核心技能
        "memory_management_sop",
    )
    dry_run: bool = False                   # 仅评估不执行（用于预览）


@dataclass
class HealthReport:
    """技能健康度评估报告"""
    skill_id: str                           # 技能标识
    health_score: float                     # 综合健康度 (0-1)
    freshness: float                        # 新鲜度得分
    reliability: float                      # 可靠性得分
    complexity_bonus: float                 # 复杂度加分
    days_since_last_use: int                # 距上次使用天数（-1 表示从未使用）
    use_count: int                          # 被复用次数
    success_rate: float                     # 成功率
    recommendation: str                     # 建议："archive" / "warn" / "keep"
    reason: str                             # 建议理由


# ===========================================================================
# MetalRestrainer
# ===========================================================================

class MetalRestrainer:
    """
    金·克修剪：评估技能健康度，自动归档低健康度技能。

    设计原则：
    - "为道日损"：修剪不是删除，而是归档——可恢复
    - 懒惰归档：只在健康度明确低于阈值时才行动
    - 白名单保护：核心技能永不修剪

    供后续集成使用的能力（S3-5）：
    - evaluate_all() → 获取所有技能的评估报告
    - archive() / restore() → 单个技能的归档/恢复
    - get_archived_skills() → 查看归档状态
    """

    def __init__(self, registry: SkillRegistry, config: Optional[MetalRestrainerConfig] = None):
        """
        初始化 MetalRestrainer。

        Args:
            registry: SkillRegistry 实例（用于读取和更新技能元数据）
            config: MetalRestrainer 配置，为 None 时使用默认配置
        """
        self._registry = registry
        self.config = config if config is not None else MetalRestrainerConfig()

    # ------------------------------------------------------------------
    # 健康度计算
    # ------------------------------------------------------------------

    def calculate_health(self, meta: SkillMeta) -> tuple:
        """
        计算技能的健康度。

        公式：
          health = w1 × freshness + w2 × reliability + w3 × complexity_bonus

        Args:
            meta: 技能元数据

        Returns:
            (health_score, freshness, reliability, complexity_bonus) 元组
        """
        w1, w2, w3 = self.config.weights
        lam = self.config.freshness_decay

        # ── 新鲜度 ──
        use_count = meta.use_count

        if use_count == 0:
            # 从未复用：新鲜度满分（尚无老化数据）
            freshness = 1.0
            days_since = -1  # 标记为"从未使用"
        else:
            # 计算距上次使用天数
            last_used_str = meta.last_used
            if last_used_str:
                days_since = self._days_since(last_used_str)
            else:
                # last_used 为空时使用创建日期
                days_since = self._days_since(
                    meta.created_at) if meta.created_at else 0

            freshness = math.exp(-lam * max(days_since, 0))
            freshness = round(freshness, 4)

        # ── 可靠性 ──
        if use_count == 0 or meta.success_rate is None:
            reliability = 0.5  # 中性默认（无使用数据）
        else:
            reliability = meta.success_rate

        # ── 复杂度加分 ──
        tool_count = getattr(meta, 'tool_count', 0)
        complexity_bonus = min(tool_count / 5, 1.0)

        # ── 综合健康度 ──
        health = w1 * freshness + w2 * reliability + w3 * complexity_bonus
        health = round(health, 4)

        return health, freshness, reliability, complexity_bonus

    # ------------------------------------------------------------------
    # 评估
    # ------------------------------------------------------------------

    def evaluate(self, skill_id: str) -> HealthReport:
        """
        评估单个技能的健康度。

        Args:
            skill_id: 技能标识符

        Returns:
            HealthReport 含评分和细分维度。
            若技能不存在，返回 health_score=0.0 且 recommendation="not_found"。
        """
        meta = self._registry.get(skill_id)
        if not meta:
            return HealthReport(
                skill_id=skill_id,
                health_score=0.0,
                freshness=0.0,
                reliability=0.0,
                complexity_bonus=0.0,
                days_since_last_use=-1,
                use_count=0,
                success_rate=0.0,
                recommendation="not_found",
                reason=f"Skill '{skill_id}' not found in registry",
            )

        # 白名单保护：始终满分
        if skill_id in self.config.whitelist:
            return HealthReport(
                skill_id=skill_id,
                health_score=1.0,
                freshness=1.0,
                reliability=1.0,
                complexity_bonus=1.0,
                days_since_last_use=0,
                use_count=meta.use_count,
                success_rate=meta.success_rate,
                recommendation="keep",
                reason="Whitelisted core skill — never pruned",
            )

        # 计算健康度
        health, freshness, reliability, complexity = self.calculate_health(
            meta)

        # 计算 days_since_last_use 用于报告
        if meta.use_count == 0:
            days_since = -1
        elif meta.last_used:
            days_since = self._days_since(meta.last_used)
        else:
            days_since = self._days_since(
                meta.created_at) if meta.created_at else 0

        # 确定建议
        if health < self.config.archive_threshold:
            recommendation = "archive"
            reason = (f"health_score ({health:.3f}) < archive_threshold "
                      f"({self.config.archive_threshold})")
        elif health < self.config.warning_threshold:
            recommendation = "warn"
            reason = (f"health_score ({health:.3f}) < warning_threshold "
                      f"({self.config.warning_threshold})")
        else:
            recommendation = "keep"
            reason = f"health_score ({health:.3f}) >= warning_threshold"

        return HealthReport(
            skill_id=skill_id,
            health_score=health,
            freshness=freshness,
            reliability=reliability,
            complexity_bonus=complexity,
            days_since_last_use=days_since,
            use_count=meta.use_count,
            success_rate=meta.success_rate,
            recommendation=recommendation,
            reason=reason,
        )

    def evaluate_all(self) -> list:
        """
        评估所有活跃技能的健康度。

        跳过白名单技能。
        返回按健康度升序排列的报告列表（最危险的排最前）。

        Returns:
            List[HealthReport]，若 config.enabled=False 返回空列表
        """
        if not self.config.enabled:
            return []

        active_skills = self._registry.get_active_skills()
        reports = []

        for meta in active_skills:
            # 跳过白名单
            if meta.name in self.config.whitelist:
                continue
            report = self.evaluate(meta.name)
            reports.append(report)

        # 按健康度升序排列（最危险排最前）
        reports.sort(key=lambda r: r.health_score)
        return reports

    # ------------------------------------------------------------------
    # 归档与恢复
    # ------------------------------------------------------------------

    def archive(self, skill_id: str) -> bool:
        """
        归档单个技能。

        1. 检查白名单（白名单技能拒绝归档）
        2. 检查技能是否存在且为 active 状态
        3. 若 dry_run=True，仅返回 True 不实际归档
        4. 调用 registry.archive() 将 status 改为 archived

        Args:
            skill_id: 技能标识符

        Returns:
            True 表示已归档（或 dry_run 下将会归档），
            False 表示：
              - 技能在白名单中
              - 技能不存在
              - 技能已是归档状态
        """
        # 白名单保护
        if skill_id in self.config.whitelist:
            return False

        # 检查技能是否存在
        meta = self._registry.get(skill_id)
        if not meta:
            return False

        # 检查是否已是归档状态
        if meta.status == STATUS_ARCHIVED:
            return False

        # 干运行模式：不实际归档
        if self.config.dry_run:
            return True

        # 执行归档
        try:
            report = self.evaluate(skill_id)
            self._registry.archive(skill_id, reason=report.reason)
            return True
        except KeyError:
            return False

    def restore(self, skill_id: str) -> bool:
        """
        恢复已归档的技能。

        1. 在 registry 中将 status 改回 active

        Args:
            skill_id: 技能标识符

        Returns:
            True 表示已恢复，
            False 表示技能不存在或不是归档状态
        """
        meta = self._registry.get(skill_id)
        if not meta:
            return False
        if meta.status != STATUS_ARCHIVED:
            return False
        return self._registry.recover(skill_id)

    def get_archived_skills(self) -> list:
        """
        列出所有已归档的技能及其归档原因和健康度。

        Returns:
            List[dict]，每项含 skill_id, health_score, reason, status
        """
        archived = self._registry.get_archived_skills()
        result = []
        for meta in archived:
            report = self.evaluate(meta.name)
            result.append({
                "skill_id": meta.name,
                "health_score": report.health_score,
                "reason": report.reason,
                "status": meta.status,
            })
        return result

    # ------------------------------------------------------------------
    # 内部辅助
    # ------------------------------------------------------------------

    def _days_since(self, iso_str: str) -> int:
        """
        计算从给定 ISO 时间字符串到现在的天数。

        Args:
            iso_str: ISO 格式时间字符串（如 "2026-05-01T10:00:00"）

        Returns:
            天数（整数），解析失败返回 0
        """
        try:
            # 处理时区后缀
            normalized = iso_str.replace("Z", "+00:00")
            dt = datetime.fromisoformat(normalized)
            # 若缺少时区信息，视为 UTC
            if dt.tzinfo is None:
                dt = dt.replace(tzinfo=timezone.utc)
            now = datetime.now(timezone.utc)
            return (now - dt).days
        except (ValueError, TypeError):
            return 0
