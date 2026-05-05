## S1-2: 将 Soul.py 注入 AgentLoop

**任务编号**：S1-2  
**任务名称**：将 Soul 注入 AgentLoop  
**优先级**：P0  
**预估工作量**：1天  
**依赖**：S1-1 已完成

### 任务目标

让慧惠在每次生成回复时，其 Soul（核心价值观、人格基线、道德边界）都能自动注入 LLM 上下文，作为最高行为准则。同时在回复生成后进行道德边界检查，若越界则返回拒绝理由。

### 操作文件
- `core/soul_prompts.py`（新建）
- `agentmain.py`（修改，仅修改 `get_system_prompt()` 函数）
- 不改动其他 GenericAgent 核心文件

### 具体指令

#### 1. 新建 `core/soul_prompts.py`
- 负责从 `core.soul` 获取 Soul 实例，并将其编译为 LLM 可用的 system prompt 片段
- 提供函数 `inject_soul_prompt(base_prompt: str) -> str`，将 Soul prompt 插入到基础 prompt 的最前面
- Soul prompt 注入格式为 `[系统身份设定 - 最高优先级]\n{Soul.to_system_prompt()}\n\n{原始基础提示词}`

#### 2. 修改 `agentmain.py` 的 `get_system_prompt()` 函数
- 在函数返回前，调用 `inject_soul_prompt()`，确保 Soul prompt 每次都注入
- 不改变 `get_system_prompt()` 的原有逻辑，仅增加钩子

#### 3. 道德边界检查
- 在 `soul_prompts.py` 中新增函数 `check_response(text: str) -> tuple[bool, str]`
- 调用 `Soul.check_moral_boundary()` 检查 LLM 生成内容
- 越界则返回 `(False, "[系统拒绝] 此回复越过道德边界：{被触发的边界名称}。")`
- 通过则返回 `(True, text)`

#### 4. 验证
- 编写 `verify_s1_2.py` 验证脚本：
  - 确认注入后的 prompt 包含“慧惠”
  - 确认注入后的 prompt 包含“我命由我不由天”
  - 确认注入后的 prompt 长度不超过原有长度 +500 tokens
  - 确认 `check_response()` 对越界内容返回 False
  - 确认 `check_response()` 对正常内容返回 True
- 运行验证脚本，全部通过后输出 “S1-2 ALL TESTS PASSED”

### 验收标准
- LLM 回答对“你是谁”的问题，回复中包含“慧惠”或“小惠”
- `get_system_prompt()` 每次调用均注入 Soul prompt
- 道德边界检查正确拒绝越界内容