# GA 结晶机制自动化验证实验方案

> **执行方式**：由 Qoder 编写自动化测试脚本，无需人工逐个执行任务。
> **交付物**：`memory/verify_ga_crystallization.py`（GA 结晶机制专项验证脚本）


## 一、实验目标

通过自动化脚本，以编程方式验证 GA 的技能结晶机制：
1. 确认结晶在什么条件下触发
2. 确认结晶产物的格式是否符合 L0 公理
3. 确认 L1 索引是否同步更新
4. 为 Sprint 3 的 `WoodGenerator` 设计提供实测数据支撑


## 二、自动化测试设计

由于 GA 是命令行驱动的 Agent，不提供程序化 API，自动化测试使用 **GA 命令行模式**。

### 2.1 GA 命令行模式

GA 支持通过命令行直接提交任务，这为自动化测试提供了接口：

```bash
# 在 GenericAgent 根目录下执行，将任务指令写入文件，由 GA 处理
python agentmain.py --task ga_test --input "帮我计算 1 到 100 的累加和"
```

任务完成后，GA 会在 `temp/ga_test/output.txt` 中输出结果。

### 2.2 测试流程

每个实验用例分为三个阶段：

```
┌─────────────┐     ┌─────────────┐     ┌─────────────┐
│ 1. 快照阶段  │ →  │ 2. 执行阶段  │ →  │ 3. 比对阶段  │
│ 记录基线状态  │     │ 运行 GA 任务 │     │ 分析产物变化  │
└─────────────┘     └─────────────┘     └─────────────┘
```

**阶段 1：快照阶段**
- 记录 `memory/` 目录下所有文件的**文件名集合**和 `global_mem_insight.txt` 的行数（作为基线）

**阶段 2：执行阶段**
- 调用 `python agentmain.py --task {task_id} --input "{任务指令}"`
- 等待进程结束（设置超时 120 秒）
- 记录退出码和输出摘要

**阶段 3：比对阶段**
- 对比执行前后的文件集合，识别**新增文件**
- 对比 `global_mem_insight.txt` 的行数变化，提取**新增条目**
- 若有新增 `*_sop.md` 文件，分析其内容是否符合 L0 公理：
  - 是否含易变状态
  - 文件行数是否在合理范围
  - 内容是否聚焦于前置条件和典型坑点


## 三、测试用例设计

### 用例 1：简单计算任务（预期无结晶）

| 属性 | 值 |
|:---|:---|
| 任务 ID | `crystal_test_01` |
| 任务指令 | 帮我计算 1 到 100 的累加和，只告诉我结果就行。 |
| 预期结晶 | 否 |
| 预期理由 | 单步 code_run，过于简单，不满足复杂性要求 |

### 用例 2：多步工具调用任务（预期触发结晶）

| 属性 | 值 |
|:---|:---|
| 任务 ID | `crystal_test_02` |
| 任务指令 | 请帮我完成：1. 在 temp 目录下创建 ga_test 子目录；2. 创建一个 Python 脚本 check_files.py，检查 temp 目录下所有 .txt 文件的大小和行数；3. 运行这个脚本；4. 如果运行成功，把这个脚本的用途和使用方法记录下来 |
| 预期结晶 | **是（可能触发）** |
| 预期理由 | 多工具调用（file_write、code_run、file_read），有明确复用价值 |

### 用例 3：与已有技能重复的任务（预期无结晶）

| 属性 | 值 |
|:---|:---|
| 任务 ID | `crystal_test_03` |
| 任务指令 | 帮我在 temp 目录下搜索所有 .py 文件，找出包含 print 语句的文件，把文件名和行数告诉我。 |
| 预期结晶 | 否 |
| 预期理由 | 与 GA 已有文件搜索能力高度重复，应复用已有技能 |

### 用例 4：外部信息获取 + 多工具编排（预期触发结晶）

| 属性 | 值 |
|:---|:---|
| 任务 ID | `crystal_test_04` |
| 任务指令 | 请帮我：1. 访问 https://fudankw.cn/sophub/ 看看它是什么；2. 找到最新发布的 3 个 SOP 的名称和描述；3. 保存到 temp/sophub_latest.txt；4. 读取文件向我做简短汇报 |
| 预期结晶 | **是（高概率触发）** |
| 预期理由 | 外部信息获取 + 多工具编排 + 明确跨会话复用价值 |

### 用例 5：错误恢复场景（预期触发结晶）

| 属性 | 值 |
|:---|:---|
| 任务 ID | `crystal_test_05` |
| 任务指令 | 帮我：1. 尝试访问一个不存在的网站 https://this-does-not-exist-12345.com；2. 如果访问失败，写一个 Python 脚本测试三个常见网站的连通性（baidu.com, github.com, sophub.fudankw.cn）；3. 把测试结果汇总成表格保存到 temp/site_status.txt |
| 预期结晶 | **是（可能触发）** |
| 预期理由 | 含错误处理分支 + 多工具调用 + 典型的“踩坑后学会”场景 |


## 四、交付物规格

### 4.1 主脚本 `memory/verify_ga_crystallization.py`

```python
"""
GA 结晶机制自动化验证脚本

通过 GA 命令行模式自动执行递进式任务，
验证技能结晶的触发条件及产物质量。
"""

import os, sys, json, shutil, subprocess, time
from pathlib import Path
from datetime import datetime
from dataclasses import dataclass, field
from typing import List, Optional

# 项目根目录
ROOT = Path(__file__).resolve().parent.parent
MEMORY_DIR = ROOT / "memory"
TEMP_DIR = ROOT / "temp"

@dataclass
class Snapshot:
    """某时刻的 memory/ 目录快照"""
    files: set
    l1_lines: int
    l1_content: str

@dataclass
class TaskResult:
    """单次任务执行结果"""
    task_id: str
    exit_code: int
    output_summary: str
    elapsed_seconds: float

@dataclass
class CrystalAnalysis:
    """结晶产物分析"""
    new_files: List[str]
    new_sop_files: List[str]
    l1_new_lines: List[str]
    sop_analysis: dict  # 每个新 SOP 的内容分析

class GACrystallizationTester:
    """GA 结晶机制自动化测试器"""
    
    def __init__(self):
        self.baseline: Optional[Snapshot] = None
    
    def take_snapshot(self) -> Snapshot:
        """记录 memory/ 目录的当前快照"""
        files = set()
        if MEMORY_DIR.exists():
            for f in MEMORY_DIR.rglob("*"):
                if f.is_file():
                    files.add(str(f.relative_to(MEMORY_DIR)))
        
        insight_path = MEMORY_DIR / "global_mem_insight.txt"
        if insight_path.exists():
            content = insight_path.read_text(encoding="utf-8")
            lines = content.strip().split("\n")
        else:
            content = ""
            lines = []
        
        return Snapshot(files=files, l1_lines=len(lines), l1_content=content)
    
    def run_task(self, task_id: str, instruction: str, 
                 timeout: int = 120) -> TaskResult:
        """通过 GA 命令行模式执行一个任务"""
        task_dir = TEMP_DIR / task_id
        os.makedirs(task_dir, exist_ok=True)
        
        # 写入任务指令
        input_file = task_dir / "input.txt"
        input_file.write_text(instruction, encoding="utf-8")
        
        # 调用 GA 命令行
        start = time.time()
        try:
            result = subprocess.run(
                [sys.executable, "agentmain.py", "--task", task_id],
                cwd=str(ROOT),
                capture_output=True, text=True,
                timeout=timeout
            )
            elapsed = time.time() - start
            exit_code = result.returncode
            
            # 读取 GA 输出
            output_file = task_dir / "output.txt"
            if output_file.exists():
                output = output_file.read_text(encoding="utf-8")[:500]
            else:
                output = result.stdout[:500] + "\n" + result.stderr[:500]
        except subprocess.TimeoutExpired:
            exit_code = -1
            elapsed = timeout
            output = "[TIMEOUT] Task exceeded time limit"
        
        return TaskResult(
            task_id=task_id,
            exit_code=exit_code,
            output_summary=output.strip(),
            elapsed_seconds=round(elapsed, 1)
        )
    
    def compare_snapshots(self, before: Snapshot, 
                         after: Snapshot) -> CrystalAnalysis:
        """比对前后快照，分析结晶产物"""
        new_files = list(after.files - before.files)
        new_sop_files = [f for f in new_files if f.endswith("_sop.md")]
        
        # L1 新增行
        before_lines = set(before.l1_content.strip().split("\n"))
        after_lines = set(after.l1_content.strip().split("\n"))
        l1_new = list(after_lines - before_lines)
        
        # 分析每个新 SOP 文件
        sop_analysis = {}
        for sop_file in new_sop_files:
            path = MEMORY_DIR / sop_file
            content = path.read_text(encoding="utf-8") if path.exists() else ""
            sop_analysis[sop_file] = {
                "line_count": len(content.strip().split("\n")),
                "has_volatile_state": self._check_volatile(content),
                "has_action_ref": self._check_action_reference(content),
                "content_preview": content[:300]
            }
        
        return CrystalAnalysis(
            new_files=new_files,
            new_sop_files=new_sop_files,
            l1_new_lines=l1_new,
            sop_analysis=sop_analysis
        )
    
    def _check_volatile(self, content: str) -> bool:
        """检查内容是否包含易变状态"""
        import re
        patterns = [
            r'\b\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}\b',  # 时间戳
            r'\bPID[:\s]*\d+\b',
            r'/tmp/[a-zA-Z0-9_]+',  # 临时路径
        ]
        return any(re.search(p, content) for p in patterns)
    
    def _check_action_reference(self, content: str) -> bool:
        """检查是否引用了具体的工具调用结果"""
        keywords = ["code_run", "file_read", "web_scan", 
                    "file_write", "成功", "执行"]
        return any(kw in content for kw in keywords)
    
    def run_test_suite(self):
        """运行完整测试套件"""
        print("=" * 60)
        print("GA 结晶机制自动化验证")
        print(f"开始时间: {datetime.now().isoformat()}")
        print("=" * 60)
        
        # 记录基线
        print("\n[1/4] 记录基线快照...")
        self.baseline = self.take_snapshot()
        print(f"  基线文件数: {len(self.baseline.files)}")
        print(f"  L1 基线行数: {self.baseline.l1_lines}")
        
        # 执行测试用例
        test_cases = [
            ("crystal_test_01", 
             "帮我计算 1 到 100 的累加和，只告诉我结果就行。",
             False, "简单计算，预期无结晶"),
            ("crystal_test_02",
             "请帮我完成：1. 在 temp 目录下创建 ga_test 子目录；2. 创建一个 Python 脚本 check_files.py，检查 temp 目录下所有 .txt 文件的大小和行数；3. 运行这个脚本；4. 如果运行成功，把这个脚本的用途和使用方法记录下来",
             True, "多步工具调用，预期触发结晶"),
            ("crystal_test_03",
             "帮我在 temp 目录下搜索所有 .py 文件，找出包含 print 语句的文件，把文件名和行数告诉我。",
             False, "与已有技能重复，预期无结晶"),
            ("crystal_test_04",
             "请帮我：1. 访问 https://fudankw.cn/sophub/ 看看它是什么；2. 找到最新发布的 3 个 SOP 的名称和描述；3. 保存到 temp/sophub_latest.txt；4. 读取文件向我做简短汇报",
             True, "外部信息获取+多工具编排，预期高概率触发"),
            ("crystal_test_05",
             "帮我：1. 尝试访问一个不存在的网站 https://this-does-not-exist-12345.com；2. 如果访问失败，写一个 Python 脚本测试三个常见网站的连通性（baidu.com, github.com, fudankw.cn）；3. 把测试结果汇总成表格保存到 temp/site_status.txt",
             True, "含错误恢复+多工具，预期可能触发"),
        ]
        
        total_tasks = len(test_cases)
        results_summary = []
        
        for i, (task_id, instruction, expect_crystal, reason) in enumerate(test_cases, 1):
            print(f"\n[2.{i}/{total_tasks}] 执行 {task_id}")
            print(f"  预期: {'触发结晶' if expect_crystal else '无结晶'}")
            print(f"  理由: {reason}")
            
            task_result = self.run_task(task_id, instruction)
            print(f"  退出码: {task_result.exit_code}")
            print(f"  耗时: {task_result.elapsed_seconds}s")
            
            # 每次任务后取快照并比对
            after = self.take_snapshot()
            analysis = self.compare_snapshots(self.baseline, after)
            
            crystal_triggered = len(analysis.new_sop_files) > 0
            
            results_summary.append({
                "task_id": task_id,
                "expect_crystal": expect_crystal,
                "crystal_triggered": crystal_triggered,
                "match_expectation": crystal_triggered == expect_crystal,
                "new_sop_files": analysis.new_sop_files,
                "l1_new_lines": analysis.l1_new_lines,
                "sop_analysis": analysis.sop_analysis
            })
            
            # 输出该任务的结果
            if crystal_triggered:
                print(f"  ✅ 结晶触发！新增 SOP: {analysis.new_sop_files}")
                for name, info in analysis.sop_analysis.items():
                    print(f"     └─ {name}: {info['line_count']}行, "
                          f"易变状态:{info['has_volatile_state']}, "
                          f"行动引用:{info['has_action_ref']}")
            else:
                print(f"  ⏭️  无结晶")
            
            # 更新基线（以防后续任务受前序任务影响）
            self.baseline = after
        
        # 汇总报告
        print("\n" + "=" * 60)
        print("[3/4] 汇总报告")
        print("=" * 60)
        
        crystal_cases = [r for r in results_summary if r["crystal_triggered"]]
        no_crystal_cases = [r for r in results_summary if not r["crystal_triggered"]]
        
        print(f"\n触发结晶的任务 ({len(crystal_cases)}/{total_tasks}):")
        for r in crystal_cases:
            print(f"  ✅ {r['task_id']}: {r['new_sop_files']}")
        
        print(f"\n未触发结晶的任务 ({len(no_crystal_cases)}/{total_tasks}):")
        for r in no_crystal_cases:
            match_str = "符合预期" if r["match_expectation"] else "⚠️ 与预期不符"
            print(f"  ─ {r['task_id']}: {match_str}")
        
        # 产物质量分析
        print("\n[4/4] 产物质量分析:")
        for r in crystal_cases:
            for name, info in r["sop_analysis"].items():
                issues = []
                if info["has_volatile_state"]:
                    issues.append("含易变状态")
                if not info["has_action_ref"]:
                    issues.append("无行动引用")
                if info["line_count"] > 100:
                    issues.append(f"过长({info['line_count']}行)")
                
                status = "⚠️ " + ", ".join(issues) if issues else "✅ 通过"
                print(f"  {status} | {name}: {info['line_count']}行, "
                      f"预览: {info['content_preview'][:100]}...")
        
        # 最终判定
        all_pass = all(
            r["match_expectation"] and 
            all(not info["has_volatile_state"] and info["has_action_ref"]
                for info in r["sop_analysis"].values())
            for r in crystal_cases
        )
        
        if all_pass:
            print("\n✅ GA 结晶验证全部通过")
        else:
            print("\n⚠️ 部分验证项需要人工审查（见上表）")
        
        return 0 if all_pass else 1


if __name__ == "__main__":
    tester = GACrystallizationTester()
    sys.exit(tester.run_test_suite())
```

### 4.2 关键约束

- **测试时间**：每个任务超时 120 秒，全部测试预计耗时 5-10 分钟
- **不修改 GA 核心代码**：仅通过命令行调用，与 GA 内核完全解耦
- **产物分析只读**：测试脚本只读取 `memory/` 目录，不写入任何文件
- **历史测试兼容**：确保 `verify_s2_6.py` 等已有测试依然通过


## 五、交付清单

| 文件 | 说明 |
|:---|:---|
| `memory/verify_ga_crystallization.py` | GA 结晶机制自动化验证脚本（主交付物） |
| - | 无需新建其他文件，测试数据在 `temp/` 中自动管理 |