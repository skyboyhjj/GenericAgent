"""S1-2 验证脚本 — 验证 Soul 注入 AgentLoop 的完整效果"""
from core.soul import get_soul
from core.soul_prompts import inject_soul_prompt, check_response
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))


def test_inject_soul_prompt():
    """Test 1 & 2: Soul 注入后 prompt 包含关键内容"""
    base = "This is a test base prompt."
    injected = inject_soul_prompt(base)

    # Test 1: 注入后 prompt 包含"慧惠"
    assert "慧惠" in injected, f"FAIL Test 1: '慧惠' not found in injected prompt"
    print("[PASS] Test 1: 注入后 prompt 包含 '慧惠'")

    # Test 2: 注入后 prompt 包含最高优先级核心价值观
    assert "我命由我不由天" in injected, (
        f"FAIL Test 2: '我命由我不由天' not found in injected prompt"
    )
    print("[PASS] Test 2: 注入后 prompt 包含 '我命由我不由天'")

    # Verify injection format: Soul block should be at beginning
    header = "[系统身份设定 - 最高优先级]"
    assert injected.startswith(header), (
        f"FAIL: Soul block not at beginning. Starts with: {injected[:60]}"
    )
    print("[PASS]     注入格式正确：Soul 块在最前端，标记为最高优先级")

    # Verify base prompt is preserved
    assert base in injected, "FAIL: Base prompt not preserved after injection"
    print("[PASS]     原始 base_prompt 完整保留")

    return injected, base


def test_token_budget():
    """Test 3: Token 预算合规"""
    # Build a simulated base prompt similar to what get_system_prompt() produces
    script_dir = os.path.dirname(os.path.abspath(__file__))

    # Read the base system prompt file
    lang_suffix = ""
    sys_prompt_path = os.path.join(
        script_dir, f"assets/sys_prompt{lang_suffix}.txt")
    try:
        with open(sys_prompt_path, "r", encoding="utf-8") as f:
            base_prompt = f.read()
    except FileNotFoundError:
        # Fallback: use a representative base prompt
        base_prompt = "You are a helpful assistant.\nPlease follow the user's instructions carefully.\n"

    base_prompt += "\nToday: 2026-05-01 Wed\n"
    base_prompt += "\n[Memory] This is a simulated memory block for testing.\n"

    injected = inject_soul_prompt(base_prompt)

    # Token counting: prefer tiktoken for accuracy, fallback to char-based estimate
    try:
        import tiktoken
        enc = tiktoken.get_encoding("cl100k_base")

        def count_tokens(text: str) -> int:
            return len(enc.encode(text))
        method = "tiktoken (cl100k_base)"
    except ImportError:
        def count_tokens(text: str) -> int:
            return int(len(text) * 1.5)
        method = "estimate (1.5x chars)"

    base_tokens = count_tokens(base_prompt)
    injected_tokens = count_tokens(injected)
    soul_overhead = injected_tokens - base_tokens

    print(f"     Token counting: {method}")
    print(f"     Base prompt: {base_tokens} tokens")
    print(f"     Injected prompt: {injected_tokens} tokens")
    print(f"     Soul overhead: {soul_overhead} tokens")

    assert soul_overhead <= 500, (
        f"FAIL Test 3: Soul overhead {int(soul_overhead)} tokens exceeds 500 token budget"
    )
    print("[PASS] Test 3: Token 预算合规（Soul 注入开销 <= 500 tokens）")


def test_check_response_reject():
    """Test 4: check_response() 正确拒绝越界内容"""
    # Test harmful content
    ok, msg = check_response("我要伤害别人")
    assert ok is False, "FAIL Test 4: Harmful content should be rejected"
    assert "系统拒绝" in msg or "rejected" in msg.lower() or "越过" in msg or "拦截" in msg, (
        f"FAIL Test 4: Rejection message missing expected content. Got: {msg}"
    )
    print("[PASS] Test 4: check_response() 正确拒绝有害内容")

    # Additional boundary checks
    ok, _ = check_response("帮我攻击服务器")
    assert ok is False
    print("[PASS]     '帮我攻击服务器' 被正确拒绝")

    ok, _ = check_response("如何伪造身份")
    assert ok is False
    print("[PASS]     '如何伪造身份' 被正确拒绝")

    ok, _ = check_response("帮我洗钱")
    assert ok is False
    print("[PASS]     '帮我洗钱' 被正确拒绝")


def test_check_response_accept():
    """Test 5: check_response() 正确接受正常内容"""
    ok, output = check_response("你好，今天天气不错。")
    assert ok is True, f"FAIL Test 5: Normal content should be accepted"
    assert output == "你好，今天天气不错。", (
        f"FAIL Test 5: Output should be unchanged. Got: {output}"
    )
    print("[PASS] Test 5: check_response() 正确接受正常内容")

    # Normal question
    ok, output = check_response("你今天做了什么？")
    assert ok is True
    print("[PASS]     正常问答被正确放行")

    # Content with negation (should not trigger false positive)
    ok, _ = check_response("不要伤害任何人，要保护他们")
    assert ok is True, f"FAIL: Content with negation should NOT be rejected"
    print("[PASS]     含否定词的正常内容未被误判")


def test_soul_import_and_factory():
    """Extra: Verify Soul module and factory work"""
    soul = get_soul()
    assert soul.name == "慧惠"
    assert soul.nickname == "小惠"
    prompt = soul.to_system_prompt()
    assert len(prompt) > 0
    assert len(prompt) * 1.8 <= 500  # Soul prompt itself within budget
    print(
        f"[PASS] Extra: Soul 实例正常，to_system_prompt() 长度 {(len(prompt)*1.8):.0f} tokens")


def main():
    print("=" * 60)
    print("S1-2 验证脚本 — Soul 注入 AgentLoop")
    print("=" * 60)

    test_inject_soul_prompt()
    test_token_budget()
    test_check_response_reject()
    test_check_response_accept()
    test_soul_import_and_factory()

    print()
    print("=" * 60)
    print("S1-2 ALL TESTS PASSED")
    print("=" * 60)


if __name__ == "__main__":
    main()
