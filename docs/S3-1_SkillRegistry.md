# S3-1: SkillRegistry 技能注册表 + 版本管理 执行规格（Qoder-ready）

> **版本**：v2.0.0  
> **日期**：2026-05-03  
> **状态**：待执行  
> **依赖**：Sprint 2 全部完成，GA 结晶机制已验证

---

## 一、任务信息

| 属性 | 值 |
|:---|:---|
| 任务编号 | S3-1 |
| 任务名称 | SkillRegistry 技能注册表 + 版本管理 |
| 优先级 | P0 |
| 预估工作量 | 2天 |
| 依赖 | Sprint 2 全部完成 |

## 二、任务背景

GA 现有的 Skill 以散文件形式存在于 `memory/` 目录下，缺少统一的元数据管理。这导致：
- 无法追踪技能的 `use_count`、`success_rate`、`health_score` 等运行时指标
- 没有 SOP 文件的版本历史，更新即覆盖
- 缺少结构化的相似度计算基础（用于火·化整合）
- 缺少环境兼容性元数据（用于土·通迁移）

慧惠需要在此基础上建立一个**集中式的技能注册表**，作为五行流转的中枢。同时，我们通过自动化测试确认了 GA 结晶机制的“涌现行为”本质——结晶触发由 LLM 自主判断，不具有确定性。因此，SkillRegistry 需要能独立于 GA 原生结晶，为后续的 WoodGenerator 质量门控提供元数据支撑。

## 三、当前代码状态

| 模块 | 状态 | 说明 |
|:---|:---|:---|
| GA 技能文件 | ✅ | `memory/` 目录下已有 SOP 文件（如 `check_files_sop.md` 等） |
| L1 索引 | ✅ | `memory/global_mem_insight.txt` |
| L0 元规则 | ✅ | `memory/memory_management_sop.md` |
| 结晶测试结果 | ✅ | `memory/crystal_test_results.md` |
| `skills/` 目录 | ❌ | 尚未创建 |

## 四、操作文件

| 文件 | 操作 | 说明 |
|:---|:---|:---|
| `skills/__init__.py` | **新建** | 包标记 |
| `skills/skill_registry.py` | **新建** | 技能注册表核心实现 + 版本管理器 |
| `skills/verify_s3_1.py` | **新建** | 注册表 + 版本管理专项验证脚本 |

**不修改已有文件**。SkillRegistry 独立于 GA 原有记忆文件运行，仅通过 `file` 字段引用已有 SOP 文件路径。

## 五、核心设计

### 5.1 技能元数据结构 (SkillMeta)

```yaml
# 在 memory/skill_registry.yaml 中的存储格式
skills:
  - name: "check_files_sop"              # 技能唯一标识符
    file: "memory/check_files_sop.md"    # GA 已有 SOP 文件路径（向后兼容）
    version: "1.0.0"                     # 当前语义化版本号
    version_history:                     # 版本历史列表
      - version: "1.0.0"
        created_at: "2026-05-03T18:05:00"
        reason: "initial"                # 创建原因：initial / updated / merged / recovered
        snapshot_file: "memory/versions/check_files_sop_v1.0.0.md"
    status: "active"                     # active / archived / deprecated
    created_at: "2026-05-03T18:05:00"
    last_used: "2026-05-03T18:05:00"
    use_count: 1
    success_rate: 1.0
    dependencies: ["code_run", "file_write"]
    similar_to: []                       # 相似技能名称列表（供火·化整合使用）
    merged_from: []                      # 合并来源
    environment:                          # 迁移兼容性信息
      os: "windows"
      python_version: "3.13"
      packages: []
    health_score: 1.0                    # 健康评分 (0-1)
    last_health_check: "2026-05-03T18:05:00"
```

### 5.2 SkillRegistry 类（核心接口）

```python
class SkillRegistry:
    """技能注册表——五行流转的中枢"""
    
    def __init__(self, registry_path: str = "memory/skill_registry.yaml"):
        ...
    
    # === 注册与管理 ===
    def register(self, skill_name: str, meta: SkillMeta) -> None
    def update_usage(self, skill_name: str, success: bool) -> None  # 更新使用统计
    def archive(self, skill_name: str, reason: str) -> None         # 归档到 L4
    def deprecate(self, skill_name: str, replaced_by: str) -> None  # 被新技能替代
    def recover(self, skill_name: str) -> None                      # 从归档恢复
    
    # === 查询 ===
    def get_active_skills(self) -> List[SkillMeta]
    def get_archived_skills(self) -> List[SkillMeta]
    def find_similar(self, skill_name: str, threshold: float = 0.7) -> List[SkillMeta]
    
    # === 持久化 ===
    def save(self) -> None
    def load(self) -> None
    
    # === 版本管理（委托给 SkillVersionManager） ===
    def create_snapshot(self, skill_name: str) -> str              # 返回快照路径
    def rollback_to(self, skill_name: str, target_version: str) -> bool
    def get_version_history(self, skill_name: str) -> List[VersionRecord]
    def diff_versions(self, skill_name: str, v1: str, v2: str) -> str
```

### 5.3 语义化版本管理

#### 版本号规则

采用语义化版本（Semantic Versioning）：`主版本.次版本.补丁版本`

| 五行法则 | 触发条件 | 版本号变化 | 示例 |
|:---|:---|:---|:---|
| **木·生** | 新建技能 | 初始 `1.0.0` | 首次结晶 |
| **水·变** | 小幅度更新（修补错误、微调参数） | 递增补丁号 `1.0.0 → 1.0.1` | 修复 API 端点 |
| **水·变** | 新增功能或步骤 | 递增次版本号 `1.0.0 → 1.1.0` | 增加错误处理分支 |
| **火·化** | 合并两个技能 | 新技能从 `2.0.0` 开始 | 合并 A(1.3.0) + B(1.2.0) → C(2.0.0) |
| **金·克后恢复** | 从归档恢复 | 保留原版本号，递增补丁号 | `1.2.0 → 1.2.1` |

#### 版本快照存储

```
memory/
├── skill_registry.yaml          # 注册表（含版本历史）
├── versions/                     # 版本快照目录
│   ├── check_files_sop_v1.0.0.md
│   ├── python_script_writer_v1.0.0.md
│   └── python_script_writer_v1.1.0.md
└── ... 原有 GA SOP 文件保持不变
```

**快照规则**：
- 每次版本变更时自动创建快照
- 金·克归档时不创建新版本，仅标记 status
- 快照文件命名规范：`{skill_name}_v{version}.md`
- 超过 10 个历史版本的技能，自动将最旧快照改为仅保留 diff

### 5.4 与 GA 原有记忆系统的兼容

| GA 原有组件 | SkillRegistry 的处理方式 |
|:---|:---|
| `memory/*_sop.md` | 通过 `file` 字段引用，不修改、不移动 |
| `memory/global_mem_insight.txt` (L1) | SkillRegistry 不直接修改 L1，由 WoodGenerator 根据注册表状态决定是否更新 L1 |
| `memory/memory_management_sop.md` (L0) | 元规则优先：SkillRegistry 的操作不得违反 L0 公理 |
| 新结晶产物 | 若 GA 触发了结晶，WoodGenerator 会在注册表中补充元数据 |

## 六、验证脚本

`skills/verify_s3_1.py` 需覆盖：

1. SkillRegistry 初始化成功（空注册表）
2. 注册新技能：`register()` 正确写入元数据
3. 更新使用统计：`update_usage()` 正确更新 `use_count` 和 `success_rate`
4. 归档技能：`archive()` 后将状态标记为 `archived`
5. 废弃技能：`deprecate()` 记录 `replaced_by`
6. 查询活跃技能：`get_active_skills()` 仅返回 status=active 的技能
7. 查询归档技能：`get_archived_skills()` 仅返回 status=archived 的技能
8. 持久化：`save()` 写入 YAML，`load()` 正确恢复
9. YAML 文件内容与注册表状态一致
10. **版本管理**：创建快照后 `version_history` 新增一条记录
11. **版本管理**：快照文件实际存在于 `memory/versions/` 目录
12. **版本管理**：`rollback_to()` 成功恢复到指定版本
13. **版本管理**：`diff_versions()` 返回有意义差异
14. **兼容性**：不影响已有的 GA 验证脚本（verify_soul.py 等全部通过）

## 七、验收标准

| # | 验收项 | 判定标准 |
|:---|:---|:---|
| 1 | 目录创建 | `skills/__init__.py` 和 `skills/skill_registry.py` 存在 |
| 2 | SkillRegistry 完整实现 | 含注册、更新、归档、废弃、恢复、查询、持久化 |
| 3 | 语义化版本管理 | 版本号规则正确，快照创建和回滚可用 |
| 4 | YAML 持久化 | `memory/skill_registry.yaml` 可读写 |
| 5 | 版本快照存储 | `memory/versions/` 目录下快照文件命名规范 |
| 6 | 验证脚本 | `skills/verify_s3_1.py` 全部通过 |
| 7 | 历史测试兼容 | 所有已有验证脚本通过 |
| 8 | 零修改 | GA 原有 memory/ 文件和核心文件不变 |

## 八、关键约束

- 不改动 GenericAgent 核心文件（`agentmain.py`, `agent_loop.py`, `ga.py` 等）
- 不修改 GA 原有 SOP 文件和 L1 索引
- SkillRegistry 以 YAML 文件形式独立存储，与 GA 原有记忆系统并行运行
- `memory/versions/` 目录下的快照文件为 SOP 文件的完整副本，不是增量补丁
- 超过 10 个历史版本的技能，自动将最旧快照转为 diff 存储

---

*规格结束。请以本文档为唯一执行依据。规格书中代码示例为设计意图参考，请在理解后适配实现，保持接口契约不变。*