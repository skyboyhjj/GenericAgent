"""Skills — 技能注册表与版本管理系统。

提供 SkillRegistry（技能注册表）和 SkillVersionManager（语义化版本管理），
作为五行流转（木·生、火·化、土·通、金·克、水·变）的中枢。
"""

from skills.skill_registry import (
    SkillMeta,
    VersionRecord,
    EnvironmentMeta,
    SkillVersionManager,
    SkillRegistry,
)

__all__ = [
    "SkillMeta",
    "VersionRecord",
    "EnvironmentMeta",
    "SkillVersionManager",
    "SkillRegistry",
]
