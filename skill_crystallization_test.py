#!/usr/bin/env python3
"""
GenericAgent Skill结晶验证脚本 v1.0
====================================
功能：
  - 4个递进式任务串行执行，共享同一Agent实例
  - 自动检测memory目录变化（新增/修改文件）
  - 追踪L1索引、L2事实、L3 SOP的变化
  - 对比首次执行与复用执行的效果差异
  - 生成完整验证报告

使用方式：
  cd /path/to/GenericAgent
  python skill_crystallization_test.py

依赖：
  - GenericAgent已安装并可正常运行（mykey.py已配置）
  - Python 3.10+
"""

import threading
import queue
import os
import sys
import time
import json
import signal
import hashlib
from datetime import datetime
from pathlib import Path


# ============================================================
# 配置区
# ============================================================

# 测试任务列表：（标签, 任务描述, 超时秒数）
TEST_TASKS = [
    ("环境探测", "帮我查看当前Python环境安装了哪些包", 120),
    ("安装+执行", "安装mootdx库，并用它查询平安银行（代码000001）最近的股票价格", 300),
    ("脚本固化", "帮我写一个Python脚本，统计当前目录下所有.md文件的行数，结果按行数从多到少排序", 180),
    ("Skill复用", "再帮我查询招商银行（代码600036）的股票价格", 180),
]

# memory目录路径（相对于agent_dir）
MEMORY_DIR = "memory"

# 任务间隔等待秒数（让蒸馏完成）
TASK_INTERVAL = 5

# 报告输出目录
REPORT_DIR = "test_reports"


# ============================================================
# Memory快照工具
# ============================================================

class MemorySnapshot:
    """memory目录状态快照，支持差异对比"""

    def __init__(self, memory_dir):
        self.memory_dir = memory_dir
        self.timestamp = datetime.now().isoformat()
        self.files = {}       # filename -> {size, mtime, md5}
        self.l1_content = ""  # global_mem_insight.txt 内容
        self.l2_content = ""  # global_mem.txt 内容

    def take(self):
        """拍摄当前快照"""
        self.timestamp = datetime.now().isoformat()
        self.files = {}

        if not os.path.exists(self.memory_dir):
            return self

        for f in os.listdir(self.memory_dir):
            filepath = os.path.join(self.memory_dir, f)
            if not os.path.isfile(filepath):
                continue
            try:
                stat = os.stat(filepath)
                with open(filepath, 'rb') as fp:
                    md5 = hashlib.md5(fp.read()).hexdigest()
                self.files[f] = {
                    "size": stat.st_size,
                    "mtime": stat.st_mtime,
                    "md5": md5,
                }
            except (OSError, PermissionError):
                continue

        # 单独记录L1、L2内容
        self.l1_content = self._read_file("global_mem_insight.txt")
        self.l2_content = self._read_file("global_mem.txt")

        return self

    def diff(self, other):
        """
        对比两个快照的差异
        other: 之前的快照
        返回: {new_files, deleted_files, modified_files, l1_changed, l2_changed}
        """
        result = {
            "new_files": [],
            "deleted_files": [],
            "modified_files": [],
            "l1_changed": False,
            "l2_changed": False,
        }

        for f, info in self.files.items():
            if f not in other.files:
                result["new_files"].append(f)
            elif info["md5"] != other.files[f]["md5"]:
                result["modified_files"].append(f)

        for f in other.files:
            if f not in self.files:
                result["deleted_files"].append(f)

        result["l1_changed"] = self.l1_content != other.l1_content
        result["l2_changed"] = self.l2_content != other.l2_content

        return result

    def _read_file(self, filename):
        """安全读取文件内容"""
        filepath = os.path.join(self.memory_dir, filename)
        if not os.path.exists(filepath):
            return ""
        try:
            with open(filepath, 'r', encoding='utf-8') as fp:
                return fp.read()
        except (OSError, UnicodeDecodeError):
            return ""


# ============================================================
# Agent执行器
# ============================================================

class AgentRunner:
    """GenericAgent任务执行器"""

    def __init__(self, agent_dir="."):
        self.agent_dir = agent_dir
        self.agent = None
        self.agent_thread = None
        self._stop_event = threading.Event()

    def start(self):
        """启动Agent"""
        os.chdir(self.agent_dir)

        # 将当前目录加入sys.path，确保能import GenericAgent模块
        if self.agent_dir not in sys.path:
            sys.path.insert(0, os.path.abspath(self.agent_dir))

        from agentmain import GeneraticAgent

        self.agent = GeneraticAgent()
        self.agent_thread = threading.Thread(target=self._run_loop, daemon=True)
        self.agent_thread.start()

        # 等待Agent就绪
        time.sleep(2)
        print("✅ Agent已启动")

    def _run_loop(self):
        """Agent主循环（在守护线程中运行）"""
        try:
            self.agent.run()
        except Exception as e:
            if not self._stop_event.is_set():
                print(f"❌ Agent运行异常: {e}")

    def run_task(self, task_query, timeout=300):
        """
        执行单个任务
        返回: {status, response, duration, tool_calls}
        """
        if self.agent is None:
            return {"status": "error", "response": "Agent未启动", "duration": 0, "tool_calls": 0}

        display_queue = self.agent.put_task(task_query, source="auto_test")
        full_response = ""
        start_time = time.time()
        tool_call_count = 0

        while True:
            # 检查超时
            if time.time() - start_time > timeout:
                self.agent.abort()
                return {
                    "status": "timeout",
                    "response": full_response,
                    "duration": round(time.time() - start_time, 1),
                    "tool_calls": tool_call_count,
                }

            # 从队列获取输出
            try:
                item = display_queue.get(timeout=10)
            except queue.Empty:
                # 10秒内无输出，继续等待（可能是LLM在推理）
                continue

            if 'done' in item:
                full_response = item['done']
                break
            elif 'next' in item:
                chunk = item.get('next', '')
                full_response += chunk
                # 检测工具调用（GenericAgent使用XML格式）
                tool_call_count += chunk.count('<tool_use>')

        duration = round(time.time() - start_time, 1)
        return {
            "status": "success",
            "response": full_response,
            "duration": duration,
            "tool_calls": tool_call_count,
        }

    def stop(self):
        """停止Agent"""
        self._stop_event.set()
        if self.agent:
            self.agent.abort()


# ============================================================
# 核心测试器
# ============================================================

class SkillCrystallizationTester:
    """Skill结晶验证测试器"""

    def __init__(self, agent_dir="."):
        self.agent_dir = agent_dir
        self.memory_dir = os.path.join(agent_dir, MEMORY_DIR)
        self.runner = AgentRunner(agent_dir)
        self.results = []
        self.report_dir = os.path.join(agent_dir, REPORT_DIR)

    def run(self):
        """执行完整测试流程"""
        print("=" * 60)
        print("🧪 GenericAgent Skill结晶验证测试")
        print(f"   时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        print("=" * 60)

        # 1. 启动Agent
        print("\n🚀 启动Agent...")
        try:
            self.runner.start()
        except Exception as e:
            print(f"❌ Agent启动失败: {e}")
            print("   请检查：")
            print("   1. mykey.py 是否已配置有效的API Key")
            print("   2. 网络是否通畅")
            print("   3. 依赖是否已安装 (pip install requests streamlit pywebview)")
            return

        # 注册信号处理（Ctrl+C优雅退出）
        def signal_handler(sig, frame):
            print("\n\n⚠️ 收到中断信号，正在停止...")
            self.runner.stop()
            sys.exit(1)
        signal.signal(signal.SIGINT, signal_handler)

        # 2. 拍摄初始快照
        snapshot_before_all = MemorySnapshot(self.memory_dir).take()
        self._print_memory_state("初始状态", snapshot_before_all)

        # 3. 逐个执行任务
        for i, (label, task_query, timeout) in enumerate(TEST_TASKS):
            print(f"\n{'=' * 60}")
            print(f"📝 任务 {i+1}/{len(TEST_TASKS)} [{label}]")
            print(f"   {task_query}")
            print(f"   超时: {timeout}秒")
            print(f"{'=' * 60}")

            # 拍摄任务前快照
            snapshot_before = MemorySnapshot(self.memory_dir).take()

            # 执行任务
            result = self.runner.run_task(task_query, timeout=timeout)
            result["label"] = label
            result["task"] = task_query
            result["index"] = i + 1

            # 拍摄任务后快照
            snapshot_after = MemorySnapshot(self.memory_dir).take()
            diff = snapshot_after.diff(snapshot_before)

            result["new_files"] = diff["new_files"]
            result["modified_files"] = diff["modified_files"]
            result["deleted_files"] = diff["deleted_files"]
            result["l1_changed"] = diff["l1_changed"]
            result["l2_changed"] = diff["l2_changed"]

            # 判断Skill是否结晶
            sop_new = [f for f in diff["new_files"]
                       if f.endswith('.md') or f.endswith('.py')
                       and f not in self._default_sop_files()]
            result["skill_crystallized"] = len(sop_new) > 0 or (
                # 也检查现有SOP是否被修改（可能是内容更新）
                any(f.endswith(('.md', '.py')) for f in diff["modified_files"])
                and diff["l1_changed"]
            )
            result["new_sop_files"] = sop_new

            self.results.append(result)
            self._print_task_result(result, diff)

            # 任务间等待
            if i < len(TEST_TASKS) - 1:
                print(f"\n⏳ 等待{TASK_INTERVAL}秒，让记忆蒸馏完成...")
                time.sleep(TASK_INTERVAL)

        # 4. 生成总结报告
        snapshot_after_all = MemorySnapshot(self.memory_dir).take()
        total_diff = snapshot_after_all.diff(snapshot_before_all)
        self._print_summary(total_diff)
        self._save_report(total_diff)

        # 5. 停止Agent
        print("\n🛑 停止Agent...")
        self.runner.stop()
        print("✅ 测试完成！")

    def _default_sop_files(self):
        """返回GenericAgent仓库自带的默认SOP文件（不算新结晶的）"""
        return {
            "memory_management_sop.md",
            "autonomous_operation_sop.md",
            "scheduled_task_sop.md",
            "web_setup_sop.md",
            "ljqCtrl_sop.md",
            "subagent_sop.md",
        }

    def _print_memory_state(self, title, snapshot):
        """打印memory目录状态"""
        print(f"\n📁 memory目录 [{title}]:")
        if not snapshot.files:
            print("   (空)")
            return
        # 按类型分组
        sop_files = [f for f in snapshot.files if f.endswith('.md')]
        py_files = [f for f in snapshot.files if f.endswith('.py')]
        other_files = [f for f in snapshot.files if not f.endswith(('.md', '.py'))]

        if sop_files:
            print(f"   SOP文件: {', '.join(sorted(sop_files))}")
        if py_files:
            print(f"   脚本文件: {', '.join(sorted(py_files))}")
        if other_files:
            print(f"   其他文件: {', '.join(sorted(other_files))}")

    def _print_task_result(self, result, diff):
        """打印单个任务结果"""
        status_icon = {"success": "✅", "timeout": "⏰", "error": "❌"}.get(result["status"], "❓")
        crystal_icon = "✅" if result["skill_crystallized"] else "❌"

        print(f"\n📊 任务结果 [{result['label']}]:")
        print(f"   状态: {status_icon} {result['status']}")
        print(f"   耗时: {result['duration']}秒")
        print(f"   工具调用: {result['tool_calls']}次")

        if diff["new_files"]:
            print(f"   📄 新增文件: {', '.join(diff['new_files'])}")
        if diff["modified_files"]:
            print(f"   ✏️  修改文件: {', '.join(diff['modified_files'])}")
        if diff["deleted_files"]:
            print(f"   🗑️  删除文件: {', '.join(diff['deleted_files'])}")
        if diff["l1_changed"]:
            print(f"   📋 L1索引: 已更新")
        if diff["l2_changed"]:
            print(f"   📋 L2事实: 已更新")

        print(f"   🔮 Skill结晶: {crystal_icon}")

        # 如果结晶成功，展示SOP内容预览
        if result["new_sop_files"]:
            print(f"\n   📝 新Skill预览:")
            for f in result["new_sop_files"][:3]:
                filepath = os.path.join(self.memory_dir, f)
                try:
                    with open(filepath, 'r', encoding='utf-8') as fp:
                        content = fp.read()
                    preview = content[:300].replace('\n', '\n      ')
                    print(f"      --- {f} ---")
                    print(f"      {preview}")
                    if len(content) > 300:
                        print(f"      ... (共{len(content)}字符)")
                except (OSError, UnicodeDecodeError):
                    pass

    def _print_summary(self, total_diff):
        """打印总结报告"""
        print(f"\n{'=' * 60}")
        print(f"📊 Skill结晶验证报告 — 总结")
        print(f"{'=' * 60}")

        # 全局memory变化
        print(f"\n📁 全局memory变化:")
        if total_diff["new_files"]:
            print(f"   新增: {', '.join(total_diff['new_files'])}")
        if total_diff["modified_files"]:
            print(f"   修改: {', '.join(total_diff['modified_files'])}")
        if total_diff["deleted_files"]:
            print(f"   删除: {', '.join(total_diff['deleted_files'])}")
        if total_diff["l1_changed"]:
            print(f"   L1索引: ✅ 已更新")
        if total_diff["l2_changed"]:
            print(f"   L2事实: ✅ 已更新")

        # 各任务对比表
        print(f"\n📋 各任务执行对比:")
        print(f"   {'任务':<12} {'耗时':>8} {'工具调用':>8} {'结晶':>6} {'新增文件':>8}")
        print(f"   {'-' * 48}")
        for r in self.results:
            crystal = "✅" if r["skill_crystallized"] else "❌"
            new_count = len(r["new_sop_files"]) if r.get("new_sop_files") else 0
            print(f"   {r['label']:<12} {r['duration']:>7}秒 {r['tool_calls']:>8}次 {crystal:>6} {new_count:>8}个")

        # 关键对比：任务2 vs 任务4
        self._print_reuse_comparison()

        # 五行诊断
        self._print_wuxing_diagnosis(total_diff)

    def _print_reuse_comparison(self):
        """对比首次执行与复用执行"""
        if len(self.results) < 4:
            return

        t2, t4 = self.results[1], self.results[3]

        print(f"\n🔥 关键对比: 任务2[安装+执行] vs 任务4[Skill复用]")
        print(f"   {'指标':<12} {'任务2(首次)':>12} {'任务4(复用)':>12} {'变化':>12}")
        print(f"   {'-' * 52}")

        # 耗时对比
        if t2["duration"] and t4["duration"] and t4["duration"] > 0:
            speedup = round(t2["duration"] / t4["duration"], 2)
            duration_change = f"加速{speedup}x"
        else:
            duration_change = "-"
        print(f"   {'耗时':<12} {t2['duration']:>10}秒 {t4['duration']:>10}秒 {duration_change:>12}")

        # 工具调用对比
        if t2["tool_calls"] and t4["tool_calls"] and t2["tool_calls"] > 0:
            reduction = round((1 - t4["tool_calls"] / t2["tool_calls"]) * 100, 1)
            calls_change = f"减少{reduction}%"
        else:
            calls_change = "-"
        print(f"   {'工具调用':<12} {t2['tool_calls']:>10}次 {t4['tool_calls']:>10}次 {calls_change:>12}")

        # 结论
        reuse_effective = (
            (t4["duration"] < t2["duration"]) or
            (t4["tool_calls"] and t4["tool_calls"] < t2["tool_calls"])
        )
        if reuse_effective:
            print(f"\n   ✅ Skill复用验证通过！复用执行明显快于首次执行。")
            print(f"      这证明GenericAgent的Skill结晶→路由→复用机制运转正常。")
        else:
            print(f"\n   ⚠️ Skill复用效果不明显。可能原因：")
            print(f"      1. 任务2的Skill未成功结晶（检查memory/下是否有股票查询SOP）")
            print(f"      2. Skill已结晶但L1索引未更新（检查global_mem_insight.txt）")
            print(f"      3. Agent未将任务4路由到已有SOP（观察执行过程是否先file_read了SOP）")
            print(f"      4. LLM后端不稳定，导致执行轮次波动")

    def _print_wuxing_diagnosis(self, total_diff):
        """打印五行诊断"""
        print(f"\n🌀 五行诊断:")

        # 木·生：是否有新Skill生成
        new_sops = [f for f in total_diff["new_files"]
                    if f.endswith(('.md', '.py')) and f not in self._default_sop_files()]
        wood = "✅ 旺" if new_sops else "⚠️ 弱"
        print(f"   木·生（积累）: {wood}  新增Skill {len(new_sops)}个")

        # 火·化：是否有整合
        fire = "❌ 缺"  # 当前GenericAgent无整合机制
        print(f"   火·化（整合）: {fire}  无整合机制（待第一期补齐）")

        # 土·通：是否有迁移
        earth = "❌ 缺"  # 当前无迁移机制
        print(f"   土·通（迁移）: {earth}  无迁移机制（待第三期补齐）")

        # 金·克：是否有淘汰
        # L1有30行限制，超过后Agent会替换——这是天然的"金"萌芽
        metal = "⚠️ 萌" if total_diff["l1_changed"] else "❌ 缺"
        print(f"   金·克（淘汰）: {metal}  L1索引有30行限制（弱金，待强化）")

        # 水·变：是否有更新
        water = "❌ 缺"  # 当前无版本管理
        print(f"   水·变（更新）: {water}  无版本管理（待第二期补齐）")

    def _save_report(self, total_diff):
        """保存报告到文件"""
        os.makedirs(self.report_dir, exist_ok=True)
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        report_path = os.path.join(self.report_dir, f"skill_test_{timestamp}.json")

        report = {
            "timestamp": timestamp,
            "tasks": [],
            "total_diff": {
                "new_files": total_diff["new_files"],
                "modified_files": total_diff["modified_files"],
                "deleted_files": total_diff["deleted_files"],
                "l1_changed": total_diff["l1_changed"],
                "l2_changed": total_diff["l2_changed"],
            },
        }

        for r in self.results:
            report["tasks"].append({
                "index": r["index"],
                "label": r["label"],
                "task": r["task"],
                "status": r["status"],
                "duration": r["duration"],
                "tool_calls": r["tool_calls"],
                "skill_crystallized": r["skill_crystallized"],
                "new_files": r["new_files"],
                "new_sop_files": r.get("new_sop_files", []),
                "modified_files": r["modified_files"],
                "l1_changed": r["l1_changed"],
                "l2_changed": r["l2_changed"],
            })

        with open(report_path, 'w', encoding='utf-8') as fp:
            json.dump(report, fp, ensure_ascii=False, indent=2)

        print(f"\n💾 报告已保存: {report_path}")


# ============================================================
# 入口
# ============================================================

if __name__ == "__main__":
    agent_dir = sys.argv[1] if len(sys.argv) > 1 else "."
    tester = SkillCrystallizationTester(agent_dir)
    tester.run()
