# 上游同步 · 冲突分诊表（UPSTREAM_TRIAGE）

> **关联**：[UPSTREAM_SYNC.md](./UPSTREAM_SYNC.md)（分叉治理诊断 + 执行实录）
> **用途**：依据诊断结果（22 modified + 79 add/add + 12 delete/delete ≈ 113 个潜在冲突点）逐条预填裁决取向，作为**未来任何 `upstream/main` → `huihui` merge 的裁决基线与回归清单**。
> **状态**：首次同步已于 2026-09-15 执行完毕（阶段 2 合并提交 `b24f96c` → 首次同步合并提交 `2590944`）。下表为预填基线，实际执行结果与关键取舍见 [UPSTREAM_SYNC.md 第八、九、十一章](./UPSTREAM_SYNC.md)。
> **裁决取值**：取本地(ours) / 取上游(theirs) / 合并(union) / 逐块人工 / 核对后整取 / 自动。
> **优先级**：P0 核心代码·最高 / P1 重要 / P2 一般 / P3 文本资产。
> **机读副本**：[`tools/triage.csv`](../tools/triage.csv)（与本文表格同源）。

| 序号 | 路径 | 类别 | 冲突类型 | 建议裁决 | 优先级 | 理由 | 负责人 | 备注 |
|---|---|---|---|---|---|---|---|---|
| 1 | .gitignore | 配置 | modify/modify | 合并(union) | P1 | 忽略规则双方各有新增，两段合并即可 |  |  |
| 2 | README.md | 文档·品牌 | modify/modify | 取本地(ours) | P1 | 保留慧惠品牌叙事；上游更新可另写入 HUIHUI.md |  |  |
| 3 | agent_loop.py | 核心代码 | modify/modify | 逐块人工 | P0 | 主循环；双方均改工具分发/回调，必须逐块核对 |  |  |
| 4 | agentmain.py | 核心代码 | modify/modify | 逐块人工 | P0 | 入口/装配层 |  |  |
| 5 | ga.py | 核心代码 | modify/modify | 逐块人工 | P0 | 模型与会话装配 |  |  |
| 6 | TMWebDriver.py | 核心·浏览器 | modify/modify | 逐块人工 | P0 | 浏览器驱动，双边均改 |  |  |
| 7 | simphtml.py | 核心·HTML | modify/modify | 逐块人工 | P1 | 网页简化，核对上游优化 |  |  |
| 8 | launch.pyw | 启动 | modify/modify | 取本地(ours) | P1 | 慧惠启动入口 |  |  |
| 9 | mykey_template.py | 配置模板 | modify/modify | 合并(union) | P2 | 仅键/注释模板，合并 |  |  |
| 10 | assets/sys_prompt.txt | 提示词 | modify/modify | 逐块人工 | P1 | 系统提示词；语气/规则差异需人工确认 |  |  |
| 11 | assets/tools_schema.json | 工具schema | modify/modify | 逐块人工 | P0 | 与 9 原子工具一致性直接相关 |  |  |
| 12 | assets/global_mem_insight_template.txt | 提示词 | modify/modify | 合并(union) | P2 | 模板文本 |  |  |
| 13 | assets/insight_fixed_structure.txt | 提示词 | modify/modify | 合并(union) | P2 | 模板文本 |  |  |
| 14 | memory/adb_ui.py | 记忆·代码 | modify/modify | 逐块人工 | P1 | ADB UI 自动化 |  |  |
| 15 | memory/ljqCtrl.py | 记忆·代码 | modify/modify | 逐块人工 | P1 | 键鼠/控制 |  |  |
| 16 | memory/autonomous_operation_sop.md | SOP | modify/modify | 合并(union) | P2 | SOP 文本，追加合并 |  |  |
| 17 | memory/ljqCtrl_sop.md | SOP | modify/modify | 合并(union) | P2 | SOP 文本 |  |  |
| 18 | memory/memory_management_sop.md | SOP·关键 | modify/modify | 逐块人工 | P1 | 记忆管理规则，与 L0-L4 强相关 |  |  |
| 19 | memory/plan_sop.md | SOP·关键 | modify/modify | 逐块人工 | P1 | 任务规划 SOP |  |  |
| 20 | memory/scheduled_task_sop.md | SOP | modify/modify | 合并(union) | P2 | SOP 文本 |  |  |
| 21 | memory/tmwebdriver_sop.md | SOP | modify/modify | 合并(union) | P2 | SOP 文本 |  |  |
| 22 | memory/web_setup_sop.md | SOP | modify/modify | 合并(union) | P2 | SOP 文本 |  |  |
| 23 | CONTRIBUTING.md | 上游文档 | add/add | 取上游(theirs) | P3 | 英文贡献指南，通用 |  |  |
| 24 | LICENSE | 许可 | add/add | 取本地(ours) | P3 | 同为 MIT，取本地即可 |  |  |
| 25 | hub.pyw | 入口/服务 | add/add | 逐块人工 | P1 | 双方各造，核对职责边界 |  |  |
| 26 | llmcore.py | 核心·模型层 | add/add | 逐块人工 | P0 | ⚠ 双方独立重造模型层，最高风险，务必逐块对照 |  |  |
| 27 | pyproject.toml | 构建配置 | add/add | 合并 | P1 | 依赖需取并集 |  |  |
| 28 | mykey_template_en.py | 配置模板 | add/add | 合并(union) | P3 | 英文键模板 |  |  |
| 29 | assets/GenericAgent_Technical_Report.pdf | 文档 | add/add | 取本地(ours) | P3 | 技术报告（取更全者） |  |  |
| 30 | assets/code_run_header.py | 代码片段 | add/add | 取本地(ours) | P2 | code_run 头 |  |  |
| 31 | assets/global_mem_insight_template_en.txt | 提示词 | add/add | 核对后整取 | P3 | en 模板 |  |  |
| 32 | assets/insight_fixed_structure_en.txt | 提示词 | add/add | 核对后整取 | P3 | en 模板 |  |  |
| 33 | assets/sys_prompt_en.txt | 提示词 | add/add | 核对后整取 | P3 | en 模板 |  |  |
| 34 | assets/tools_schema_cn.json | 工具schema | add/add | 逐块人工 | P1 | 中文 tools schema，与工具一致性 |  |  |
| 35 | assets/images/* | 图片资产 | add/add | 取本地(ours) | P3 | 品牌图：bar/feishu_group/logo/workflow.jpg |  |  |
| 36 | assets/tmwd_cdp_bridge/* | 浏览器桥 | add/add | 逐块人工 | P1 | CDP 桥（js/manifest/popup），功能关键 |  |  |
| 37 | frontends/*.py | 前端 | add/add | 取本地(ours) | P1 | 多前端定制（chatapp_common/continue_cmd/dcapp/desktop_pet_v2/dingtalkapp/fsapp/qqapp/qtapp/stapp/stapp2/tgapp/wechatapp/wecomapp） |  |  |
| 38 | frontends/DESKTOP_PET_README.md | 前端文档 | add/add | 取本地(ours) | P3 | 桌面宠物说明 |  |  |
| 39 | frontends/chat_bubble.png | 前端资源 | add/add | 取本地(ours) | P3 | 资源图 |  |  |
| 40 | frontends/skins/* | 前端皮肤 | add/add | 取本地(ours) | P3 | 皮肤整套（boy/dinosaur/doux/glube/line/mort/tard/vita），整目录取本地 |  |  |
| 41 | memory/L4_raw_sessions/compress_session.py | 记忆·代码 | add/add | 逐块人工 | P1 | L4 会话压缩 |  |  |
| 42 | memory/autonomous_operation_sop/* | SOP+代码 | add/add | 取本地(ours) | P2 | helper.py + task_planning.md |  |  |
| 43 | memory/github_contribution_sop.md | SOP | add/add | 合并(union) | P3 | SOP 文本 |  |  |
| 44 | memory/keychain.py | 记忆·代码 | add/add | 逐块人工 | P1 | ⚠ 双方独立重造，涉及凭据，务必核对 |  |  |
| 45 | memory/memory_cleanup_sop.md | SOP | add/add | 合并(union) | P2 | SOP 文本 |  |  |
| 46 | memory/ocr_utils.py | 记忆·代码 | add/add | 核对后整取 | P2 | OCR 工具 |  |  |
| 47 | memory/procmem_scanner_sop.md | SOP | add/add | 合并(union) | P3 | SOP 文本 |  |  |
| 48 | memory/supervisor_sop.md | SOP | add/add | 合并(union) | P2 | SOP 文本 |  |  |
| 49 | memory/ui_detect.py | 记忆·代码 | add/add | 逐块人工 | P2 | UI 检测 |  |  |
| 50 | memory/vision_api.template.py | 记忆·模板 | add/add | 合并(union) | P2 | 视觉 API 模板 |  |  |
| 51 | memory/vision_sop.md | SOP | add/add | 合并(union) | P2 | SOP 文本 |  |  |
| 52 | plugins/langfuse_tracing.py | 插件 | add/add | 取上游(theirs) | P2 | 第三方追踪插件，通用 |  |  |
| 53 | reflect/autonomous.py | 自省·代码 | add/add | 逐块人工 | P1 | 自主逻辑，可能有本地定制 |  |  |
| 54 | reflect/scheduler.py | 自省·代码 | add/add | 逐块人工 | P1 | 调度器 |  |  |
| 55 | WELCOME_NEW_USER.md | 已删除 | delete/delete | 自动（双方已删） | — | 双方均删除 → 一般不产生冲突，确认即可 |  |  |
| 56 | sidercall.py | 已删除 | delete/delete | 自动（双方已删） | — | 双方均删除 → 一般不产生冲突，确认即可 |  |  |
| 57 | stapp.py | 已删除 | delete/delete | 自动（双方已删） | — | 双方均删除 → 一般不产生冲突，确认即可 |  |  |
| 58 | tgapp.py | 已删除 | delete/delete | 自动（双方已删） | — | 双方均删除 → 一般不产生冲突，确认即可 |  |  |
| 59 | assets/cookie_grabber/background.js | 已删除 | delete/delete | 自动（双方已删） | — | 双方均删除 → 一般不产生冲突，确认即可 |  |  |
| 60 | assets/cookie_grabber/content.js | 已删除 | delete/delete | 自动（双方已删） | — | 双方均删除 → 一般不产生冲突，确认即可 |  |  |
| 61 | assets/cookie_grabber/manifest.json | 已删除 | delete/delete | 自动（双方已删） | — | 双方均删除 → 一般不产生冲突，确认即可 |  |  |
| 62 | assets/cookie_grabber/popup.html | 已删除 | delete/delete | 自动（双方已删） | — | 双方均删除 → 一般不产生冲突，确认即可 |  |  |
| 63 | assets/cookie_grabber/popup.js | 已删除 | delete/delete | 自动（双方已删） | — | 双方均删除 → 一般不产生冲突，确认即可 |  |  |
| 64 | assets/ljq_web_driver.user.js | 已删除 | delete/delete | 自动（双方已删） | — | 双方均删除 → 一般不产生冲突，确认即可 |  |  |
| 65 | assets/make_prompts.py | 已删除 | delete/delete | 自动（双方已删） | — | 双方均删除 → 一般不产生冲突，确认即可 |  |  |
| 66 | memory/mem_scanner_sop.md | 已删除 | delete/delete | 自动（双方已删） | — | 双方均删除 → 一般不产生冲突，确认即可 |  |  |

## 一、本次同步实裁摘要（2026-09-15）

### 1.1 阶段 2：`integration/upstream-merge`（合并提交 `b24f96c`）

预期冲突 113，实测需裁决 **48**：

| 裁决类型 | 数量 | 代表文件 |
|:---|:---|:---|
| 取上游（theirs） | 13 | `pyproject.toml`、`memory/ui_detect.py`、`.gitignore`、`memory/vision_api.template.py` 等 |
| 取本地（ours） | 27（13＋14） | `agentmain.py`、`llmcore.py`、`assets/tools_schema.json`、`TMWebDriver.py`、`hub.pyw`、`memory/keychain.py` 等 |
| 文本合并 | 8 | `agent_loop.py`、`ga.py`、`assets/sys_prompt.txt`、`memory/*.md` 等 |

### 1.2 首次同步：`git merge --no-ff upstream/main`（合并提交 `2590944`）

吸收上游 3 个提交（`1b6442f` / `f07bfc5` / `96be945`），实测冲突 **2** 文件：

| 文件 | 冲突来源 | 裁决 |
|:---|:---|:---|
| `agentmain.py` | `f07bfc5`：一方删除 / 一方改写「强制唤醒 `recv()`」块 | **取本地 ours**（丢弃 `_INFLIGHT` 机制，保留简化版 `abort()`） |
| `llmcore.py` | `f07bfc5`：顶部 `_INFLIGHT` / urllib3 钩子 + `_stream_with_retry` 加 `sess._tid` | **取本地 ours**（慧惠已 generator 重造模型层，无 `active_response`，机制不适用） |

无冲突吸收：`1b6442f`（`ga.py`、`assets/insight_fixed_structure{,_en}.txt` 提示词收敛）、`96be945`（`memory/vision_sop.md` 视觉后端文档）。

## 二、冲突热点（未来 merge 裁决固定为「取本地 ours」）

见 [UPSTREAM_SYNC.md §9.3](./UPSTREAM_SYNC.md)：

`agentmain.py`、`llmcore.py`、`hub.pyw`、`launch.pyw`、`TMWebDriver.py`、`simphtml.py`、`assets/sys_prompt.txt`、`assets/tools_schema.json`、`memory/keychain.py`、`memory/ui_detect.py`

## 三、维护约定

1. **加文件不改文件**：新能力优先落在 `plugins/`、`skills/`、`core/` 等独立目录，或新增钩子，禁止直接改上游核心文件。
2. 必须改核心时，先在本表补一条分诊记录，标注「冲突热点」。
3. 品牌 / README 类每次 merge 固定「取本地」，差异写进 [`HUIHUI.md`](../HUIHUI.md) 而非侵占上游 `README.md`。
4. 本表与 [`tools/triage.csv`](../tools/triage.csv) 同源，改动请同步两者。
