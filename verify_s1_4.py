"""verify_s1_4.py — S1-4 场景模板验收脚本

验证：
1. prompts/scenarios.json 文件存在且 JSON 合法
2. 场景总数 >= 20
3. 5 个必含场景全部包含
4. 每个场景的 value 字段匹配 Soul.py 中三个价值观之一
5. 每个 id 唯一
"""

import json
import sys
from pathlib import Path

BASE_DIR = Path(__file__).parent
SCENARIOS_PATH = BASE_DIR / "prompts" / "scenarios.json"

VALID_VALUES = {"我命由我不由天", "善行无辙迹", "为道日损"}
MANDATORY_IDS = {"scene_001", "scene_002",
                 "scene_003", "scene_004", "scene_005"}

MANDATORY_DETAIL = {
    "scene_001": ("用户列出多项待办", "我命由我不由天"),
    "scene_002": ("用户长期未说话后回来", "为道日损"),
    "scene_003": ("深夜用户打开对话", "善行无辙迹"),
    "scene_004": ("完成一项耗时任务", "善行无辙迹"),
    "scene_005": ("用户忘了某件事", "为道日损"),
}

REQUIRED_FIELDS = {"id", "trigger", "intent_keywords",
                   "response_example", "response_style", "value"}

errors: list[str] = []

# 1. 文件存在且可解析
if not SCENARIOS_PATH.exists():
    print(f"[FAIL] 文件不存在: {SCENARIOS_PATH}")
    sys.exit(1)

try:
    with open(SCENARIOS_PATH, "r", encoding="utf-8") as f:
        scenarios = json.load(f)
except json.JSONDecodeError as e:
    print(f"[FAIL] JSON 格式不合法: {e}")
    sys.exit(1)

print(f"[OK] JSON 解析成功，共 {len(scenarios)} 个场景")

# 2. 场景总数 >= 20
if len(scenarios) < 20:
    errors.append(f"场景总数不足: {len(scenarios)} < 20")

# 3. 检查必含场景
present_ids = {s["id"] for s in scenarios}
missing_mandatory = MANDATORY_IDS - present_ids
if missing_mandatory:
    errors.append(f"缺少必含场景: {missing_mandatory}")
else:
    # 验证必含场景的内容正确性
    for sid in MANDATORY_IDS:
        scene = next(s for s in scenarios if s["id"] == sid)
        expected_trigger, expected_value = MANDATORY_DETAIL[sid]
        if scene["value"] != expected_value:
            errors.append(
                f"{sid} 价值观不匹配: 期望 '{expected_value}', 实际 '{scene['value']}'")

# 4. 每个场景 id 唯一
ids = [s["id"] for s in scenarios]
if len(ids) != len(set(ids)):
    from collections import Counter
    dupes = [id_ for id_, count in Counter(ids).items() if count > 1]
    errors.append(f"存在重复 id: {dupes}")

# 5. 每个场景的 value 匹配三个价值观
for scene in scenarios:
    sid = scene["id"]
    # 必填字段
    missing_fields = REQUIRED_FIELDS - set(scene.keys())
    if missing_fields:
        errors.append(f"{sid} 缺少必填字段: {missing_fields}")
        continue

    # value 合法性
    if scene["value"] not in VALID_VALUES:
        errors.append(f"{sid} 的 value '{scene['value']}' 不匹配已知价值观")

    # intent_keywords 非空
    if not scene["intent_keywords"]:
        errors.append(f"{sid} 的 intent_keywords 为空")

    # response_example 非空
    if not scene["response_example"].strip():
        errors.append(f"{sid} 的 response_example 为空")

# 6. 三大价值观覆盖统计
value_counts = {}
for scene in scenarios:
    v = scene["value"]
    value_counts[v] = value_counts.get(v, 0) + 1

print(f"[OK] 价值观分布: {value_counts}")

for v in VALID_VALUES:
    count = value_counts.get(v, 0)
    if count < 3:
        errors.append(f"价值观 '{v}' 场景数不足: {count} < 3")

# 7. tone 字段检查（可选但推荐）
no_tone = [s["id"] for s in scenarios if not s.get("tone")]
if no_tone:
    print(f"[WARN] 以下场景缺少 tone 字段: {no_tone}")

# 结果输出
if errors:
    print(f"\n[FAIL] 发现 {len(errors)} 个问题:")
    for e in errors:
        print(f"  - {e}")
    sys.exit(1)
else:
    print(
        f"\n[OK] S1-4 ALL TESTS PASSED ({len(scenarios)} scenarios, {len(VALID_VALUES)} values covered)")
    sys.exit(0)
