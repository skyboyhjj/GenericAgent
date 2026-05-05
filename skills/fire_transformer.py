"""
FireTransformer — 火·化整合（轻量先行版）

设计依据：
  - 《慧惠五行流转引擎-方案设计书 v1.1》第六·4节
  - 本期策略：识别冗余，输出建议——纯程序化相似度计算
  - 第二期：LLM 驱动的语义判断、合并执行、拆分回退

FireTransformer 不修改 GA 核心代码，通过 SkillRegistry 读取技能元数据，
使用纯程序化算法扫描所有活跃技能，计算相似度并输出合并建议报告。
"""

from pathlib import Path
from dataclasses import dataclass, field
from typing import List, Optional, Dict, Any

from .skill_registry import SkillRegistry, SkillMeta, EnvironmentMeta

# ---------------------------------------------------------------------------
# 路径常量
# ---------------------------------------------------------------------------
ROOT = Path(__file__).resolve().parent.parent


# ===========================================================================
# 配置与数据结构
# ===========================================================================

@dataclass
class FireTransformerConfig:
    """火·化整合的配置（轻量先行版）"""
    enabled: bool = True                        # 总开关
    similarity_threshold: float = 0.6           # 综合相似度阈值（超过此值建议合并）
    high_confidence_threshold: float = 0.8      # 高置信度阈值（标记为强烈建议）
    max_suggestions: int = 5                    # 单次审计最多输出的建议数

    # 四维度权重（总和应为 1.0）
    weight_name: float = 0.30                   # 名称相似度权重
    weight_dependencies: float = 0.30           # 依赖项重叠度权重
    weight_tags: float = 0.20                   # 标签重叠度权重
    weight_environment: float = 0.20            # 环境兼容性权重


@dataclass
class SimilarityReport:
    """两个技能之间的相似度报告"""
    skill_a: str                                # 技能A的ID
    skill_b: str                                # 技能B的ID
    overall_similarity: float                   # 综合相似度 (0-1)
    name_similarity: float                      # 名称相似度
    dependency_similarity: float                # 依赖项重叠度
    tag_similarity: float                       # 标签重叠度
    environment_similarity: float               # 环境兼容性
    confidence: str                             # "high" / "medium" / "low"
    reason: str                                 # 可读的相似原因描述


# ===========================================================================
# FireTransformer
# ===========================================================================

class FireTransformer:
    """
    火·化整合（轻量先行版）：识别相似技能，输出合并建议。

    本期只做纯程序化的相似度计算与建议输出。
    完整的 LLM 驱动合并功能将在第二期实现（详见方案书v1.1第六·4节）。

    三层漏斗（方案书v1.1设计）：
      Layer 1（本期）: 标签快筛 → 快速过滤无关联技能
      Layer 2（本期）: 工具交叉验证 → 四维度加权评分
      Layer 3（第二期）: LLM 语义判断 → 最终合并决策
    """

    def __init__(self, registry: SkillRegistry, config: Optional[FireTransformerConfig] = None):
        """
        初始化 FireTransformer。

        Args:
            registry: SkillRegistry 实例（用于读取活跃技能元数据）
            config: FireTransformer 配置，为 None 时使用默认配置
        """
        self._registry = registry
        self.config = config if config is not None else FireTransformerConfig()

    # ==================================================================
    # 本期实现：相似度计算 & 建议输出（纯程序化，不调用 LLM）
    # ==================================================================

    def calculate_similarity(self, skill_a: SkillMeta, skill_b: SkillMeta) -> float:
        """
        计算两个技能的综合相似度（0-1），纯程序化，不调用 LLM。

        四维度加权：
        - 名称相似度 (weight_name, 默认0.30)：基于单词重叠和公共子串
        - 依赖项重叠度 (weight_dependencies, 默认0.30)：dependencies 的 Jaccard 系数
        - 标签重叠度 (weight_tags, 默认0.20)：tags 的 Jaccard 系数
        - 环境兼容性 (weight_environment, 默认0.20)：os、python_version 等的一致性

        Args:
            skill_a: 技能A的 SkillMeta
            skill_b: 技能B的 SkillMeta

        Returns:
            0.0 ~ 1.0 之间的综合相似度
        """
        cfg = self.config

        # 四维度分别计算
        name_sim = self._name_similarity(skill_a.name, skill_b.name)

        deps_a = skill_a.dependencies if skill_a.dependencies else []
        deps_b = skill_b.dependencies if skill_b.dependencies else []
        dep_sim = self._jaccard_similarity(deps_a, deps_b)

        # tags：使用 getattr 安全获取（SkillMeta 可能无此字段）
        tags_a = getattr(skill_a, 'tags', None) or []
        tags_b = getattr(skill_b, 'tags', None) or []
        tag_sim = self._jaccard_similarity(tags_a, tags_b)

        # environment：使用 getattr 安全获取
        env_a = getattr(skill_a, 'environment', None)
        env_b = getattr(skill_b, 'environment', None)
        env_sim = self._environment_similarity(env_a, env_b)

        # 加权求和
        overall = (
            cfg.weight_name * name_sim +
            cfg.weight_dependencies * dep_sim +
            cfg.weight_tags * tag_sim +
            cfg.weight_environment * env_sim
        )
        return round(overall, 4)

    def find_similar_pairs(self) -> list:
        """
        扫描所有活跃技能，返回相似度超过阈值的技能对列表。

        策略：
        1. 获取所有活跃技能
        2. 对所有无序对计算相似度
        3. 过滤低于 similarity_threshold 的对
        4. 按相似度降序排列
        5. 限制返回 max_suggestions 条

        Returns:
            List[SimilarityReport]，若 config.enabled=False 返回空列表
        """
        if not self.config.enabled:
            return []

        active_skills = self._registry.get_active_skills()
        if len(active_skills) < 2:
            return []

        reports = []
        # 枚举所有无序对
        for i in range(len(active_skills)):
            for j in range(i + 1, len(active_skills)):
                skill_a = active_skills[i]
                skill_b = active_skills[j]

                # 计算各维度相似度
                name_sim = self._name_similarity(skill_a.name, skill_b.name)

                deps_a = skill_a.dependencies if skill_a.dependencies else []
                deps_b = skill_b.dependencies if skill_b.dependencies else []
                dep_sim = self._jaccard_similarity(deps_a, deps_b)

                tags_a = getattr(skill_a, 'tags', None) or []
                tags_b = getattr(skill_b, 'tags', None) or []
                tag_sim = self._jaccard_similarity(tags_a, tags_b)

                env_a = getattr(skill_a, 'environment', None)
                env_b = getattr(skill_b, 'environment', None)
                env_sim = self._environment_similarity(env_a, env_b)

                # 加权综合
                overall = round(
                    self.config.weight_name * name_sim +
                    self.config.weight_dependencies * dep_sim +
                    self.config.weight_tags * tag_sim +
                    self.config.weight_environment * env_sim,
                    4
                )

                # 阈值过滤
                if overall < self.config.similarity_threshold:
                    continue

                # 置信度分级
                if overall >= self.config.high_confidence_threshold:
                    confidence = "high"
                else:
                    confidence = "medium"

                # 生成可读原因
                reason = self._build_reason(
                    name_sim, dep_sim, tag_sim, env_sim,
                    skill_a.name, skill_b.name
                )

                reports.append(SimilarityReport(
                    skill_a=skill_a.name,
                    skill_b=skill_b.name,
                    overall_similarity=overall,
                    name_similarity=name_sim,
                    dependency_similarity=dep_sim,
                    tag_similarity=tag_sim,
                    environment_similarity=env_sim,
                    confidence=confidence,
                    reason=reason,
                ))

        # 按相似度降序排列
        reports.sort(key=lambda r: r.overall_similarity, reverse=True)

        # 限制数量
        return reports[:self.config.max_suggestions]

    def generate_suggestions(self) -> list:
        """
        生成合并建议列表，供 RootAuditor 和人工审核使用。

        基于 find_similar_pairs() 的结果，格式化为结构化建议。

        Returns:
            List[dict]，每项包含完整的相似度分析和合并建议，
            格式见 generate_suggestions 的文档字符串。
        """
        pairs = self.find_similar_pairs()
        suggestions = []

        for report in pairs:
            suggestions.append({
                "skill_a": report.skill_a,
                "skill_b": report.skill_b,
                "similarity": report.overall_similarity,
                "confidence": report.confidence,
                "dimensions": {
                    "name": report.name_similarity,
                    "dependencies": report.dependency_similarity,
                    "tags": report.tag_similarity,
                    "environment": report.environment_similarity,
                },
                "reason": report.reason,
            })

        return suggestions

    # ==================================================================
    # 第二期预留接口（本期仅返回占位信息，不执行实际操作）
    # ==================================================================

    def merge(self, skill_a: str, skill_b: str, strategy: str = "auto") -> dict:
        """
        [第二期] 执行两个技能的合并。

        第二期将实现（详见方案书v1.1第六·4节）：
        1. 调用 LLM 进行语义相似度判断（三层漏斗 Layer 3）
           - 评估两个 SOP 的功能重叠度
           - 识别差异化的操作步骤
           - 判断是否适合合并（如工具调用链相似、前置条件兼容等）
        2. 生成 MergeProposal（含合并策略、收益评估、风险评估）
           - 收益：消除冗余、减少选择困难、提炼通用范式
           - 风险：合并后可能丢失特殊场景覆盖、SOP 过于复杂
        3. 调用 LLM 合并两个 SOP 内容
           - 保留所有功能性步骤
           - 去重并统一描述语言
           - 标记差异化的分支路径
        4. 使用 WoodGrower.post_validate() 校验合并产物
           - R1-R4 规则检查（禁止绝对路径、日期、环境特定值）
           - 确保合并后的 SOP 符合 L0 公理3
        5. 写入新 SOP 文件，更新 SkillRegistry（merged_from 字段）
           - 原技能标记为 deprecated，保留版本历史
           - 记录 merge_log.yaml 审计日志
        6. 旧技能标记为 merged，旧 SOP 归档到 memory/archive/merge_history/
           - 旧 SOP 内容保留，支持随时回溯
        7. 更新 L1 索引（global_mem_insight.txt），反映技能合并

        策略选项（方案书第六·4.3节）：
        - "absorb_a": A 吸收 B 的差异化内容，B 归档
        - "absorb_b": B 吸收 A 的差异化内容，A 归档
        - "create_new": 创建全新 SOP C，A 和 B 均标记为 merged_from C
        - "auto": 由 LLM 根据分析结果自动选择最优策略

        Args:
            skill_a: 技能A的标识符
            skill_b: 技能B的标识符
            strategy: 合并策略（"absorb_a" / "absorb_b" / "create_new" / "auto"）

        Returns:
            当前版本返回占位信息，不执行实际操作。
            第二期将返回 MergeResult（含新技能ID、归档的技能列表、校验报告）。
        """
        return {
            "status": "not_implemented",
            "message": (
                "自动合并功能将在第二期（火·化完整版）中实现。"
                "届时将支持 LLM 驱动的语义判断、合并执行、拆分回退。"
                "当前请基于 generate_suggestions() 的建议手动审核。"
            ),
            "suggestion": f"建议手动合并 {skill_a} 和 {skill_b}",
            "available_strategies": ["absorb_a", "absorb_b", "create_new", "auto"],
            "planned_version": "v2.0.0",
        }

    def split(self, merged_skill_id: str) -> dict:
        """
        [第二期] 拆分已合并的技能，恢复原始技能。

        第二期将实现（详见方案书v1.1第六·4.4节）：
        1. 读取 merged_from 字段，定位原始技能
        2. 从 archive/merge_history/ 恢复原始 SOP
        3. 将原始技能的 status 改回 active
        4. 将合并产物的 status 改为 deprecated
        5. 更新 L1 索引

        拆分是合并的逆操作，作为"反悔机制"存在。
        当用户或系统发现合并后的技能不如原始版本好用时，
        可以通过拆分回退到合并前的状态。

        Args:
            merged_skill_id: 合并产物的技能标识符

        Returns:
            当前版本返回占位信息。
            第二期将返回 SplitResult（含恢复的技能列表）。
        """
        return {
            "status": "not_implemented",
            "message": (
                "拆分回退功能将在第二期实现。"
                "届时可以从 merged_from 字段恢复原始技能。"
            ),
            "merged_skill_id": merged_skill_id,
            "planned_version": "v2.0.0",
        }

    # ==================================================================
    # 内部：四维度相似度计算（纯程序化）
    # ==================================================================

    def _name_similarity(self, name_a: str, name_b: str) -> float:
        """
        计算两个技能名称的相似度。

        算法：
        1. 去掉 _sop 后缀
        2. 按下划线分词
        3. 计算 Jaccard 系数（公共单词 / 总单词）
        4. 额外加分：如果一方名称完全包含另一方（如 check_files 和 check_files_v2）

        边界情况：
        - 两个名称完全相同 → 1.0
        - 两个名称无公共词 → 0.0

        Args:
            name_a: 技能A的名称
            name_b: 技能B的名称

        Returns:
            0.0 ~ 1.0 之间的名称相似度
        """
        if name_a == name_b:
            return 1.0

        # 标准化：去掉 _sop 后缀
        clean_a = name_a.replace("_sop", "")
        clean_b = name_b.replace("_sop", "")

        # 按下划线分词（保留非空词）
        words_a = set(w for w in clean_a.split("_") if w)
        words_b = set(w for w in clean_b.split("_") if w)

        if not words_a or not words_b:
            return 0.0

        # Jaccard 系数
        intersection = words_a & words_b
        union = words_a | words_b
        jaccard = len(intersection) / len(union) if union else 0.0

        # 包含关系加分：如果一方名称是另一方的子串
        containment_bonus = 0.0
        if clean_a in clean_b or clean_b in clean_a:
            containment_bonus = 0.3

        # 综合：Jaccard + 包含加分，上限 1.0
        score = min(jaccard + containment_bonus, 1.0)
        return round(score, 4)

    def _jaccard_similarity(self, items_a: list, items_b: list) -> float:
        """
        计算两个列表的 Jaccard 系数。

        Jaccard = |交集| / |并集|

        边界情况：
        - 两个空列表 → 0.0（无法判断相似性）
        - 只有一个空列表 → 0.0（无交集）

        Args:
            items_a: 第一个列表
            items_b: 第二个列表

        Returns:
            0.0 ~ 1.0 之间的 Jaccard 系数
        """
        set_a = set(items_a) if items_a else set()
        set_b = set(items_b) if items_b else set()

        if not set_a and not set_b:
            return 0.0  # 两个空集：无法判断相似度

        intersection = set_a & set_b
        union = set_a | set_b

        if not union:
            return 0.0

        return round(len(intersection) / len(union), 4)

    def _environment_similarity(self, env_a, env_b) -> float:
        """
        计算两个技能的环境兼容性。

        比较子维度：
        - os：相同=1.0，不同=0.0，一个未知=0.5
        - python_version：主版本号相同=1.0，不同=0.5，一个未知=0.5
        - 各项取平均

        env_a 和 env_b 可能是：
        - EnvironmentMeta 对象（SkillMeta.environment）
        - dict（to_dict() 输出）
        - None（字段不存在或未设置）

        Args:
            env_a: 技能A的环境信息
            env_b: 技能B的环境信息

        Returns:
            0.0 ~ 1.0 之间的环境兼容性
        """
        # 提取 os 和 python_version
        os_a = self._extract_env_field(env_a, 'os')
        os_b = self._extract_env_field(env_b, 'os')
        py_a = self._extract_env_field(env_a, 'python_version')
        py_b = self._extract_env_field(env_b, 'python_version')

        # OS 相似度
        if not os_a or not os_b:
            os_sim = 0.5  # 一方或双方未知 → 中性
        elif os_a.lower() == os_b.lower():
            os_sim = 1.0
        else:
            os_sim = 0.0

        # Python 版本相似度（仅比较主版本号）
        if not py_a or not py_b:
            py_sim = 0.5
        else:
            major_a = py_a.split('.')[0] if '.' in py_a else py_a
            major_b = py_b.split('.')[0] if '.' in py_b else py_b
            if major_a == major_b:
                py_sim = 1.0
            else:
                py_sim = 0.5  # 不同主版本仍可能兼容

        return round((os_sim + py_sim) / 2, 4)

    def _extract_env_field(self, env, field: str) -> str:
        """
        从环境对象中安全提取字段值。

        兼容 EnvironmentMeta 对象和 dict 两种格式。

        Args:
            env: EnvironmentMeta / dict / None
            field: 字段名（如 'os', 'python_version'）

        Returns:
            字段值字符串，不存在则返回空字符串
        """
        if env is None:
            return ""
        if isinstance(env, EnvironmentMeta):
            return getattr(env, field, "") or ""
        if isinstance(env, dict):
            return env.get(field, "") or ""
        return ""

    def _build_reason(self, name_sim: float, dep_sim: float,
                      tag_sim: float, env_sim: float,
                      name_a: str, name_b: str) -> str:
        """
        根据各维度得分生成可读的相似原因描述。

        Args:
            name_sim: 名称相似度
            dep_sim: 依赖相似度
            tag_sim: 标签相似度
            env_sim: 环境兼容性
            name_a: 技能A名称
            name_b: 技能B名称

        Returns:
            中文原因描述字符串
        """
        parts = []

        if name_sim >= 0.8:
            parts.append("名称高度相似")
        elif name_sim >= 0.5:
            parts.append("名称部分相似")

        if dep_sim >= 0.8:
            parts.append("依赖项高度重叠")
        elif dep_sim >= 0.5:
            parts.append("依赖项部分重叠")

        if tag_sim >= 0.8:
            parts.append("标签高度重合")
        elif tag_sim >= 0.5:
            parts.append("标签部分重合")

        if env_sim >= 0.9:
            parts.append("环境完全兼容")
        elif env_sim >= 0.5:
            parts.append("环境基本兼容")
        elif env_sim > 0:
            parts.append("环境部分兼容")

        if not parts:
            parts.append(f"综合相似度较低")

        # 拼接
        if len(parts) == 1:
            return parts[0]
        else:
            return "，".join(parts[:-1]) + "，" + parts[-1]
