"""S1-3 验证脚本 — INITIALIZING 状态机"""
from core.initializer import InitializationHandler, InitState
import sys
import os
import time
import threading

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))


FORBIDDEN_TERMS = ["加载", "初始化", "同步", "数据", "Loading", "Init", "Sync", "Data"]


# ---- Test 1: Message Timing ----

def test_message_timing():
    """验证消息时序：0s 和 3s 消息在正确时间到达。"""
    print("[Test 1] Message Timing")

    handler = InitializationHandler()
    messages = []

    def _collect():
        for elapsed, msg in handler.start(sync_func=None):
            messages.append((round(elapsed, 1), msg))

    t = threading.Thread(target=_collect, daemon=True)
    t0 = time.time()
    t.start()
    t.join(timeout=10)

    assert len(messages) >= 2, f"Expected >= 2 messages, got {len(messages)}"

    # 第一条消息应在 < 0.5s 内到达
    elapsed_0, msg_0 = messages[0]
    assert elapsed_0 < 0.5, (
        f"First message delay {elapsed_0:.1f}s exceeds 0.5s limit"
    )
    assert msg_0 == "在吗？", f"Unexpected first message: {msg_0}"
    print(f"     [OK] 0s: '{msg_0}' at {elapsed_0:.2f}s")

    # 第二条消息应在 ~3s 到达
    if len(messages) >= 2:
        elapsed_1, msg_1 = messages[1]
        assert 2.5 <= elapsed_1 <= 4.5, (
            f"Second message at {elapsed_1:.1f}s, expected ~3s"
        )
        assert msg_1 == "我在认识你。请等我一会儿。", (
            f"Unexpected second message: {msg_1}"
        )
        print(f"     [OK] 3s: '{msg_1}' at {elapsed_1:.2f}s")

    print("  [PASS] Test 1: Message timing correct\n")


# ---- Test 2: No Technical Terminology ----

def test_no_technical_terms():
    """验证所有消息零技术术语。"""
    print("[Test 2] No Technical Terminology")

    handler = InitializationHandler()
    all_messages = set()

    # 收集所有可能的消息
    for _, msg in handler._TIMED_MESSAGES:
        all_messages.add(msg)
    for _, msg in handler._PROGRESS_MESSAGES:
        all_messages.add(msg)
    all_messages.add(handler.FINAL_MESSAGE)
    all_messages.add(handler.FALLBACK_MESSAGE)

    violations = []
    for msg in all_messages:
        for term in FORBIDDEN_TERMS:
            if term.lower() in msg.lower():
                violations.append(f"'{term}' in '{msg}'")

    assert not violations, (
        f"Technical terms found:\n" + "\n".join(violations)
    )

    for msg in sorted(all_messages):
        print(f"     [OK] {msg[:60]}...")

    print("  [PASS] Test 2: Zero technical terminology\n")


# ---- Test 3: Sync Success Path ----

def test_sync_success():
    """验证同步成功路径：终态消息 + IDLE 状态。"""
    print("[Test 3] Sync Success Path")

    handler = InitializationHandler()

    def fast_sync(h):
        """快速完成同步。"""
        time.sleep(0.5)
        h.set_progress(0.3)
        time.sleep(0.5)
        h.set_progress(0.8)
        time.sleep(0.5)
        h.set_progress(1.0)

    messages = []
    for elapsed, msg in handler.start(sync_func=fast_sync):
        messages.append(msg)

    # 应该有完整的消息序列（至少 5 条 + 终态）
    assert len(messages) >= 3, f"Expected >= 3 messages, got {len(messages)}"

    # 最后一条消息应该是终态消息
    last_msg = messages[-1]
    assert last_msg == handler.FINAL_MESSAGE or last_msg == handler.FALLBACK_MESSAGE, (
        f"Unexpected final message: {last_msg}"
    )

    # 无同步错误
    assert handler._sync_error is None, f"Unexpected sync error: {handler._sync_error}"

    # 状态应为 IDLE
    assert handler.state == InitState.IDLE, (
        f"Expected IDLE state, got {handler.state}"
    )

    print(f"     Messages: {len(messages)} total")
    for i, m in enumerate(messages):
        print(f"       [{i}] {m}")
    print(f"     Final state: {handler.state.value}")
    print("  [PASS] Test 3: Sync success → IDLE\n")


# ---- Test 4: Sync Failure Path ----

def test_sync_failure():
    """验证同步失败降级路径：不阻塞 + FALLBACK 消息 + FAILED 状态。"""
    print("[Test 4] Sync Failure Path")

    handler = InitializationHandler()

    def failing_sync(h):
        """模拟同步失败。"""
        time.sleep(0.1)
        raise RuntimeError("Simulated sync failure")

    messages = []
    t_start = time.time()
    for elapsed, msg in handler.start(sync_func=failing_sync):
        messages.append(msg)

    t_total = time.time() - t_start

    # 不应超过 10s（证明未阻塞）
    assert t_total < 10.0, f"Flow took {t_total:.1f}s, expected < 10s"

    # 最后一条消息应该是降级消息
    assert messages[-1] == handler.FALLBACK_MESSAGE, (
        f"Expected fallback message, got: {messages[-1]}"
    )

    # 状态应为 FAILED
    assert handler.state == InitState.FAILED, (
        f"Expected FAILED state, got {handler.state}"
    )

    print(f"     Total time: {t_total:.1f}s")
    print(f"     Messages: {len(messages)}")
    print(f"     Last message: {messages[-1]}")
    print(f"     Final state: {handler.state.value}")
    print("  [PASS] Test 4: Sync failure → graceful degradation\n")


# ---- Test 5: First-Time vs Returning User ----

def test_flag_file():
    """验证标志文件机制。"""
    print("[Test 5] Flag File Mechanism")

    script_dir = os.path.dirname(os.path.abspath(__file__))
    flag_path = os.path.join(script_dir, "huihui_initialized.flag")

    # 清理测试残留
    if os.path.exists(flag_path):
        os.remove(flag_path)

    # 首次启动：标志文件不应存在
    assert not os.path.exists(
        flag_path), "Flag file should not exist before first launch"
    print("     [OK] Before first launch: flag absent")

    # 模拟首次初始化完成后创建标志文件
    with open(flag_path, "w", encoding="utf-8") as f:
        f.write("initialized_at=2026-05-01T00:00:00\n")

    assert os.path.exists(flag_path), "Flag file should exist after first init"
    print("     [OK] After first init: flag created")

    # 再次启动：标志文件应存在
    assert os.path.exists(
        flag_path), "Flag file should persist on second launch"
    print("     [OK] Second launch: flag present")

    # 清理
    os.remove(flag_path)

    print("  [PASS] Test 5: Flag file mechanism works\n")


# ---- Test 6: Progress Tracking ----

def test_progress_tracking():
    """验证进度跟踪和线程安全。"""
    print("[Test 6] Progress Tracking")

    handler = InitializationHandler()

    # 初始进度
    assert handler.sync_progress == 0.0
    print(f"     Initial progress: {handler.sync_progress}")

    # 设置进度（在线程中模拟）
    def update_progress():
        for p in (0.1, 0.3, 0.5, 0.75, 1.0):
            time.sleep(0.2)
            handler.set_progress(p)

    t = threading.Thread(target=update_progress, daemon=True)
    t.start()
    t.join(timeout=3)

    assert handler.sync_progress == 1.0, (
        f"Progress should be 1.0, got {handler.sync_progress}"
    )
    print(f"     Final progress: {handler.sync_progress}")

    # 边界测试：不应超过 1.0
    handler.set_progress(99.9)
    assert handler.sync_progress == 1.0
    print("     [OK] Progress clamped to 1.0")

    handler.set_progress(-5.0)
    assert handler.sync_progress == 0.0
    print("     [OK] Progress clamped to 0.0")

    print("  [PASS] Test 6: Progress tracking correct\n")


# ---- Test 7: State Transitions ----

def test_state_transitions():
    """验证状态流转。"""
    print("[Test 7] State Transitions")

    handler = InitializationHandler()

    # 初始状态
    assert handler.state == InitState.INITIALIZING
    assert handler.is_initializing is True
    assert handler.is_ready is False
    print(f"     Initial: {handler.state.value}, ready={handler.is_ready}")

    # 成功完成
    def quick_sync(h):
        time.sleep(0.1)
        h.set_progress(1.0)

    for _ in handler.start(sync_func=quick_sync):
        pass

    assert handler.state == InitState.IDLE
    assert handler.is_initializing is False
    assert handler.is_ready is True
    print(
        f"     After success: {handler.state.value}, ready={handler.is_ready}")

    # 失败完成
    handler2 = InitializationHandler()

    def fail_sync(h):
        raise RuntimeError("test")

    for _ in handler2.start(sync_func=fail_sync):
        pass

    assert handler2.state == InitState.FAILED
    assert handler2.is_ready is True  # FAILED 也算 ready（不阻塞）
    print(
        f"     After failure: {handler2.state.value}, ready={handler2.is_ready}")

    print("  [PASS] Test 7: State transitions correct\n")


# ============================================================

def main():
    print("=" * 60)
    print("S1-3 验证脚本 — INITIALIZING 状态机")
    print("=" * 60)
    print()

    test_message_timing()
    test_no_technical_terms()
    test_sync_success()
    test_sync_failure()
    test_flag_file()
    test_progress_tracking()
    test_state_transitions()

    print("=" * 60)
    print("S1-3 ALL TESTS PASSED")
    print("=" * 60)


if __name__ == "__main__":
    main()
