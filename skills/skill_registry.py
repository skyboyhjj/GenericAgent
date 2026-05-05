"""
SkillRegistry — 技能注册表 + 语义化版本管理系统

SkillRegistry 作为五行流转的中枢，提供统一的技能元数据管理：
  - 木·生: register() → 初始版本 1.0.0
  - 水·变: bump_version() → 语义化版本递增
  - 火·化: merge 时设置 merged_from
  - 金·克: archive() / deprecate()
  - 土·通: environment 元数据用于跨环境迁移

存储格式: memory/skill_registry.yaml + memory/versions/
"""

import os
import re
import json
import shutil
import logging
from pathlib import Path
from datetime import datetime, timezone
from dataclasses import dataclass, field, asdict
from typing import List, Optional, Dict, Any
from collections import defaultdict

import yaml

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# 路径常量
# ---------------------------------------------------------------------------
ROOT = Path(__file__).resolve().parent.parent
MEMORY_DIR = ROOT / "memory"
VERSIONS_DIR = MEMORY_DIR / "versions"
DEFAULT_REGISTRY_PATH = MEMORY_DIR / "skill_registry.yaml"

# 技能状态枚举
STATUS_ACTIVE = "active"
STATUS_ARCHIVED = "archived"
STATUS_DEPRECATED = "deprecated"

# 版本变更原因枚举
REASON_INITIAL = "initial"
REASON_UPDATED = "updated"
REASON_MERGED = "merged"
REASON_RECOVERED = "recovered"

# 版本号变更类型
BUMP_PATCH = "patch"    # 0.0.1
BUMP_MINOR = "minor"    # 0.1.0
BUMP_MAJOR = "major"    # 1.0.0

# 历史版本 prun 阈值
MAX_VERSION_SNAPSHOTS = 10


# ===========================================================================
# 数据结构
# ===========================================================================

@dataclass
class EnvironmentMeta:
    """技能所处的环境信息（用于土·通迁移）"""
    os: str = ""
    python_version: str = ""
    packages: List[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {"os": self.os, "python_version": self.python_version, "packages": self.packages}

    @classmethod
    def from_dict(cls, d: dict) -> "EnvironmentMeta":
        return cls(
            os=d.get("os", ""),
            python_version=d.get("python_version", ""),
            packages=d.get("packages", []),
        )


@dataclass
class VersionRecord:
    """版本历史中的一条记录"""
    version: str                    # 语义化版本号 e.g. "1.0.0"
    created_at: str                 # ISO 时间戳
    reason: str                     # initial / updated / merged / recovered
    snapshot_file: str = ""        # 快照文件相对路径

    def to_dict(self) -> dict:
        return {
            "version": self.version,
            "created_at": self.created_at,
            "reason": self.reason,
            "snapshot_file": self.snapshot_file,
        }

    @classmethod
    def from_dict(cls, d: dict) -> "VersionRecord":
        return cls(
            version=d.get("version", "0.0.0"),
            created_at=d.get("created_at", ""),
            reason=d.get("reason", REASON_INITIAL),
            snapshot_file=d.get("snapshot_file", ""),
        )


@dataclass
class SkillMeta:
    """技能元数据——注册表的原子单元"""
    name: str                       # 技能唯一标识符
    file: str                       # GA 已有 SOP 文件路径（相对于项目根）
    version: str = "1.0.0"         # 当前语义化版本号
    version_history: List[VersionRecord] = field(default_factory=list)
    status: str = STATUS_ACTIVE     # active / archived / deprecated
    created_at: str = ""
    last_used: str = ""
    use_count: int = 0
    success_rate: float = 1.0       # 成功率 (0.0 ~ 1.0)
    dependencies: List[str] = field(default_factory=list)
    similar_to: List[str] = field(default_factory=list)
    merged_from: List[str] = field(default_factory=list)
    environment: EnvironmentMeta = field(default_factory=EnvironmentMeta)
    health_score: float = 1.0       # 健康评分 (0.0 ~ 1.0)
    last_health_check: str = ""
    pillar_tag: str = ""            # 四象限标签: 自爱/尽责/贡献/传承
    emotional_value: float = 0.5    # 情感价值评分 (0.0~1.0)，默认 0.5
    whitelist: bool = False         # 白名单标记
    whitelist_reason: str = ""      # 白名单原因

    def to_dict(self) -> dict:
        return {
            "name": self.name,
            "file": self.file,
            "version": self.version,
            "version_history": [vh.to_dict() for vh in self.version_history],
            "status": self.status,
            "created_at": self.created_at,
            "last_used": self.last_used,
            "use_count": self.use_count,
            "success_rate": self.success_rate,
            "dependencies": self.dependencies,
            "similar_to": self.similar_to,
            "merged_from": self.merged_from,
            "environment": self.environment.to_dict(),
            "health_score": self.health_score,
            "last_health_check": self.last_health_check,
            "pillar_tag": self.pillar_tag,
            "emotional_value": self.emotional_value,
            "whitelist": self.whitelist,
            "whitelist_reason": self.whitelist_reason,
        }

    @classmethod
    def from_dict(cls, d: dict) -> "SkillMeta":
        vh_raw = d.get("version_history", [])
        version_history = [VersionRecord.from_dict(v) for v in vh_raw]
        env_raw = d.get("environment", {})
        return cls(
            name=d.get("name", ""),
            file=d.get("file", ""),
            version=d.get("version", "1.0.0"),
            version_history=version_history,
            status=d.get("status", STATUS_ACTIVE),
            created_at=d.get("created_at", ""),
            last_used=d.get("last_used", ""),
            use_count=d.get("use_count", 0),
            success_rate=d.get("success_rate", 1.0),
            dependencies=d.get("dependencies", []),
            similar_to=d.get("similar_to", []),
            merged_from=d.get("merged_from", []),
            environment=EnvironmentMeta.from_dict(env_raw),
            health_score=d.get("health_score", 1.0),
            last_health_check=d.get("last_health_check", ""),
            pillar_tag=d.get("pillar_tag", ""),
            emotional_value=d.get("emotional_value", 0.5),
            whitelist=d.get("whitelist", False),
            whitelist_reason=d.get("whitelist_reason", ""),
        )


# ===========================================================================
# 语义化版本管理器
# ===========================================================================

class SkillVersionManager:
    """语义化版本管理器 —— 水·变 的执行者

    路径策略：
      - 若传入 registry_path，则从 registry_path 动态推导
        versions_dir = registry_path.parent / "versions"
      - 否则回退到模块级常量 VERSIONS_DIR（向后兼容）
      - ROOT 始终使用模块级常量（测试可通过模块 hack 覆盖）
    """

    SEMVER_RE = re.compile(r"^(\d+)\.(\d+)\.(\d+)$")

    def __init__(self, registry_path: Optional[str] = None):
        if registry_path:
            rp = Path(registry_path)
            self._versions_dir = rp.resolve().parent / "versions"
        else:
            self._versions_dir = VERSIONS_DIR

    @staticmethod
    def parse(version: str) -> tuple:
        """解析版本号字符串为 (major, minor, patch) 元组"""
        m = SkillVersionManager.SEMVER_RE.match(version)
        if not m:
            raise ValueError(f"Invalid semver: {version!r}")
        return int(m.group(1)), int(m.group(2)), int(m.group(3))

    @staticmethod
    def to_str(major: int, minor: int, patch: int) -> str:
        return f"{major}.{minor}.{patch}"

    @staticmethod
    def bump(version: str, bump_type: str) -> str:
        """递增语义化版本号"""
        major, minor, patch = SkillVersionManager.parse(version)
        if bump_type == BUMP_MAJOR:
            return SkillVersionManager.to_str(major + 1, 0, 0)
        elif bump_type == BUMP_MINOR:
            return SkillVersionManager.to_str(major, minor + 1, 0)
        elif bump_type == BUMP_PATCH:
            return SkillVersionManager.to_str(major, minor, patch + 1)
        else:
            raise ValueError(f"Unknown bump_type: {bump_type!r}")

    @staticmethod
    def compare(v1: str, v2: str) -> int:
        """比较两个版本号：v1 < v2 → -1, v1 == v2 → 0, v1 > v2 → 1"""
        a = SkillVersionManager.parse(v1)
        b = SkillVersionManager.parse(v2)
        if a < b:
            return -1
        elif a > b:
            return 1
        return 0

    def create_snapshot(self, skill_name: str, version: str,
                        sop_file_path: str) -> str:
        """
        为指定版本创建快照文件。

        快照文件保存在 self._versions_dir（由 registry_path 动态推导）
        目录下，文件命名格式为 {skill_name}_v{version}.md。

        返回快照文件的相对路径（相对于项目根目录）。
        """
        self._versions_dir.mkdir(parents=True, exist_ok=True)

        snapshot_name = f"{skill_name}_v{version}.md"
        snapshot_path = self._versions_dir / snapshot_name

        # 复制源文件内容到快照
        source = ROOT / sop_file_path
        if source.exists():
            content = source.read_text(encoding="utf-8", errors="replace")
            snapshot_path.write_text(content, encoding="utf-8")
        else:
            # 源文件不存在时创建空快照
            snapshot_path.write_text(
                f"# {skill_name} v{version}\n\n(snapshot — source not found)\n", encoding="utf-8")

        # 返回相对于项目根目录的路径
        return str(snapshot_path.relative_to(ROOT)).replace("\\", "/")

    def rollback_to(self, skill_name: str, target_version: str) -> Optional[str]:
        """
        从快照恢复指定版本的内容。

        返回恢复后的文件内容，若快照不存在返回 None。
        """
        snapshot_name = f"{skill_name}_v{target_version}.md"
        snapshot_path = self._versions_dir / snapshot_name
        if not snapshot_path.exists():
            return None
        return snapshot_path.read_text(encoding="utf-8", errors="replace")

    def diff_versions(self, skill_name: str, v1: str, v2: str) -> str:
        """
        对比两个版本的快照，返回差异摘要。
        使用行级对比（新增/删除行）。
        """
        content1 = self.rollback_to(skill_name, v1)
        content2 = self.rollback_to(skill_name, v2)

        if content1 is None:
            return f"[ERROR] Version {v1} snapshot not found for {skill_name}"
        if content2 is None:
            return f"[ERROR] Version {v2} snapshot not found for {skill_name}"

        lines1 = content1.split("\n")
        lines2 = content2.split("\n")

        added = []
        removed = []

        # 简单行级对比
        set1 = set(lines1)
        set2 = set(lines2)

        for line in lines2:
            if line not in set1:
                added.append(line)
        for line in lines1:
            if line not in set2:
                removed.append(line)

        parts = []
        parts.append(f"# Diff: {skill_name} {v1} → {v2}")
        parts.append(f"## Added ({len(added)} lines)")
        for line in added[:20]:
            parts.append(f"+ {line[:120]}")
        if len(added) > 20:
            parts.append(f"... and {len(added) - 20} more")

        parts.append(f"## Removed ({len(removed)} lines)")
        for line in removed[:20]:
            parts.append(f"- {line[:120]}")
        if len(removed) > 20:
            parts.append(f"... and {len(removed) - 20} more")

        parts.append(f"## Summary")
        parts.append(f"Total: {len(lines1)} → {len(lines2)} lines, "
                     f"+{len(added)} / -{len(removed)}")

        return "\n".join(parts)

    def prune_old_snapshots(self, skill_name: str, version_history: List[VersionRecord]) -> None:
        """
        若历史版本超过 MAX_VERSION_SNAPSHOTS，将最旧快照转为 diff 存储。

        规则：保留最新 10 个完整快照，超出部分转为 diff 格式。
        """
        if len(version_history) <= MAX_VERSION_SNAPSHOTS:
            return

        # 按版本号排序（升序）
        sorted_versions = sorted(
            version_history, key=lambda v: self.parse(v.version))
        # 需要裁剪的旧版本
        to_prune = sorted_versions[:len(
            sorted_versions) - MAX_VERSION_SNAPSHOTS]
        keep = sorted_versions[len(sorted_versions) - MAX_VERSION_SNAPSHOTS:]

        for vr in to_prune:
            snapshot_path = ROOT / vr.snapshot_file if vr.snapshot_file else None
            if snapshot_path and snapshot_path.exists():
                # 将快照转为 diff（相对于下一个版本）
                next_vr = keep[0]  # 最靠近的保留版本
                diff_content = self.diff_versions(
                    skill_name, vr.version, next_vr.version)
                diff_file = snapshot_path.with_suffix(".diff")
                diff_file.write_text(diff_content, encoding="utf-8")
                # 删除原始快照
                snapshot_path.unlink()


# ===========================================================================
# 技能注册表
# ===========================================================================

class SkillRegistry:
    """技能注册表——五行流转的中枢

    管理所有已注册技能的元数据，包括版本历史、运行时统计、
    环境兼容性等信息。数据持久化到 YAML 文件。
    """

    def __init__(self, registry_path: str = ""):
        """
        初始化注册表。

        Args:
            registry_path: YAML 注册表文件路径（相对于项目根或绝对路径）。
                           默认: memory/skill_registry.yaml
        """
        if registry_path:
            p = Path(registry_path)
            self._registry_path = p if p.is_absolute() else ROOT / p
        else:
            self._registry_path = DEFAULT_REGISTRY_PATH

        self._skills: Dict[str, SkillMeta] = {}
        self._version_manager = SkillVersionManager(str(self._registry_path))

    # ------------------------------------------------------------------
    # 注册与管理
    # ------------------------------------------------------------------

    def register(self, skill_name: str, meta: SkillMeta) -> None:
        """
        注册新技能（木·生）。

        自动设置初始版本 1.0.0 和时间戳。
        若技能已存在，抛出 ValueError。
        """
        if skill_name in self._skills:
            # 已存在：更新元数据（合并策略）
            existing = self._skills[skill_name]
            # 保留已有统计，更新描述性字段
            existing.file = meta.file or existing.file
            existing.dependencies = meta.dependencies or existing.dependencies
            existing.similar_to = meta.similar_to or existing.similar_to
            existing.environment = meta.environment
            return

        now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S")

        meta.name = skill_name
        meta.created_at = now
        meta.last_used = now
        meta.status = STATUS_ACTIVE

        # 初始版本记录
        if not meta.version_history:
            meta.version_history.append(VersionRecord(
                version=meta.version,
                created_at=now,
                reason=REASON_INITIAL,
                snapshot_file="",
            ))
        meta.version = meta.version_history[-1].version if meta.version_history else "1.0.0"

        self._skills[skill_name] = meta

    def update_usage(self, skill_name: str, success: bool) -> bool:
        """
        更新技能使用统计（木·生反馈回路）。

        每次调用递增 use_count，并移动 success_rate 加权平均。

        Returns:
            True if skill found and updated, False otherwise.
        """
        skill = self._skills.get(skill_name)
        if not skill:
            return False

        now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S")
        skill.last_used = now
        skill.use_count += 1

        # 加权移动平均更新成功率（新数据权重 0.2）
        alpha = 0.2
        skill.success_rate = round(
            skill.success_rate * (1 - alpha) +
            (1.0 if success else 0.0) * alpha, 4
        )

        # 更新健康评分
        skill.health_score = self._compute_health(skill)
        skill.last_health_check = now

        return True

    def archive(self, skill_name: str, reason: str = "") -> None:
        """
        归档技能（金·克）。

        将技能标记为 archived 状态，但保留所有元数据和版本历史。
        L0 公理 2 保障：已验证数据不可删改。
        """
        skill = self._skills.get(skill_name)
        if not skill:
            raise KeyError(f"Skill not found: {skill_name!r}")
        skill.status = STATUS_ARCHIVED

    def deprecate(self, skill_name: str, replaced_by: str) -> None:
        """
        废弃技能——被新技能替代（金·克）。

        标记为 deprecated 并将 replaced_by 记录在元数据中。
        """
        skill = self._skills.get(skill_name)
        if not skill:
            raise KeyError(f"Skill not found: {skill_name!r}")
        skill.status = STATUS_DEPRECATED
        # 在 similar_to 中记录替代关系
        if replaced_by not in skill.similar_to:
            skill.similar_to.append(replaced_by)

    def recover(self, skill_name: str) -> bool:
        """
        从归档恢复技能（金·克后恢复）。

        返回 True 表示恢复成功，False 表示技能不在归档状态。
        """
        skill = self._skills.get(skill_name)
        if not skill:
            raise KeyError(f"Skill not found: {skill_name!r}")
        if skill.status == STATUS_ACTIVE:
            return False  # 已是活跃状态
        skill.status = STATUS_ACTIVE
        return True

    # ------------------------------------------------------------------
    # 查询
    # ------------------------------------------------------------------

    def get_active_skills(self) -> List[SkillMeta]:
        """获取所有活跃技能"""
        return [s for s in self._skills.values() if s.status == STATUS_ACTIVE]

    def get_archived_skills(self) -> List[SkillMeta]:
        """获取所有归档技能"""
        return [s for s in self._skills.values() if s.status == STATUS_ARCHIVED]

    def get_deprecated_skills(self) -> List[SkillMeta]:
        """获取所有废弃技能"""
        return [s for s in self._skills.values() if s.status == STATUS_DEPRECATED]

    def get(self, skill_name: str) -> Optional[SkillMeta]:
        """按名称获取技能元数据"""
        return self._skills.get(skill_name)

    def find_similar(self, skill_name: str, threshold: float = 0.7) -> List[SkillMeta]:
        """
        查找与指定技能相似的技能（供火·化整合使用）。

        相似度基于:
          - 共享依赖项 (40%)
          - 共享 similar_to 链接 (30%)
          - 名称关键词重叠 (30%)

        返回相似度 ≥ threshold 的技能列表。
        """
        source = self._skills.get(skill_name)
        if not source:
            return []

        results: List[tuple] = []
        for name, target in self._skills.items():
            if name == skill_name or target.status != STATUS_ACTIVE:
                continue
            sim = self._compute_similarity(source, target)
            if sim >= threshold:
                results.append((sim, target))

        results.sort(key=lambda x: x[0], reverse=True)
        return [r[1] for r in results]

    def list_all(self) -> List[SkillMeta]:
        """返回所有已注册技能"""
        return list(self._skills.values())

    def get_skill_count(self) -> int:
        return len(self._skills)

    # ------------------------------------------------------------------
    # P忠恕 自我认知偏离度 (SAD)
    # ------------------------------------------------------------------

    # 默认 P忠恕 四维权重
    _DEFAULT_FORMULA_WEIGHTS: Dict[str, float] = {
        "temporal": 0.20,
        "spatial": 0.20,
        "wisdom": 0.30,
        "causality": 0.30,
    }
    _SAD_DIMENSIONS: tuple[str, str, str, str] = (
        "temporal", "spatial", "wisdom", "causality",
    )

    def calculate_sad(self) -> Dict[str, float]:
        """计算 P忠恕 自我认知偏离度 (Self-Awareness Deviation)。

        对比用户自定义的 P忠恕 主观权重与基于技能使用数据推导的客观权重，
        分别计算四个维度的偏离度：

        - temporal (时位): 知进知退 vs 逆势而动
        - spatial  (宇位): 损有余补不足 vs 占有囤积
        - wisdom   (识位): 涤除玄鉴 vs 心随境转
        - causality(缘位): 常与善人 vs 自我中心

        算法:
            1. 从 YAML 文件 formula_weights 字段读取用户自定义权重（主观权重）
            2. 从技能使用数据推导各维度的实际权重分布（客观权重）
               客观权重[dim] = 该维度被评分的总次数 / 所有维度被评分的总次数
            3. SAD[dim] = |subjective[dim] - objective[dim]|
            4. overall_sad = 四个维度 SAD 的算术平均值

        Returns:
            Dict[str, float]:
                {
                    "temporal_sad":   float,  # 时位偏离度
                    "spatial_sad":    float,  # 宇位偏离度
                    "wisdom_sad":     float,  # 识位偏离度
                    "causality_sad":  float,  # 缘位偏离度
                    "overall_sad":    float,  # 综合偏离度（四维均值）
                }

        错误处理:
            - YAML 文件不存在或 formula_weights 字段缺失 → 使用默认权重并输出警告
            - formula_weights 格式不正确（缺少维度、权重和非 1.0）→ 使用默认权重
            - 无维度评分事件数据 → 客观权重回退为默认权重
        """
        # ---- Step 1: 读取主观权重 ----
        subjective = dict(self._DEFAULT_FORMULA_WEIGHTS)
        try:
            if self._registry_path.exists():
                with open(self._registry_path, "r", encoding="utf-8") as f:
                    raw = yaml.safe_load(f)
                if isinstance(raw, dict) and "formula_weights" in raw:
                    fw = raw["formula_weights"]
                    if isinstance(fw, dict):
                        valid = True
                        for dim in self._SAD_DIMENSIONS:
                            if dim not in fw or not isinstance(fw[dim], (int, float)):
                                valid = False
                                break
                        if valid and abs(sum(fw[d] for d in self._SAD_DIMENSIONS) - 1.0) < 0.01:
                            subjective = {d: float(fw[d])
                                          for d in self._SAD_DIMENSIONS}
                        else:
                            logger.warning(
                                "formula_weights 格式无效，回退至默认权重"
                            )
                    else:
                        logger.warning("formula_weights 不是 dict 类型，回退至默认权重")
                else:
                    logger.info("YAML 中未找到 formula_weights，使用默认权重")
            else:
                logger.info("注册表文件不存在，使用默认主观权重")
        except (yaml.YAMLError, OSError, ValueError) as e:
            logger.warning("读取 formula_weights 失败 (%s)，回退至默认权重", e)

        # ---- Step 2: 计算客观权重 ----
        # 尝试从 YAML 顶层 dimension_counts 读取维度评分频次
        dim_counts: Dict[str, int] = {d: 0 for d in self._SAD_DIMENSIONS}
        try:
            if self._registry_path.exists():
                with open(self._registry_path, "r", encoding="utf-8") as f:
                    raw = yaml.safe_load(f)
                if isinstance(raw, dict) and "dimension_counts" in raw:
                    dc = raw["dimension_counts"]
                    if isinstance(dc, dict):
                        for dim in self._SAD_DIMENSIONS:
                            if dim in dc and isinstance(dc[dim], (int, float)):
                                dim_counts[dim] = int(dc[dim])
        except (yaml.YAMLError, OSError):
            pass

        total_counts = sum(dim_counts.values())
        if total_counts > 0:
            objective = {
                d: round(dim_counts[d] / total_counts, 4)
                for d in self._SAD_DIMENSIONS
            }
        else:
            # 无评分数据 → 使用默认权重作为客观权重
            logger.info("无维度评分数据，客观权重回退为默认权重")
            objective = dict(self._DEFAULT_FORMULA_WEIGHTS)

        # ---- Step 3: 计算各维度 SAD ----
        sad: Dict[str, float] = {}
        for dim in self._SAD_DIMENSIONS:
            sad[f"{dim}_sad"] = round(
                abs(subjective[dim] - objective[dim]), 4
            )

        # ---- Step 4: 计算综合 SAD ----
        sad["overall_sad"] = round(
            sum(sad[f"{dim}_sad"] for dim in self._SAD_DIMENSIONS)
            / len(self._SAD_DIMENSIONS),
            4,
        )

        return sad

    # ------------------------------------------------------------------
    # ALIGN-001: 个人-公共对齐引擎
    # ------------------------------------------------------------------

    # 默认 Sophub 社区基准数据（四象限）
    _DEFAULT_SOPHUB_BENCHMARK: Dict[str, Dict[str, float]] = {
        "自爱": {"avg_stars": 3.5, "success_rate": 0.65, "adoption_count": 45.0},
        "尽责": {"avg_stars": 3.8, "success_rate": 0.72, "adoption_count": 38.0},
        "贡献": {"avg_stars": 4.0, "success_rate": 0.78, "adoption_count": 52.0},
        "传承": {"avg_stars": 4.2, "success_rate": 0.81, "adoption_count": 30.0},
    }
    _PILLAR_QUADRANTS: tuple[str, str, str, str] = (
        "自爱", "尽责", "贡献", "传承",
    )

    # 五行干预策略映射
    _ALIGNMENT_INTERVENTIONS = {
        "severe_deficit": {        # < 0.3
            "mode": "quantitative_easing",
            "description": "QE模式：木·生积极、金·克暂停",
            "木·生": "积极培育",
            "金·克": "完全暂停",
        },
        "mild_deficit": {          # 0.3-0.7
            "mode": "rate_cut",
            "description": "降息模式：土·通跨领域注资、金·克温和",
            "土·通": "跨领域注资",
            "金·克": "温和修剪",
        },
        "normal": {                # 0.7-1.3
            "mode": "normalization",
            "description": "利率正常化：火·化活跃整合",
            "火·化": "活跃整合",
        },
        "surplus": {               # > 1.3
            "mode": "sterilization",
            "description": "冲销干预：土·通出口、火·化提炼",
            "土·通": "出口方法论",
            "火·化": "提炼智慧",
        },
        "no_public_data": {        # null
            "mode": "no_public_data",
            "description": "该象限无社区基准，暂不干预",
        },
    }

    def calculate_alignment(self) -> Dict[str, Any]:
        """计算个人技能价值与公共核心素养的对齐度。

        读取 Sophub 社区数据（若无则使用内置默认基准），
        对四个象限分别计算 SelfValue、PublicValue 和 AlignmentScore，
        并根据对齐度给出五行干预建议。

        Returns:
            {
                "quadrants": {
                    "自爱": {
                        "self_value": float,
                        "public_value": float,
                        "alignment_score": float | None,
                        "intervention": {"mode": str, "description": str, ...},
                    },
                    ...
                },
                "overall_alignment": float | None,
                "summary": str,
                "benchmark_source": "file" | "default",
                "benchmark_age_hours": float | None,
            }
        """
        import math
        import json

        # ---- Step 1: 加载 Sophub 社区数据 ----
        benchmark_path = MEMORY_DIR / "sophub_benchmark.json"
        benchmark: Dict[str, Dict[str, float]] = {}
        benchmark_source = "default"
        benchmark_age_hours = None

        if benchmark_path.exists():
            try:
                with open(benchmark_path, "r", encoding="utf-8") as f:
                    loaded = json.load(f)
                # 验证四象限完整性
                valid = True
                for quad in self._PILLAR_QUADRANTS:
                    if quad not in loaded or not isinstance(loaded[quad], dict):
                        valid = False
                        break
                    qd = loaded[quad]
                    for key in ("avg_stars", "success_rate", "adoption_count"):
                        if key not in qd or not isinstance(qd[key], (int, float)):
                            valid = False
                            break
                if valid:
                    benchmark = {
                        q: {
                            "avg_stars": float(loaded[q]["avg_stars"]),
                            "success_rate": float(loaded[q]["success_rate"]),
                            "adoption_count": float(loaded[q]["adoption_count"]),
                        }
                        for q in self._PILLAR_QUADRANTS
                    }
                    benchmark_source = "file"
                    # 检查是否超24小时未更新
                    if "updated_at" in loaded:
                        try:
                            updated = datetime.fromisoformat(
                                loaded["updated_at"].replace("Z", "+00:00"))
                            age = (datetime.now(timezone.utc) -
                                   updated).total_seconds() / 3600
                            benchmark_age_hours = round(age, 1)
                            if age > 24:
                                logger.warning(
                                    "sophub_benchmark.json 超 %s 小时未更新 (%s h)",
                                    24, age,
                                )
                        except (ValueError, TypeError):
                            pass
                else:
                    logger.warning("sophub_benchmark.json 格式不完整，使用默认基准")
            except (json.JSONDecodeError, OSError) as e:
                logger.warning("读取 sophub_benchmark.json 失败 (%s)，使用默认基准", e)

        if not benchmark:
            benchmark = dict(self._DEFAULT_SOPHUB_BENCHMARK)

        # ---- Step 2: 计算个人各象限价值 (SelfValue) ----
        active_skills = self.get_active_skills()
        # 按 pillar_tag 分组
        grouped: Dict[str, List[SkillMeta]] = {
            q: [] for q in self._PILLAR_QUADRANTS}
        unclassified: List[SkillMeta] = []
        for skill in active_skills:
            tag = skill.pillar_tag if skill.pillar_tag in self._PILLAR_QUADRANTS else ""
            if tag:
                grouped[tag].append(skill)
            else:
                unclassified.append(skill)

        self_values: Dict[str, float] = {}
        for quad in self._PILLAR_QUADRANTS:
            skills = grouped[quad]
            if not skills:
                self_values[quad] = 0.0
            else:
                total = sum(
                    skill.health_score * skill.use_count * skill.emotional_value
                    for skill in skills
                )
                self_values[quad] = round(total, 4)

        # ---- Step 3: 计算公共各象限价值 (PublicValue) ----
        public_values: Dict[str, float] = {}
        for quad in self._PILLAR_QUADRANTS:
            b = benchmark[quad]
            public_values[quad] = round(
                b["avg_stars"] * 0.5
                + b["success_rate"] * 0.3
                + math.log(1 + b["adoption_count"]) * 0.2,
                4,
            )

        # ---- Step 4: 计算对齐度 (AlignmentScore) & 干预策略 ----
        quadrants_result: Dict[str, Dict[str, Any]] = {}
        valid_scores: List[float] = []

        for quad in self._PILLAR_QUADRANTS:
            sv = self_values[quad]
            pv = public_values[quad]

            if pv == 0.0:
                alignment_score = None
                intervention = self._ALIGNMENT_INTERVENTIONS["no_public_data"]
            else:
                alignment_score = round(sv / pv, 4)
                valid_scores.append(alignment_score)

                if alignment_score < 0.3:
                    intervention = self._ALIGNMENT_INTERVENTIONS["severe_deficit"]
                elif alignment_score < 0.7:
                    intervention = self._ALIGNMENT_INTERVENTIONS["mild_deficit"]
                elif alignment_score <= 1.3:
                    intervention = self._ALIGNMENT_INTERVENTIONS["normal"]
                else:
                    intervention = self._ALIGNMENT_INTERVENTIONS["surplus"]

            quadrants_result[quad] = {
                "self_value": sv,
                "public_value": pv,
                "alignment_score": alignment_score,
                "intervention": intervention,
            }

        # ---- Step 5: 计算综合对齐度 ----
        overall_alignment = None
        if valid_scores:
            overall_alignment = round(
                sum(valid_scores) / len(valid_scores), 4
            )

        # 生成摘要
        summary = self._build_alignment_summary(
            quadrants_result, overall_alignment)

        return {
            "quadrants": quadrants_result,
            "overall_alignment": overall_alignment,
            "summary": summary,
            "benchmark_source": benchmark_source,
            "benchmark_age_hours": benchmark_age_hours,
        }

    @staticmethod
    def _build_alignment_summary(
        quadrants: Dict[str, Dict[str, Any]],
        overall: Optional[float],
    ) -> str:
        """生成对齐度摘要文本。"""
        parts = []
        if overall is not None:
            if overall < 0.3:
                overall_desc = "严重折价 — 需要系统性的能力建设"
            elif overall < 0.7:
                overall_desc = "一般折价 — 需要跨领域学习和补充"
            elif overall <= 1.3:
                overall_desc = "平价区间 — 个人价值与社区共识匹配良好"
            else:
                overall_desc = "溢价区间 — 你的能力可对外输出、引领他人"
            parts.append(f"综合对齐度: {overall:.4f} ({overall_desc})")
        else:
            parts.append("综合对齐度: 无有效数据")

        for quad, data in quadrants.items():
            score = data["alignment_score"]
            mode = data["intervention"]["mode"]
            if score is None:
                parts.append(
                    f"  {quad}: N/A — {data['intervention']['description']}")
            else:
                parts.append(f"  {quad}: {score:.4f} → 干预模式={mode}")

        return "\n".join(parts)

    # ------------------------------------------------------------------
    # STAGE-001: 修为六阶段自适应策略
    # ------------------------------------------------------------------

    # 六阶段判定阈值的维度
    _STAGE_THRESHOLDS = {
        "convergence": 0.3,        # 权重收敛判定阈值 (max-min > 0.3)
        "balance": 0.1,            # 均衡判定阈值 (max-min < 0.1)
        "stable": 0.03,            # 稳定判定阈值 (连续变化 < 0.03)
        "stable_count": 3,         # 连续稳定版本数 → 耳顺
        "unstoppable_count": 5,    # 连续无更新版本数 → 从心所欲
    }

    _STAGE_NAMES = [
        "志于学",    # 各维度权重波动大，无明显趋势
        "立",        # 权重开始收敛于某个维度
        "不惑",      # 识位+Causality是两个最高的权重
        "知天命",    # 四维权重趋于均衡
        "耳顺",      # 权重长期稳定
        "从心所欲",  # 权重不再变化
    ]

    _STAGE_STRATEGIES = {
        "志于学": {
            "name": "志于学",
            "index": 0,
            "companion_strategy": "此时是探索期，慧惠应保持好奇、减少干预，提供多元视角但不强推方向。多问'你觉得呢？'而非'你应该…'。",
        },
        "立": {
            "name": "立",
            "index": 1,
            "companion_strategy": "你正在某个维度上扎根深入，慧惠应帮你聚焦——减少其他维度干扰，提供该维度的深度资源和案例。",
        },
        "不惑": {
            "name": "不惑",
            "index": 2,
            "companion_strategy": "识位与缘位成为你的核心锚点，理性判断和因果洞察是你的优势。慧惠可以引入更多高级对话：反问你的假设、帮助你在灰色地带做抉择。",
        },
        "知天命": {
            "name": "知天命",
            "index": 3,
            "companion_strategy": "四维趋于均衡，你不再偏废一端。慧惠应变为'静默的见证者'：仅在关键节点提供轻量反馈，更多是记录和映照。",
        },
        "耳顺": {
            "name": "耳顺",
            "index": 4,
            "companion_strategy": "权重长期稳定，形成你的稳固内在体系。慧惠可以退为'归档者'：系统性整理你的修行轨迹，为你产出修行报告而非指导。",
        },
        "从心所欲": {
            "name": "从心所欲",
            "index": 5,
            "companion_strategy": "你已不依赖外部权重体系。慧惠的角色是'致贺者'：庆祝你的自由，温柔提醒你偶尔回首起点，感知来路的意义。",
        },
    }

    def analyze_weight_evolution(self) -> Dict[str, Any]:
        """分析 P忠恕 公式权重的版本历史，映射到六阶段修行模型。

        从 memory/skill_registry.yaml 读取 formula_weights 当前值
        和 _formula_weights_history 历史记录，计算各版本间四维权重的
        变化趋势，并映射为六修行阶段。

        Returns:
            {
                "current_stage": str,          # 当前修行阶段
                "stage_index": int,            # 阶段序号 (0-5)
                "evolution": [                 # 各版本变化趋势列表
                    {
                        "version_tag": str,    # 版本标识
                        "weights": dict,       # 该版本的四维权重
                        "trend": str,          # 趋势描述
                        "stage_tendency": str, # 阶段倾向
                    }
                ],
                "strategy": str,               # 慧惠陪伴策略建议
                "convergence_metric": float,   # 当前权重收敛度 (max-min)
                "is_balanced": bool,           # 是否均衡
                "stable_since_versions": int,  # 连续稳定版本数
            }
        """
        # ---- Step 1: 读取公式权重历史 ----
        all_versions: List[Dict[str, Any]] = []

        try:
            if self._registry_path.exists():
                with open(self._registry_path, "r", encoding="utf-8") as f:
                    raw = yaml.safe_load(f)

                if isinstance(raw, dict):
                    # 当前权重
                    current_weights = dict(self._DEFAULT_FORMULA_WEIGHTS)
                    if "formula_weights" in raw and isinstance(raw["formula_weights"], dict):
                        fw = raw["formula_weights"]
                        valid = True
                        for dim in self._SAD_DIMENSIONS:
                            if dim not in fw or not isinstance(fw[dim], (int, float)):
                                valid = False
                        if valid:
                            current_weights = {
                                d: float(fw[d]) for d in self._SAD_DIMENSIONS}

                    all_versions.append({
                        "version_tag": "current",
                        "weights": dict(current_weights),
                    })

                    # 历史版本
                    if "_formula_weights_history" in raw and isinstance(
                        raw["_formula_weights_history"], list
                    ):
                        for entry in raw["_formula_weights_history"]:
                            if isinstance(entry, dict) and "weights" in entry:
                                w = entry["weights"]
                                version_entry = {
                                    "version_tag": entry.get("version_tag", "unknown"),
                                    "weights": {},
                                }
                                valid = True
                                for dim in self._SAD_DIMENSIONS:
                                    if dim in w and isinstance(w[dim], (int, float)):
                                        version_entry["weights"][dim] = float(
                                            w[dim])
                                    else:
                                        valid = False
                                        break
                                if valid:
                                    all_versions.insert(
                                        0, version_entry
                                    )  # 历史在前，当前在后
                else:
                    all_versions.append({
                        "version_tag": "current",
                        "weights": dict(self._DEFAULT_FORMULA_WEIGHTS),
                    })
            else:
                all_versions.append({
                    "version_tag": "current",
                    "weights": dict(self._DEFAULT_FORMULA_WEIGHTS),
                })
        except (yaml.YAMLError, OSError) as e:
            logger.warning("读取公式权重历史失败 (%s)，使用默认权重", e)
            all_versions.append({
                "version_tag": "current",
                "weights": dict(self._DEFAULT_FORMULA_WEIGHTS),
            })

        # ---- Step 2: 计算相邻版本变化向量 ----
        version_count = len(all_versions)
        changes: List[Dict[str, float]] = []
        if version_count >= 2:
            for i in range(1, version_count):
                prev = all_versions[i - 1]["weights"]
                curr = all_versions[i]["weights"]
                delta = {}
                for dim in self._SAD_DIMENSIONS:
                    delta[dim] = round(curr[dim] - prev[dim], 4)
                changes.append(delta)

        # ---- Step 3: 分析各版本趋势并映射阶段倾向 ----
        evolution: List[Dict[str, Any]] = []
        for i, ver in enumerate(all_versions):
            entry = {
                "version_tag": ver["version_tag"],
                "weights": dict(ver["weights"]),
                "trend": "",
                "stage_tendency": "",
            }

            weights_list = [ver["weights"][dim]
                            for dim in self._SAD_DIMENSIONS]
            weight_range = round(max(weights_list) - min(weights_list), 4)

            if i == 0:
                entry["trend"] = f"初始权重，范围={weight_range}"
            elif i < len(changes) + 1:
                delta = changes[i - 1]
                dims_sorted = sorted(
                    self._SAD_DIMENSIONS,
                    key=lambda d: abs(delta[d]),
                    reverse=True,
                )
                max_change_dim = dims_sorted[0]
                max_change_val = abs(delta[max_change_dim])
                direction = "升" if delta[max_change_dim] > 0 else "降"
                entry["trend"] = (
                    f"最大变化维度={max_change_dim}({direction}{max_change_val:.4f}), "
                    f"范围={weight_range}"
                )
            else:
                entry["trend"] = "无变化数据"

            # 映射阶段倾向
            entry["stage_tendency"] = self._classify_stage_tendency(
                ver["weights"], weight_range
            )
            evolution.append(entry)

        # ---- Step 4: 判定当前阶段 ----
        current_weights = all_versions[-1]["weights"]
        weights_list = [
            current_weights[dim] for dim in self._SAD_DIMENSIONS
        ]
        weight_range = round(max(weights_list) - min(weights_list), 4)

        # 判断连续稳定版本数
        stable_since = 0
        if version_count >= 2:
            for ch in reversed(changes):
                if all(abs(v) < self._STAGE_THRESHOLDS["stable"] for v in ch.values()):
                    stable_since += 1
                else:
                    break

        # 判断连续无更新版本数 (changes 中所有 delta 都为 0)
        unchanged_since = 0
        if version_count >= 2:
            for ch in reversed(changes):
                if all(v == 0.0 for v in ch.values()):
                    unchanged_since += 1
                else:
                    break

        # 判定阶段
        current_stage = self._determine_stage(
            current_weights, weight_range, stable_since, unchanged_since, version_count
        )

        stage_info = self._STAGE_STRATEGIES[current_stage]

        return {
            "current_stage": current_stage,
            "stage_index": stage_info["index"],
            "evolution": evolution,
            "strategy": stage_info["companion_strategy"],
            "convergence_metric": weight_range,
            "is_balanced": weight_range < self._STAGE_THRESHOLDS["balance"],
            "stable_since_versions": stable_since,
        }

    def _classify_stage_tendency(
        self, weights: Dict[str, float], weight_range: float
    ) -> str:
        """根据权重分布判断单个版本的阶段倾向。"""
        sorted_dims = sorted(
            self._SAD_DIMENSIONS, key=lambda d: weights[d], reverse=True
        )

        if weight_range < self._STAGE_THRESHOLDS["balance"]:
            return "知天命（四维均衡）"
        elif weight_range > self._STAGE_THRESHOLDS["convergence"]:
            top_dim = sorted_dims[0]
            dim_names = {
                "temporal": "时位",
                "spatial": "宇位",
                "wisdom": "识位",
                "causality": "缘位",
            }
            if sorted_dims[0] == "wisdom" and sorted_dims[1] == "causality":
                return "不惑（识位+缘位主导）"
            return f"立（权重收敛于{dim_names.get(top_dim, top_dim)}）"
        else:
            return "志于学（权重波动中）"

    def _determine_stage(
        self,
        weights: Dict[str, float],
        weight_range: float,
        stable_since: int,
        unchanged_since: int,
        version_count: int,
    ) -> str:
        """根据综合条件判定当前修行阶段。"""
        sorted_dims = sorted(
            self._SAD_DIMENSIONS, key=lambda d: weights[d], reverse=True
        )

        # 从心所欲: 连续5版本无更新
        if unchanged_since >= self._STAGE_THRESHOLDS["unstoppable_count"]:
            return "从心所欲"

        # 耳顺: 连续3版本变化<0.03
        if stable_since >= self._STAGE_THRESHOLDS["stable_count"]:
            return "耳顺"

        # 知天命: 四维均衡 (max-min < 0.1)
        if weight_range < self._STAGE_THRESHOLDS["balance"]:
            return "知天命"

        # 不惑: 识位+causality是最高两个权重
        if sorted_dims[0] == "wisdom" and sorted_dims[1] == "causality":
            # 还要确保它们不是随便相等的
            wisdom_val = weights["wisdom"]
            causality_val = weights["causality"]
            if wisdom_val >= 0.25 and causality_val >= 0.25:
                return "不惑"

        # 立: 最大最小权重大于0.3
        if weight_range > self._STAGE_THRESHOLDS["convergence"]:
            return "立"

        # 默认 → 志于学
        return "志于学"

    # ------------------------------------------------------------------
    # 持久化
    # ------------------------------------------------------------------

    # YAML 中由外部管理、save 时应保留的顶层字段
    _PRESERVED_TOP_KEYS = {"formula_weights", "dimension_counts"}

    def save(self) -> None:
        """
        将注册表持久化到 YAML 文件。

        保留已有的 formula_weights / dimension_counts 等外部配置字段，
        仅更新 skills 列表。

        写入: memory/skill_registry.yaml
        """
        self._registry_path.parent.mkdir(parents=True, exist_ok=True)

        # 读取已有 YAML，保留外部管理的顶层字段
        existing: Dict[str, Any] = {}
        if self._registry_path.exists():
            try:
                with open(self._registry_path, "r", encoding="utf-8") as f:
                    existing = yaml.safe_load(f) or {}
            except (yaml.YAMLError, OSError):
                pass

        data: Dict[str, Any] = {
            "skills": [s.to_dict() for s in self._skills.values()],
        }

        # 将已有文件中受保护的字段复制到新 data 中
        for key in self._PRESERVED_TOP_KEYS:
            if key in existing:
                data[key] = existing[key]

        with open(self._registry_path, "w", encoding="utf-8") as f:
            yaml.safe_dump(data, f, allow_unicode=True,
                           sort_keys=False, default_flow_style=False)

    def load(self) -> bool:
        """
        从 YAML 文件加载注册表。

        返回 True 表示成功加载，False 表示文件不存在。
        """
        if not self._registry_path.exists():
            return False

        with open(self._registry_path, "r", encoding="utf-8") as f:
            data = yaml.safe_load(f)

        if not data or "skills" not in data:
            return False

        self._skills = {}
        for skill_data in data["skills"]:
            skill = SkillMeta.from_dict(skill_data)
            self._skills[skill.name] = skill

        return True

    # ------------------------------------------------------------------
    # 版本管理（委托给 SkillVersionManager）
    # ------------------------------------------------------------------

    def create_snapshot(self, skill_name: str) -> Optional[str]:
        """
        创建当前 SOP 文件的版本快照。

        返回快照文件路径，若技能不存在返回 None。
        """
        skill = self._skills.get(skill_name)
        if not skill:
            return None

        snapshot_path = self._version_manager.create_snapshot(
            skill_name, skill.version, skill.file
        )

        # 更新版本历史中的快照路径
        if skill.version_history:
            skill.version_history[-1].snapshot_file = snapshot_path

        # 超过阈值时裁剪旧快照
        self._version_manager.prune_old_snapshots(
            skill_name, skill.version_history)

        return snapshot_path

    def rollback_to(self, skill_name: str, target_version: str) -> bool:
        """
        回滚到指定版本。

        1. 从快照恢复文件内容
        2. 递增补丁版本号（如 1.2.0 → 1.2.1）
        3. 添加版本历史记录

        返回 True 表示回滚成功。
        """
        skill = self._skills.get(skill_name)
        if not skill:
            raise KeyError(f"Skill not found: {skill_name!r}")

        content = self._version_manager.rollback_to(skill_name, target_version)
        if content is None:
            return False

        # 恢复文件内容
        sop_path = ROOT / skill.file
        sop_path.parent.mkdir(parents=True, exist_ok=True)
        sop_path.write_text(content, encoding="utf-8")

        # 版本号处理：保留原版本号，递增补丁号
        now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S")
        new_version = self._version_manager.bump(skill.version, BUMP_PATCH)

        # 创建恢复后的快照
        snapshot_path = self._version_manager.create_snapshot(
            skill_name, new_version, skill.file
        )

        skill.version_history.append(VersionRecord(
            version=new_version,
            created_at=now,
            reason=REASON_RECOVERED,
            snapshot_file=snapshot_path,
        ))
        skill.version = new_version

        return True

    def get_version_history(self, skill_name: str) -> List[VersionRecord]:
        """获取技能的版本历史"""
        skill = self._skills.get(skill_name)
        return skill.version_history if skill else []

    def diff_versions(self, skill_name: str, v1: str, v2: str) -> str:
        """对比两个版本的差异"""
        return self._version_manager.diff_versions(skill_name, v1, v2)

    def bump_version(self, skill_name: str, bump_type: str,
                     sop_file_path: Optional[str] = None) -> Optional[str]:
        """
        递增版本号并创建快照（水·变）。

        Args:
            skill_name: 技能名称
            bump_type: 'patch' / 'minor' / 'major'
            sop_file_path: 新 SOP 文件路径（可选，默认使用当前路径）

        Returns:
            新版本号字符串，若技能不存在返回 None。
        """
        skill = self._skills.get(skill_name)
        if not skill:
            return None

        # 创建当前版本的快照
        self.create_snapshot(skill_name)

        # 递增版本号
        new_version = self._version_manager.bump(skill.version, bump_type)
        now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S")

        # 若提供了新文件路径，更新
        if sop_file_path:
            skill.file = sop_file_path

        skill.version_history.append(VersionRecord(
            version=new_version,
            created_at=now,
            reason=REASON_UPDATED,
            snapshot_file="",
        ))
        skill.version = new_version

        return new_version

    def merge_skills(self, skill_name_a: str, skill_name_b: str,
                     new_name: str, new_file: str) -> Optional[SkillMeta]:
        """
        合并两个技能（火·化）。

        新技能从 2.0.0 开始（假设合并后是重大变化）。
        原技能不被删除（L0 公理2），但标记 merged_from 关系。
        """
        skill_a = self._skills.get(skill_name_a)
        skill_b = self._skills.get(skill_name_b)
        if not skill_a or not skill_b:
            return None

        now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S")

        merged = SkillMeta(
            name=new_name,
            file=new_file,
            version="2.0.0",
            version_history=[VersionRecord(
                version="2.0.0",
                created_at=now,
                reason=REASON_MERGED,
                snapshot_file="",
            )],
            created_at=now,
            last_used=now,
            merged_from=[skill_name_a, skill_name_b],
            dependencies=list(
                set(skill_a.dependencies + skill_b.dependencies)),
            environment=skill_a.environment,  # 继承第一个的环境
        )

        self._skills[new_name] = merged
        return merged

    # ------------------------------------------------------------------
    # 内部辅助
    # ------------------------------------------------------------------

    def _compute_health(self, skill: SkillMeta) -> float:
        """计算健康评分 (0.0 ~ 1.0)"""
        score = 0.0

        # 成功率权重 40%
        score += skill.success_rate * 0.4

        # 使用频率权重 20%（log 衰减防过拟合）
        import math
        freq_score = min(math.log(skill.use_count + 1) /
                         math.log(20), 1.0) if skill.use_count > 0 else 0.0
        score += freq_score * 0.2

        # 活跃度权重 20%（最近30天内使用过）
        if skill.last_used:
            try:
                last = datetime.fromisoformat(
                    skill.last_used.replace("Z", "+00:00"))
                days_ago = (datetime.now(timezone.utc) - last).days
                recency = max(0, 1.0 - days_ago / 30)
                score += recency * 0.2
            except (ValueError, TypeError):
                pass

        # SOP 文件存在性 20%
        if (ROOT / skill.file).exists():
            score += 0.2

        return round(min(score, 1.0), 4)

    def _compute_similarity(self, a: SkillMeta, b: SkillMeta) -> float:
        """计算两个技能的相似度 (0.0 ~ 1.0)"""
        score = 0.0

        # 共享依赖项 (40%)
        if a.dependencies and b.dependencies:
            a_set = set(a.dependencies)
            b_set = set(b.dependencies)
            union = len(a_set | b_set)
            if union > 0:
                score += (len(a_set & b_set) / union) * 0.4

        # 共享 similar_to (30%)
        a_sim = set(a.similar_to) | {a.name}
        b_sim = set(b.similar_to) | {b.name}
        sim_union = len(a_sim | b_sim)
        if sim_union > 0:
            score += (len(a_sim & b_sim) / sim_union) * 0.3

        # 名称关键词重叠 (30%) - 简单 bigram 重叠
        a_bigrams = set(a.name[i:i+2] for i in range(len(a.name) - 1))
        b_bigrams = set(b.name[i:i+2] for i in range(len(b.name) - 1))
        bg_union = len(a_bigrams | b_bigrams)
        if bg_union > 0:
            score += (len(a_bigrams & b_bigrams) / bg_union) * 0.3

        return round(score, 4)
