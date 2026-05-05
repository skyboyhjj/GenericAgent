"""
RootAuditor — 归根·审计：五行流转总调度器

设计依据：
  - 《慧惠五行流转引擎-方案设计书 v1.0》第六·4节
  - 核心理念："静为躁君"——在后台安静地维护技能生态健康
  - "动善时"——按周期触发，不频繁打扰

RootAuditor 不修改 GA 核心代码，通过调度已有的五行模块实现技能生命周期自动化。
"""

import json
import os
import random
import threading
from pathlib import Path
from datetime import datetime, timezone
from dataclasses import dataclass, field, asdict
from typing import List, Optional, Dict, Any

# ---------------------------------------------------------------------------
# 路径常量
# ---------------------------------------------------------------------------
ROOT = Path(__file__).resolve().parent.parent
MEMORY_DIR = ROOT / "memory"
LAST_AUDIT_FILE = MEMORY_DIR / "last_audit.txt"
AUDIT_LOG_FILE = MEMORY_DIR / "audit_log.json"

# 审计周期常量
PERIOD_MANUAL = "manual"
PERIOD_DAILY = "daily"
PERIOD_WEEKLY = "weekly"
PERIOD_MONTHLY = "monthly"

# 审计周期对应的检查间隔（小时）
PERIOD_INTERVALS = {
    PERIOD_DAILY: 24,
    PERIOD_WEEKLY: 168,
    PERIOD_MONTHLY: 720,
}


# ===========================================================================
# 数据结构
# ===========================================================================

@dataclass
class AuditReport:
    """一次审计的报告"""
    period: str                         # "manual" / "daily" / "weekly" / "monthly"
    timestamp: str                      # ISO 8601 时间戳
    actions: list = field(default_factory=list)     # 已执行的动作（归档等）
    warnings: list = field(default_factory=list)    # 发现的警告
    active_count: int = 0               # 当前活跃技能数
    archived_count: int = 0             # 当前已归档技能数
    health_trend: dict = field(default_factory=dict)  # 健康度趋势（monthly 时填充）

    def to_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, d: dict) -> "AuditReport":
        return cls(
            period=d.get("period", PERIOD_MANUAL),
            timestamp=d.get("timestamp", ""),
            actions=d.get("actions", []),
            warnings=d.get("warnings", []),
            active_count=d.get("active_count", 0),
            archived_count=d.get("archived_count", 0),
            health_trend=d.get("health_trend", {}),
        )


# ===========================================================================
# RootAuditor
# ===========================================================================

class RootAuditor:
    """
    归根·审计：五行流转总调度器。

    职责：
    - 管理所有五行模块的生命周期
    - 按周期自动触发审计动作
    - 生成审计报告并持久化
    - 静默执行，不阻塞用户对话

    设计原则：
    - "静为躁君"：在后台安静地维护技能生态健康
    - "动善时"：按周期触发，不频繁打扰
    """

    def __init__(self, registry,
                 wood_grower=None,
                 metal_restrainer=None,
                 fire_transformer=None,
                 water_adapter=None,
                 earth_connector=None):
        """
        初始化五行引擎总调度器。

        Args:
            registry: SkillRegistry 实例（必需）
            wood_grower: WoodGrower 实例（可选，不传则使用默认配置）
            metal_restrainer: MetalRestrainer 实例（可选，不传则使用默认配置）
            fire_transformer: 火·化模块（预留，第二期）
            water_adapter: 水·变模块（预留/占位）
            earth_connector: 土·通模块（预留/占位）
        """
        self.registry = registry

        # 五色模块
        self.wood_grower = wood_grower          # 木·生
        self.metal_restrainer = metal_restrainer  # 金·克
        self.fire_transformer = fire_transformer   # 火·化（预留）
        self.water_adapter = water_adapter         # 水·变（占位）
        self.earth_connector = earth_connector     # 土·通（占位）

        # 线程锁，防止并发审计
        self._audit_lock = threading.Lock()
        self._last_audit_time: Optional[str] = None

        # 自动加载上次审计时间
        self._load_last_audit_time()

    # ------------------------------------------------------------------
    # 审计调度
    # ------------------------------------------------------------------

    def audit(self, period: str = PERIOD_MANUAL) -> AuditReport:
        """
        执行一轮审计。

        Args:
            period: 审计周期
              - "manual"：手动触发，执行全部审计动作
              - "daily"：每日审计，仅执行金·克评估 + 归档
              - "weekly"：每周审计，daily + 产物质量抽检
              - "monthly"：每月审计，weekly + 健康度趋势分析 + 占位模块

        Returns:
            AuditReport 包含本轮审计的全部动作摘要。
        """
        with self._audit_lock:
            report = self._execute_audit(period)
            self._save_audit_log(report)
            self._update_last_audit_time(report.timestamp)
            return report

    def audit_async(self, period: str = PERIOD_DAILY, callback=None) -> None:
        """
        在后台线程中异步执行审计，不阻塞调用方。

        Args:
            period: 审计周期（同 audit()）
            callback: 审计完成后的回调函数，接收 AuditReport 参数
        """
        def _run():
            try:
                report = self.audit(period)
                if callback:
                    callback(report)
            except Exception as e:
                # 审计失败不应导致主程序崩溃
                import traceback
                traceback.print_exc()

        thread = threading.Thread(
            target=_run, daemon=True, name="root-auditor")
        thread.start()

    # ------------------------------------------------------------------
    # 查询
    # ------------------------------------------------------------------

    def get_last_audit_time(self) -> Optional[str]:
        """
        返回上次审计的 ISO 8601 时间戳。

        Returns:
            时间字符串，从未审计则返回 None。
        """
        self._load_last_audit_time()
        return self._last_audit_time

    def get_audit_history(self, limit: int = 10) -> list:
        """
        返回最近 N 次审计记录的摘要列表。

        Args:
            limit: 返回的最大记录数

        Returns:
            List[dict]，每项为审计记录摘要
        """
        entries = self._load_audit_log()
        if not entries:
            return []
        # 按时间倒序，取最近 limit 条
        entries.sort(key=lambda e: e.get("timestamp", ""), reverse=True)
        return entries[:limit]

    def is_audit_due(self, period: str = PERIOD_DAILY) -> bool:
        """
        检查是否到了指定的审计周期。

        Args:
            period: 审计周期（"daily" / "weekly" / "monthly"）

        Returns:
            True 表示应执行审计，False 表示尚未到期
        """
        last = self.get_last_audit_time()
        if last is None:
            return True  # 从未审计，应立即执行

        interval_hours = PERIOD_INTERVALS.get(period, 24)
        try:
            last_dt = datetime.fromisoformat(last.replace("Z", "+00:00"))
            if last_dt.tzinfo is None:
                last_dt = last_dt.replace(tzinfo=timezone.utc)
            elapsed = (datetime.now(timezone.utc) -
                       last_dt).total_seconds() / 3600
            return elapsed >= interval_hours
        except (ValueError, TypeError):
            return True  # 解析失败，保守起见应审计

    # ------------------------------------------------------------------
    # 内部：审计执行
    # ------------------------------------------------------------------

    def _execute_audit(self, period: str) -> AuditReport:
        """
        执行审计的核心逻辑。
        """
        actions = []
        warnings = []
        now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S")

        # 全部周期都执行：金·克健康度评估 + 归档
        if period in (PERIOD_DAILY, PERIOD_WEEKLY, PERIOD_MONTHLY, PERIOD_MANUAL):
            if self.metal_restrainer and self.metal_restrainer.config.enabled:
                reports = self.metal_restrainer.evaluate_all()
                for r in reports:
                    if r.recommendation == "archive":
                        archived = self.metal_restrainer.archive(r.skill_id)
                        action_entry = {
                            "type": "archive",
                            "skill_id": r.skill_id,
                            "health": round(r.health_score, 2),
                            "reason": r.reason,
                        }
                        if archived:
                            actions.append(action_entry)
                    elif r.recommendation == "warn":
                        warnings.append({
                            "type": "low_health",
                            "skill_id": r.skill_id,
                            "health": round(r.health_score, 2),
                        })

        # 每周/每月/手动：产物质量抽检（随机 20%）
        if period in (PERIOD_WEEKLY, PERIOD_MONTHLY, PERIOD_MANUAL):
            if self.wood_grower and self.wood_grower.config.enabled:
                active_skills = self.registry.get_active_skills()
                if active_skills:
                    sample_size = max(1, len(active_skills) // 5)
                    sampled = random.sample(
                        active_skills,
                        min(sample_size, len(active_skills))
                    )
                    for skill in sampled:
                        sop_path = ROOT / skill.file
                        if sop_path.exists():
                            result = self.wood_grower.post_validate(
                                str(sop_path))
                            if not result.passed:
                                warnings.append({
                                    "type": "quality_issue",
                                    "skill_id": skill.name,
                                    "detail": str(result.violations)[:200],
                                })

        # 每月/手动：健康度趋势分析
        if period in (PERIOD_MONTHLY, PERIOD_MANUAL):
            health_trend = self._compute_health_trend()
        else:
            health_trend = {}

        # 手动：额外调用占位模块
        if period == PERIOD_MANUAL:
            if self.water_adapter:
                try:
                    result = self.water_adapter.check_and_update(
                        "__audit_test__")
                    actions.append({
                        "type": "water_check",
                        "module": "water_adapter",
                        "result": result,
                    })
                except Exception:
                    pass
            if self.earth_connector:
                try:
                    result = self.earth_connector.check_compatibility(
                        "__audit_test__")
                    actions.append({
                        "type": "earth_check",
                        "module": "earth_connector",
                        "result": result,
                    })
                except Exception:
                    pass

        # 统计
        active_count = len(self.registry.get_active_skills())
        archived_count = len(
            self.metal_restrainer.get_archived_skills()) if self.metal_restrainer else 0

        return AuditReport(
            period=period,
            timestamp=now,
            actions=actions,
            warnings=warnings,
            active_count=active_count,
            archived_count=archived_count,
            health_trend=health_trend,
        )

    def _compute_health_trend(self) -> dict:
        """
        计算当前健康度分布趋势。

        Returns:
            dict 含 active_count, avg_health, low_health_count, high_health_count
        """
        if not self.metal_restrainer or not self.metal_restrainer.config.enabled:
            return {}

        reports = self.metal_restrainer.evaluate_all()
        if not reports:
            return {"active_count": 0, "avg_health": 0.0,
                    "low_health_count": 0, "high_health_count": 0}

        scores = [r.health_score for r in reports]
        avg_health = round(sum(scores) / len(scores), 4)
        low_count = sum(1 for s in scores if s < 0.5)
        high_count = sum(1 for s in scores if s >= 0.7)

        return {
            "active_count": len(reports),
            "avg_health": avg_health,
            "low_health_count": low_count,
            "high_health_count": high_count,
        }

    # ------------------------------------------------------------------
    # 内部：持久化
    # ------------------------------------------------------------------

    def _save_audit_log(self, report: AuditReport) -> None:
        """
        将审计报告追加到 memory/audit_log.json。
        """
        MEMORY_DIR.mkdir(parents=True, exist_ok=True)

        entries = self._load_audit_log()
        entries.append(report.to_dict())

        # 限制日志条数（保留最近 200 条）
        if len(entries) > 200:
            entries = entries[-200:]

        with open(AUDIT_LOG_FILE, "w", encoding="utf-8") as f:
            json.dump(entries, f, ensure_ascii=False, indent=2)

    def _load_audit_log(self) -> list:
        """
        从 memory/audit_log.json 加载审计日志。

        Returns:
            List[dict]，文件不存在或损坏时返回空列表
        """
        if not AUDIT_LOG_FILE.exists():
            return []
        try:
            with open(AUDIT_LOG_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
            if isinstance(data, list):
                return data
            return []
        except (json.JSONDecodeError, OSError):
            return []

    def _update_last_audit_time(self, timestamp: str) -> None:
        """
        更新上次审计时间到 memory/last_audit.txt。
        """
        MEMORY_DIR.mkdir(parents=True, exist_ok=True)
        self._last_audit_time = timestamp
        with open(LAST_AUDIT_FILE, "w", encoding="utf-8") as f:
            f.write(timestamp)

    def _load_last_audit_time(self) -> None:
        """
        从 memory/last_audit.txt 加载上次审计时间。
        """
        if LAST_AUDIT_FILE.exists():
            try:
                self._last_audit_time = LAST_AUDIT_FILE.read_text(
                    encoding="utf-8").strip()
            except OSError:
                self._last_audit_time = None
        else:
            self._last_audit_time = None
