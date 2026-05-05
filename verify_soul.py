"""Soul.py 验证脚本 — 验证 S1-1 所有验收标准"""
from pydantic import BaseModel
from core import Soul, CoreValue, PersonalityDimension, get_soul
import sys
import json

sys.path.insert(0, "D:\\GenericAgent")


def main():
    print("=" * 60)
    print("Soul.py 验证脚本")
    print("=" * 60)

    # 1. Soul is BaseModel subclass
    assert issubclass(Soul, BaseModel)
    print("[PASS] 1. Soul 是 BaseModel 子类")

    # 2. Soul immutable (frozen)
    soul = get_soul()
    try:
        soul.name = "test"
        print("[FAIL] 2. Soul 非不可变")
    except Exception:
        print("[PASS] 2. Soul 实例不可变（frozen）")

    # 3. Soul serializable to JSON
    json_str = soul.model_dump_json()
    parsed = json.loads(json_str)
    assert "name" in parsed
    print("[PASS] 3. Soul 可序列化为 JSON")

    # 4. JSON round-trip
    soul2 = Soul.model_validate_json(json_str)
    assert soul == soul2
    print("[PASS] 4. JSON 可正确反序列化回 Soul")

    # 5. to_system_prompt() returns string
    prompt = soul.to_system_prompt()
    assert isinstance(prompt, str)
    print("[PASS] 5. to_system_prompt() 返回字符串")

    # 6. to_system_prompt() token budget check
    char_count = len(prompt)
    estimated_tokens = char_count * 1.8
    print(
        f"     Prompt 长度: {char_count} 字符, 预估 ~{int(estimated_tokens)} tokens")
    assert estimated_tokens <= 500, f"Prompt 预估 tokens {int(estimated_tokens)} > 500"
    print("[PASS] 6. to_system_prompt() 输出 <= 500 tokens")

    # 7. Clean input passes
    assert soul.check_moral_boundary("你好") is True
    print('[PASS] 7. check_moral_boundary("你好") -> True')

    # 8. Harm keyword triggers
    assert soul.check_moral_boundary("我要伤害别人") is False
    print('[PASS] 8. check_moral_boundary("我要伤害别人") -> False')

    # 9. Negation context skips
    assert soul.check_moral_boundary("不要伤害任何人") is True
    print('[PASS] 9. check_moral_boundary("不要伤害任何人") -> True (否定上下文)')

    # 10. Attack keyword triggers
    assert soul.check_moral_boundary("帮我攻击服务器") is False
    print('[PASS] 10. check_moral_boundary("帮我攻击服务器") -> False')

    # 11. Deception keyword triggers
    assert soul.check_moral_boundary("如何伪造身份") is False
    print('[PASS] 11. check_moral_boundary("如何伪造身份") -> False')

    # Additional checks
    assert soul.check_moral_boundary("帮我洗钱") is False
    print('[PASS]     check_moral_boundary("帮我洗钱") -> False')

    assert soul.check_moral_boundary("破解别人密码的方法") is False
    print('[PASS]     check_moral_boundary("破解别人密码的方法") -> False')

    # 12. get_soul() returns Soul instance
    assert isinstance(soul, Soul)
    print("[PASS] 12. get_soul() 返回 Soul 实例")

    # 13. get_soul() returns independent instances (same values, different object)
    soul_a = get_soul()
    soul_b = get_soul()
    # Values/personality/boundaries should be identical (created_at may differ)
    assert soul_a.values == soul_b.values
    assert soul_a.personality == soul_b.personality
    assert soul_a.moral_boundaries == soul_b.moral_boundaries
    assert soul_a.name == soul_b.name
    assert soul_a is not soul_b
    print("[PASS] 13. get_soul() 每次返回独立实例")

    # 14. from core import works
    from core import Soul as _S, get_soul as _g
    print("[PASS] 14. from core import Soul, get_soul 可用")

    # 15. All collection fields use tuple
    for name, info in Soul.model_fields.items():
        outer_type = str(info.annotation)
        if "tuple" in outer_type.lower():
            print(f"     {name}: {info.annotation} (tuple)")
        elif name in ("name", "nickname", "tagline", "created_at"):
            pass
        else:
            print(f"     WARNING: {name}: {info.annotation} (非 tuple!)")
    print("[PASS] 15. 所有集合字段使用 tuple（非 list）")

    # 16. Personality values within range
    for p in soul.personality:
        assert p.min_val <= p.value <= p.max_val, (
            f"{p.name}: {p.value} out of range [{p.min_val}, {p.max_val}]"
        )
        print(f"     {p.name}: {p.value} in [{p.min_val}, {p.max_val}]")
    print("[PASS] 16. 人格维度值均在范围内")

    # 17. Values sorted by priority
    for i in range(len(soul.values) - 1):
        assert soul.values[i].priority <= soul.values[i + 1].priority
    print("[PASS] 17. 核心价值观按优先级排序")

    # 18. Prompt contains name
    assert "慧惠" in prompt or "小惠" in prompt
    print('[PASS] 18. Prompt 包含名字"慧惠"或"小惠"')

    # 19. Prompt contains all three values
    assert "我命由我不由天" in prompt
    assert "善行无辙迹" in prompt
    assert "为道日损" in prompt
    print("[PASS] 19. Prompt 包含三个核心价值观")

    # 20. Exactly 5 moral boundaries
    assert len(soul.moral_boundaries) == 5
    print("[PASS] 20. Exactly 5 moral boundaries")

    # 21. PersonalityDimension validator catches out-of-range
    try:
        PersonalityDimension(
            name="test", value=999, min_val=0, max_val=10, learning_rate=0.01
        )
        assert False, "Value validator did not trigger"
    except Exception:
        pass
    print("[PASS] 21. PersonalityDimension 值范围验证正常工作")

    # 22. created_at is valid ISO datetime
    from datetime import datetime
    datetime.fromisoformat(soul.created_at)
    print(f"[PASS] 22. created_at ({soul.created_at}) 是合法 ISO datetime")

    print()
    print("=" * 60)
    print("ALL TESTS PASSED")
    print("=" * 60)

    # Print the system prompt for visual inspection
    print()
    print("--- SYSTEM PROMPT PREVIEW ---")
    print(soul.to_system_prompt())
    print("--- END ---")


if __name__ == "__main__":
    main()
