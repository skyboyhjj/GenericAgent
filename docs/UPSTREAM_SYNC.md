# 上游同步 · 分叉治理诊断实录

> **日期**：2026-09-12
> **状态**：阶段 2 一次性对齐已完成（`integration/upstream-merge` 分支合并提交 `b24f96c`）
> **关联**：本仓库 `skyboyhjj/GenericAgent` ⇄ 上游 `lsdefine/GenericAgent`

---

## 一、背景与目的

本仓库（`skyboyhjj/GenericAgent`）相对上游（`lsdefine/GenericAgent`）已实质分叉。本文档记录一次完整的分叉诊断结果，用于判断"能否一次合并成功"，并作为后续同步工程的依据。

## 二、诊断环境

| 项 | 值 |
|:---|:---|
| 本仓库 remote `origin` | `https://github.com/skyboyhjj/GenericAgent.git` |
| 上游 remote `upstream` | `https://github.com/lsdefine/GenericAgent.git` |
| 本仓库 `main` tip | `2ea9af2` |
| 上游 `upstream/main` tip | `86171ae`（已与 GitHub API 核验一致） |
| 网络 | 直连失败（`curl 56 Connection reset`），经本地代理 `socks5h://127.0.0.1:10808` 成功拉取 |

> **坑位记录**：本地克隆起初为**浅克隆（shallow）**，`main` 仅 2 个提交，导致 `rev-list --left-right --count` 初算成 `2/1359`（错误）。已通过 `git fetch --unshallow origin` 修复，修复后数字与 GitHub API 完全对齐。

## 三、诊断结果

### 3.1 分叉点（merge-base）

存在 **2 个共同祖先（criss-cross）**：

- `71c59d2`（2026-03-12，`更新plan_sop.md和subagent_sop.md文档`）
- `df3b347`

criss-cross 的成因：fork 曾在 `8fbce9f` 执行过一次 `Merge branch 'main' of lsdefine/GenericAgent`。这会使后续 merge 比单祖先更复杂。

### 3.2 领先 / 落后计数

```text
领先 405　落后 1238　（diverged）
```

> 原治理方案记为 "404/1238"，差 1 是本日新增的同步提交 `2ea9af2`（`feat: 同步问候引擎、袭明同步与记忆他人功能`）。

### 3.3 双边改动规模

| 维度 | fork 侧（405 提交） | 上游侧（1238 提交） |
|:---|:---|:---|
| 改动文件数 | 219 | 374 |
| 插入 / 删除 | +42845 / −2791 | +85641 / −2992 |
| 新增（A） | 183 | 338 |
| 修改（M） | 22 | 22 |
| 删除（D） | 12 | 13 |
| 重命名（R） | 2 | 1 |

### 3.4 冲突面（关键结论）

| 冲突类型 | 数量 | 说明 |
|:---|:---|:---|
| **modified**（双边改同一文件） | **22** | 100% 重叠，无一旁路 |
| **add/add**（双边同名新增） | **79** | 同名不同内容，merge 必冲突 |
| **delete/delete**（双边同名删除） | **12** | |

**合计潜在需手工解决的冲突点 ≈ 113 个文件**，远大于"少数几个"的乐观估计。

#### 22 个被双边修改的核心文件

```text
.gitignore
README.md
agent_loop.py
agentmain.py
ga.py
TMWebDriver.py
simphtml.py
launch.pyw
mykey_template.py
assets/sys_prompt.txt
assets/tools_schema.json
assets/global_mem_insight_template.txt
assets/insight_fixed_structure.txt
memory/adb_ui.py
memory/ljqCtrl.py
memory/autonomous_operation_sop.md
memory/ljqCtrl_sop.md
memory/memory_management_sop.md
memory/plan_sop.md
memory/scheduled_task_sop.md
memory/tmwebdriver_sop.md
memory/web_setup_sop.md
```

核心文件 `agent_loop.py`、`ga.py`、`agentmain.py` 均在其中，落在"高冲突"分支。

#### 79 个 add/add 同名新增（按目录归类）

- **根目录**：`CONTRIBUTING.md`、`LICENSE`、`hub.pyw`、`llmcore.py`、`pyproject.toml`、`mykey_template_en.py`
- **assets/**：`GenericAgent_Technical_Report.pdf`、`code_run_header.py`、`global_mem_insight_template_en.txt`、`insight_fixed_structure_en.txt`、`sys_prompt_en.txt`、`tools_schema_cn.json`、`images/{bar,feishu_group,logo,workflow}.jpg`、`tmwd_cdp_bridge/{background,content,disable_dialogs}.js` + `manifest.json` + `popup.{html,js}`
- **frontends/**：`DESKTOP_PET_README.md`、`chat_bubble.png`、`chatapp_common.py`、`continue_cmd.py`、`dcapp.py`、`desktop_pet_v2.pyw`、`dingtalkapp.py`、`fsapp.py`、`qqapp.py`、`qtapp.py`、`stapp.py`、`stapp2.py`、`tgapp.py`、`wechatapp.py`、`wecomapp.py`，及 `skins/{boy,dinosaur,doux,glube,line,mort,tard,vita}/*`
- **memory/**：`L4_raw_sessions/compress_session.py`、`autonomous_operation_sop/{helper.py,task_planning.md}`、`github_contribution_sop.md`、`keychain.py`、`memory_cleanup_sop.md`、`ocr_utils.py`、`procmem_scanner_sop.md`、`supervisor_sop.md`、`ui_detect.py`、`vision_api.template.py`、`vision_sop.md`
- **plugins/**：`langfuse_tracing.py`
- **reflect/**：`autonomous.py`、`scheduler.py`

> 注意：`llmcore.py`、`pyproject.toml`、`hub.pyw`、整套 `frontends/`、`memory/keychain.py` 等，均是双边**各自独立重造同路径**的平行结构，是本次冲突的主要来源。

#### 12 个 delete/delete 同名删除

```text
WELCOME_NEW_USER.md
sidercall.py
stapp.py
tgapp.py
assets/cookie_grabber/{background,content}.js
assets/cookie_grabber/manifest.json
assets/cookie_grabber/popup.{html,js}
assets/ljq_web_driver.user.js
assets/make_prompts.py
memory/mem_scanner_sop.md
```

## 四、结论

1. **"很可能一次 merge 就搞定"不成立**：冲突面约为 113 个文件，且核心文件（`agent_loop.py`/`ga.py`/`agentmain.py`）全部被双边改过。
2. **命中"高冲突"分支**：应优先执行 **§5 改动收窄**，把 `frontends/`、`memory/`、`llmcore.py`、`plugins/`、`reflect/` 等撞名结构挪入独立命名空间，收敛 add/add 面，再做一次性 merge。
3. criss-cross merge-base 会额外增加合并复杂度，需在 `integration/` 分支做，不直接动 `main`。

## 五、建议治理路径

| 阶段 | 动作 | 状态 |
|:---|:---|:---|
| 0 备份冻结 | `--mirror` 镜像 + 打 tag `huihui-pre-sync-*` | ✅ 完成（tag `huihui-pre-sync-20260912` → `4ea7e5d`） |
| 1 诊断 | 本实录 | ✅ 完成 |
| 2 一次性对齐 | `integration/` 分支 `git merge upstream/main --no-ff` | ✅ 完成（`b24f96c`） |
| 3 改动收窄 | 定制下沉至独立目录 + 品牌分离 + 治理清单 | ✅ 完成（务实收窄） |
| 4 双轨 SLA | `main`≈上游 / `huihui`=全定制 | ✅ 完成 |
| 6 自动化 | `tools/sync-upstream.ps1` + GitHub Actions 漂移提醒 | ✅ 完成（脚本；CI 待 token `workflow` scope） |

## 六、验证方式

- 领先/落后与 GitHub Compare API（`repos/skyboyhjj/GenericAgent/compare/lsdefine:main...main`）交叉核验一致：`ahead_by=405`、`behind_by=1238`、`status=diverged`。
- `upstream/main` tip 与 `gh api repos/lsdefine/GenericAgent/git/refs/heads/main` 核验一致（`86171aec`）。

## 七、合并取向（本次已决策）

- **总体原则**：以我方（慧惠）定制为准；冲突时优先保留本仓库自研定制与品牌。
- **前端 / 工具类**：上游对 `frontends/`（桌面宠物、各 IM 入口等）及纯工具类文件的更新，**在不影响核心的前提下不 merge**，保留差异并将对应文件标记为「已审阅 / 不合并」。
- **核心逻辑类**：`agent_loop.py`、`ga.py`、`agentmain.py` 等冲突点逐文件人工判断，不影响慧惠定制的前提下吸收上游修复。

## 八、阶段 2 合并执行实录

> 分支：`integration/upstream-merge`；合并提交：`b24f96c`；预期冲突文件 113，实测需裁决 48。

### 8.1 冲突裁决统计

| 裁决类型 | 数量 | 代表文件 |
|:---|:---|:---|
| **取上游（theirs）** | 13 | `pyproject.toml`、`memory/ui_detect.py`、`.gitignore`、`memory/vision_api.template.py` 等 |
| **取本地（ours）** | 13＋14 | `agentmain.py`、`llmcore.py`、`assets/tools_schema.json`、`TMWebDriver.py`、`hub.pyw`、`memory/keychain.py` 等 |
| **文本合并** | 8 | `agent_loop.py`、`ga.py`、`assets/sys_prompt.txt`、`memory/*.md` 等 |

### 8.2 关键取舍（慧惠定制保全）

- `agentmain.py` **取本地**：保留 `class GeneraticAgent`（慧惠全部前端 `dingtalkapp.py`/`fsapp.py`/`wechatapp.py`/`stapp.py`/`tgapp.py`/`dcapp.py`/`qtapp.py`/`qqapp.py` 等均 `from agentmain import GeneraticAgent`）。
- `llmcore.py` **取本地**：保留 `reload_mykeys()` / `mykeys` 全局及 `ToolClient`/`ClaudeSession`/`NativeClaudeSession` 等会话类，慧惠密钥重载与多模型会话依赖其 API。
- `assets/tools_schema.json` **取本地**：保留慧惠自研工具协议（如 `code_run` 的 `inline_eval`/`cwd` 字段）。
- `TMWebDriver.py` / `hub.pyw` / `memory/keychain.py` / `reflect/scheduler.py` / `memory/compress_session.py` 等核心运行态文件**取本地**，避免上游重构破坏运行环境。
- 上游纯新增（无冲突）部分全部吸收：`frontends/desktop/`（Tauri 桌面）、`ga_cli/`、`plugins/`、`docs/`、`frontends/tests/` 等。

### 8.3 回归验证

| 检查 | 结果 |
|:---|:---|
| `python -m py_compile agentmain.py llmcore.py agent_loop.py ga.py` | ✅ 通过 |
| `assets/tools_schema.json` JSON 合法 | ✅ 通过 |
| 无残留冲突标记（`<<<<<<<` / `>>>>>>>`） | ✅ 通过 |
| `from agentmain import GeneraticAgent` 符号存在 | ✅ 通过 |
| 工作区 `git status` 干净 | ✅ 通过 |

> **未执行**：`frontends/tests/` 完整 pytest 套件（涉及 `requirements.txt` 依赖与真实桥接环境），待阶段 3 改动收窄后补齐。

## 九、阶段 3 改动收窄（务实收窄）

> 原则：**外挂增强，不改核心**。本次只做低风险、高价值的收窄，不重构深度定制的核心文件。

### 9.1 本次动作

- **品牌分离**：`README.md` 保持上游原版零 diff（未来 merge 无冲突）；新增 `HUIHUI.md` 承载慧惠差异说明（自有新增，上游永不触碰）。
- **安全清理**：删除泄漏明文 DeepSeek API key 的 `testDS.py`、调试快照 `check3_full.txt`、`test_reports/` 6 个测试产物。
- **目录归位**：`requst/`（拼写错误）→ `docs/requirements/`。

### 9.2 零冲突资产清单（上游不碰 · 未来 merge 自动无冲突）

| 资产 | 说明 |
|:---|:---|
| `core/` | soul 人格基线（`soul.py` / `soul_prompts.py` / `scenario_matcher.py` / `initializer.py`） |
| `skills/` | 五行流转引擎（五模块 + `skill_registry.py` + `root_auditor.py`） |
| `algorithms/` | 五行算法（`pzhongshu_analyzer.py` / `integration.py`） |
| `plugins/hooks.py`、`plugins/project_mode.py` | 慧惠自有插件 |
| `launch_huihui.pyw`、`huihui_initialized.flag` | 专属启动入口与标识 |
| `prompts/`、`tools/` | 场景数据、道境提取工具 |
| `HUIHUI.md`、`docs/requirements/` | 品牌文档与需求文档 |
| 顶层 `verify_*.py` / `skill_crystallization_test.py` | 慧惠自有回归脚本 |

### 9.3 冲突热点清单（未来 merge 必撞 · 裁决固定为「取本地 ours」）

> 这些文件是慧惠对上游核心的深度定制，未来任何 merge 都优先保留本地版本，上游同文件的改进按需手动 cherry-pick 吸收。

| 文件 | 冲突原因 |
|:---|:---|
| `agentmain.py` | `from core.soul_prompts import inject_soul_prompt` + `class GeneraticAgent` + `load_llm_sessions` 密钥逻辑 |
| `llmcore.py` | 双方独立重造模型层（`reload_mykeys` / 会话类） |
| `hub.pyw`、`launch.pyw` | 入口职责重造 |
| `TMWebDriver.py`、`simphtml.py` | 浏览器 / HTML 工具双边改 |
| `assets/sys_prompt.txt`、`assets/tools_schema.json` | 提示词与工具协议 |
| `memory/keychain.py`、`memory/ui_detect.py` | 记忆/凭据双造 |

### 9.4 收窄规范（未来新增能力时遵循）

1. **加文件不改文件**：新能力优先落在 `plugins/`、`skills/`、`core/` 等独立目录，或新增钩子，禁止直接改上游核心文件。
2. 必须改核心时，先在 [docs/UPSTREAM_TRIAGE.md](./UPSTREAM_TRIAGE.md) 补一条分诊记录，标注「冲突热点」。
3. 品牌/README 类每次 merge 固定「取本地」，差异写进 `HUIHUI.md` 而非侵占上游 README。

## 十、阶段 4 双轨 SLA（vendor branch 重塑）

> 目标：`main` = 上游镜像（未来 sync 零冲突）；`huihui` = 全部慧惠定制（发布/部署分支）。
> 执行日：2026-09-15。

### 10.1 重塑后分支拓扑

| 分支 | 角色 | tip | 说明 |
|:---|:---|:---|:---|
| `main` | 上游镜像 | `c68fa07` | = `upstream/main`(`1b6442f`) + 剥离 CI workflow 的提交 |
| `huihui` | 全定制 | `2590944` | 由 `integration/upstream-merge` 重命名而来；已 merge `upstream/main`（方案 A 裁决） |
| `upstream/main` | 上游 | `1b6442f` | 上游较诊断时（`86171ae`）已前进 3 个提交 |

### 10.2 关键动作

- `git branch -m integration/upstream-merge huihui` → `git push -u origin huihui`；删除远端 `integration/upstream-merge`。
- `git reset --hard upstream/main` → `git push --force origin main`，`main` 与上游对齐。
- 备份 tag `huihui-pre-sync-20260912` 指向 `4ea7e5d`（阶段 0 冻结点），回退命令 `git push --force origin 4ea7e5d:main`。

### 10.3 已知约束：token 无 `workflow` scope

上游 `main` 自带 `.github/workflows/desktop-ci.yml`、`desktop-release-package.yml`，当前 token 无 `workflow` 权限，无法推送工作流文件。故 `main` 镜像 = 上游内容 **剥离这 2 个 CI 文件**（提交 `c68fa07`）。该剥离逻辑已固化进同步脚本（见 §十一）。

## 十一、阶段 6 自动化（双轨同步脚本）

### 11.1 脚本

新增 `tools/sync-upstream.ps1`。用法：

```powershell
powershell -NoProfile -File tools/sync-upstream.ps1
```

流程：

1. `git fetch upstream --prune`。
2. 计算 `main...upstream/main` 的 ahead/behind 并彩字输出。
3. `behind=0` → 提示已最新并退出。
4. `behind>0` → `main`：`reset --hard upstream/main` → 剥离 `.github/workflows/*` → `push --force origin main`。
5. `huihui`：`git merge main --no-ff`；冲突则提示「解决后 `git add -A; git commit`」并 `exit 1`。
6. `git push origin huihui`。

### 11.2 CI 漂移提醒（待启用）

本次不创建 `.github/workflows/upstream-drift.yml`（token 无 `workflow` scope）。启用前提：token 补充 `workflow` scope 后，新增一个按周期检查 `upstream/main` 领先并告警的 workflow 即可。

### 11.3 首次同步执行实录（2026-09-15）

`git merge --no-ff upstream/main` 吸收上游 3 个提交（`1b6442f`/`f07bfc5`/`96be945`），实测冲突 2 文件：

| 文件 | 冲突来源 | 裁决 |
|:---|:---|:---|
| `agentmain.py` | `f07bfc5` abort() 一方删除/一方改写「强制唤醒 recv()」块 | **取本地 ours**（丢弃 `_INFLIGHT` 机制，保留简化版 `abort()`） |
| `llmcore.py` | `f07bfc5` 顶部 `_INFLIGHT`/urllib3 钩子 + `_stream_with_retry` 加 `sess._tid` | **取本地 ours**（慧惠已 generator 重造模型层，无 `active_response`，机制不适用） |

吸收成功的：`1b6442f`（`ga.py`、`assets/insight_fixed_structure{,_en}.txt` 提示词收敛）、`96be945`（`memory/vision_sop.md` 视觉后端文档）。合并提交 `2590944`，`core/`、`skills/`、`algorithms/` 等慧惠零冲突资产未受影响，核心模块 `py_compile` 通过。