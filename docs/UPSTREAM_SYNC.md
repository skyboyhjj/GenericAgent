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
| 0 备份冻结 | `--mirror` 镜像 + 打 tag `huihui-pre-sync-*` | 待办 |
| 1 诊断 | 本实录 | ✅ 完成 |
| 2 一次性对齐 | `integration/` 分支 `git merge upstream/main --no-ff` | ✅ 完成（`b24f96c`） |
| 3 改动收窄 | 定制下沉至 `huihui/`、`wuxing/` 等独立目录 | **建议优先** |
| 4 双轨 SLA | `main`≈上游 / `huihui`=全定制 | 待办 |
| 6 自动化 | `tools/sync-upstream.ps1` + GitHub Actions 漂移提醒 | 待办 |

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