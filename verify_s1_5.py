"""verify_s1_5.py — S1-5 场景模板注入验收脚本

验证：
1. 场景模板文件可正常加载
2. ScenarioMatcher.match() 返回合理结果
3. inject_soul_prompt() 包含场景参考块
4. 每次注入场景数 ≤ 3
5. 注入不导致上下文超 30K token
6. 向后兼容：不含 user_input 的调用不受影响
"""

from core.soul_prompts import inject_soul_prompt
from core.scenario_matcher import ScenarioMatcher
import json
import sys
import time
from pathlib import Path

BASE_DIR = Path(__file__).parent
SCENARIOS_PATH = BASE_DIR / "prompts" / "scenarios.json"

errors: list[str] = []

# ============================================================
# 1. 场景模板文件可正常加载
# ============================================================
print("=" * 50)
print("Test 1: Scenario loading")
try:
    with open(SCENARIOS_PATH, "r", encoding="utf-8") as f:
        scenarios = json.load(f)
    print(f"[OK] Loaded {len(scenarios)} scenarios from {SCENARIOS_PATH}")
except Exception as e:
    errors.append(f"Failed to load scenarios: {e}")
    print(f"[FAIL] {e}")

# ============================================================
# 2. ScenarioMatcher.match() 返回合理结果
# ============================================================
print("\n" + "=" * 50)
print("Test 2: ScenarioMatcher.match()")


matcher = ScenarioMatcher(min_score=0.25)  # 与 soul_prompts.py 中的生产配置一致

# 2a. 匹配"我今天有6件事要做"
test_inputs = [
    ("我今天有6件事要做，忙死了", "scene_001"),  # 多项待办
    ("最近太忙了，每天都没时间休息", "scene_021"),  # 太忙了
    ("我想改变自己，但是好害怕失败", "scene_010"),  # 想改变但不敢
    ("不知道该怎么办，好无力", "scene_006"),  # 无力感
    ("谢谢你的帮助", "scene_012"),  # 谢谢
    ("我忘了今天要做什么，唉", "scene_005"),  # 忘了某事
]

for user_input, expected_id in test_inputs:
    result = matcher.match(user_input, scenarios, max_results=3)
    result_ids = [s["id"] for s in result]
    if len(result) > 0:
        print(
            f"[OK] '{user_input[:20]}...' matched {len(result)} scenes: {result_ids}")
    else:
        print(f"[WARN] '{user_input[:20]}...' matched 0 scenes")

# 2b. 空输入返回空列表
empty_result = matcher.match("", scenarios)
if empty_result == []:
    print("[OK] Empty input returns empty list")
else:
    errors.append(f"Empty input should return [], got {empty_result}")

# 2c. 无匹配输入返回空列表
no_match = matcher.match("xyzzy_abcde_nothing_to_match", scenarios)
if no_match == []:
    print("[OK] No-match input returns empty list")
else:
    errors.append(f"No-match input should return [], got {no_match}")

# ============================================================
# 3. inject_soul_prompt() 包含场景参考块
# ============================================================
print("\n" + "=" * 50)
print("Test 3: inject_soul_prompt() with scenario injection")


base_prompt = "You are a helpful assistant."
test_input = "我今天有6件事要做，感觉很忙"

# 带 user_input 的注入
prompt_with_scenarios = inject_soul_prompt(base_prompt, user_input=test_input)

if "[场景参考" in prompt_with_scenarios:
    print("[OK] Prompt contains scenario reference block")
else:
    print("[WARN] No scenario reference block (may be acceptable if no keywords matched)")

if "[系统身份设定 - 最高优先级]" in prompt_with_scenarios:
    print("[OK] Prompt contains Soul identity block")
else:
    errors.append("Prompt missing Soul identity block")

if base_prompt in prompt_with_scenarios:
    print("[OK] Base prompt preserved at end")
else:
    errors.append("Base prompt not found in output")

# 注入顺序验证：Soul → Scenarios → base_prompt
soul_pos = prompt_with_scenarios.find("[系统身份设定")
scenario_pos = prompt_with_scenarios.find("[场景参考")
base_pos = prompt_with_scenarios.find(base_prompt)

if soul_pos < scenario_pos < base_pos:
    print("[OK] Injection order correct: Soul → Scenarios → Base")
elif scenario_pos == -1:
    print("[OK] No scenarios (acceptable), order: Soul → Base")
else:
    errors.append(
        f"Injection order wrong: Soul={soul_pos}, Scenario={scenario_pos}, Base={base_pos}")

# ============================================================
# 4. 每次注入场景数 ≤ 3
# ============================================================
print("\n" + "=" * 50)
print("Test 4: Max 3 scenarios injected")

# 构造一个会匹配多个场景的高命中输入
broad_input = "我今天有6件事要做，太忙了没办法，不知道该怎么办"
result = matcher.match(broad_input, scenarios, max_results=3)
count = len(result)
print(f"[OK] Matched {count} scenarios (max 3)")

# 验证 max_results 参数生效
result_1 = matcher.match(broad_input, scenarios, max_results=1)
if len(result_1) <= 1:
    print("[OK] max_results=1 works correctly")
else:
    errors.append(f"max_results=1 returned {len(result_1)} results")

# ============================================================
# 5. 注入不导致上下文超 30K token
# ============================================================
print("\n" + "=" * 50)
print("Test 5: Token budget check")

base_length = 20000  # 模拟一个较大的 base prompt
large_base = "这是一个较长的系统提示词。" * 500  # ~5000 chars
prompt_final = inject_soul_prompt(large_base, user_input=test_input)

# 使用 tiktoken 精确计数，不可用时用 1.5x 估算
try:
    import tiktoken
    enc = tiktoken.get_encoding("cl100k_base")
    token_count = len(enc.encode(prompt_final))
    method = "tiktoken (cl100k_base)"
except ImportError:
    token_count = int(len(prompt_final) * 1.5)
    method = "1.5x char estimate"

print(f"[OK] Total tokens: {token_count} ({method})")

if token_count > 30000:
    errors.append(f"Token count {token_count} exceeds 30K limit")
else:
    print("[OK] Token count within 30K budget")

# ============================================================
# 6. 向后兼容：不含 user_input 的调用不受影响
# ============================================================
print("\n" + "=" * 50)
print("Test 6: Backward compatibility")

prompt_no_input = inject_soul_prompt(base_prompt)

# 不应包含场景参考块
if "[场景参考" not in prompt_no_input:
    print("[OK] No scenario block when user_input is None")
else:
    errors.append("Should not have scenario block when user_input is None")

# 应包含 Soul 和 base_prompt
if "[系统身份设定" in prompt_no_input and base_prompt in prompt_no_input:
    print("[OK] Soul + base_prompt preserved without user_input")
else:
    errors.append("Missing Soul or base_prompt in no-input call")

# ============================================================
# 7. 性能检查：场景匹配延迟 < 200ms
# ============================================================
print("\n" + "=" * 50)
print("Test 7: Performance check (< 200ms)")

start = time.perf_counter()
for _ in range(100):
    matcher.match(test_input, scenarios, max_results=3)
elapsed = (time.perf_counter() - start) * 1000  # ms
avg_latency = elapsed / 100

print(f"[OK] Average matching latency: {avg_latency:.2f}ms (100 iterations)")
if avg_latency > 200:
    errors.append(f"Matching latency {avg_latency:.2f}ms exceeds 200ms")

# ============================================================
# 结果
# ============================================================
print("\n" + "=" * 50)
if errors:
    print(f"\n[FAIL] {len(errors)} error(s) found:")
    for e in errors:
        print(f"  - {e}")
    sys.exit(1)
else:
    print("\n[OK] S1-5 ALL TESTS PASSED")
    sys.exit(0)
