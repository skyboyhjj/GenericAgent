"""
慧惠（Huihui）启动入口

与 launch.pyw 同级，提供慧惠专属的初见仪式体验。
首次启动 → INITIALIZING 状态机 → 初见消息序列
再次启动 → 直接进入常规 AgentLoop
"""

import webview
import threading
import subprocess
import sys
import time
import os
import atexit
import socket
import random

# --- 五行流转引擎（S3-5 集成） ---


def _init_wuxing_engine():
    """初始化五行流转引擎，返回 (registry, root_auditor) 元组。
    初始化失败时静默降级，不影响慧惠正常启动。"""
    try:
        from skills.skill_registry import SkillRegistry
        from skills.wood_grower import WoodGrower
        from skills.metal_restrainer import MetalRestrainer
        from skills.water_adapter import WaterAdapter
        from skills.earth_connector import EarthConnector
        from skills.root_auditor import RootAuditor

        registry = SkillRegistry()
        wood_grower = WoodGrower(registry)
        metal_restrainer = MetalRestrainer(registry)
        water_adapter = WaterAdapter(registry)
        earth_connector = EarthConnector(registry)
        root_auditor = RootAuditor(
            registry=registry,
            wood_grower=wood_grower,
            metal_restrainer=metal_restrainer,
            water_adapter=water_adapter,
            earth_connector=earth_connector,
        )
        print("[Wuxing] Five-element engine initialized.")
        return registry, root_auditor
    except Exception as e:
        print(f"[Wuxing] Engine init skipped: {e}")
        return None, None


def _check_and_audit(root_auditor):
    """在后台检查审计周期并触发审计。"""
    if root_auditor is None:
        return
    try:
        # 每日审计：超过 24 小时未审计则触发
        if root_auditor.is_audit_due("daily"):
            print("[Wuxing] Audit due. Starting daily audit in background...")
            root_auditor.audit_async("daily")
        else:
            last = root_auditor.get_last_audit_time()
            print(f"[Wuxing] Audit not due yet. Last audit: {last}")
    except Exception as e:
        print(f"[Wuxing] Audit check failed: {e}")


def _run_wuxing_audit_on_startup():
    """启动时异步执行五行审计检查。"""
    registry, root_auditor = _init_wuxing_engine()
    if root_auditor:
        # 延迟 3 秒让 Streamlit 先就绪，再异步执行审计
        def _delayed_audit():
            time.sleep(3)
            _check_and_audit(root_auditor)
        threading.Thread(target=_delayed_audit, daemon=True,
                         name="wuxing-startup").start()
    return registry, root_auditor


# --- 袭明数据同步（XIMING-INTEGRATE-01） ---


def _read_last_sync() -> int | None:
    """读取上次同步的秒级 Unix 时间戳。文件不存在返回 None（触发全量同步）。"""
    try:
        with open(LAST_SYNC_FILE, "r") as f:
            return int(f.read().strip())
    except (FileNotFoundError, ValueError):
        return None


def _write_last_sync(ts: float) -> None:
    """写入当前时间的秒级 Unix 时间戳。"""
    os.makedirs(os.path.dirname(LAST_SYNC_FILE), exist_ok=True)
    with open(LAST_SYNC_FILE, "w") as f:
        f.write(str(int(ts)))


def _run_ximing_sync():
    """后台执行袭明数据同步完整流程。

    流程：启动服务 → 同步判断 → 拉取数据 → 三级目录 → 差分 → 蒸馏 → 记忆写入。
    所有异常静默降级，不阻塞慧惠正常启动。
    """
    print("[XiMing] Starting sync flow...")
    sync_ok = False

    try:
        # 1. 启动数据服务
        from memory.ximing_server_manager import XiMingServerManager
        from memory.ximing_directory_manager import XiMingDirectoryManager
        from memory.ximing_diff_engine import XiMingDiffEngine
        from memory.ximing_pipeline import XiMingPipeline
        from memory.memory_core import MemoryCore
        from memory.gateway.adapters.ximing_adapter import XiMingAdapter

        mgr = XiMingServerManager()
        if not mgr.start():
            print("[XiMing] Server failed to start — skipping sync")
            return

        dir_mgr = XiMingDirectoryManager()
        adapter = XiMingAdapter()
        pipeline = XiMingPipeline()
        mem = MemoryCore()
        diff_engine = XiMingDiffEngine()

        # 2. 同步判断
        last_ts = _read_last_sync()
        now_ts = time.time()
        is_first_sync = last_ts is None
        is_due = is_first_sync or (now_ts - (last_ts or 0)) > 86400

        if not is_due:
            print(f"[XiMing] Sync not due (last: {last_ts}, "
                  f"elapsed: {int(now_ts - (last_ts or 0))}s)")
            return

        # 3. 同步今日数据（总是先同步 Today）
        print("[XiMing] Syncing today...")
        result_today = adapter.sync_today()
        if not result_today.success:
            print(f"[XiMing] Today sync failed: {result_today.error_message}")
            return
        daily_data = result_today.data[0] if result_today.data else None
        if daily_data is None:
            print("[XiMing] Today sync returned empty data")
            return

        # 3a. 保存快照到 incoming/
        today_snapshot = {
            "synced_at": int(now_ts),
            "sync_type": "today",
            "data": daily_data.model_dump(),
        }
        incoming_file = dir_mgr.move_to_incoming(today_snapshot)

        # 3b. 检查 comments.resync_needed → 追加 History 同步
        need_history = is_first_sync
        try:
            conn = adapter.check_connectivity()
            if conn.reachable:
                import urllib.request
                import json
                req = urllib.request.Request(
                    "http://127.0.0.1:9876/api/v1/today",
                    method="GET",
                )
                req.add_header("Accept", "application/json")
                with urllib.request.urlopen(req, timeout=3) as resp:
                    raw = json.loads(resp.read().decode("utf-8"))
                    comments = raw.get("comments", {})
                    if comments.get("resync_needed"):
                        need_history = True
                        print(f"[XiMing] resync requested: "
                              f"{comments.get('resync_reason', '')}")
        except Exception:
            pass

        history_data = []
        if need_history:
            print("[XiMing] Syncing history...")
            result_hist = adapter.sync_history()
            if result_hist.success:
                history_data = result_hist.data
                hist_snapshot = {
                    "synced_at": int(now_ts),
                    "sync_type": "history",
                    "data": [d.model_dump() for d in history_data],
                }
                dir_mgr.move_to_incoming(hist_snapshot)

        # 4. 三级目录流转：incoming → processing
        dir_mgr.move_to_processing(incoming_file)

        # 5. 差分识别
        previous_events = []
        current_events = daily_data.model_dump().get("events", [])
        diff_result = diff_engine.diff(previous_events, current_events)
        if diff_result.has_changes:
            print(f"[XiMing] Diff: {diff_result.summary}")

        # 6. 蒸馏管道
        # 首次同步：处理全量历史
        if is_first_sync and history_data:
            print("[XiMing] Processing history through pipeline...")
            l2_metrics = pipeline.process_history(history_data)
        else:
            # 增量：先加载已有历史（从 l4_archive 恢复），再处理今日
            pass  # pipeline._history_events 在首次 process_history 后已有数据

        # 处理今日数据
        insight = pipeline.process_daily(daily_data)
        l2_metrics = pipeline.get_metrics()

        # 7. 写入记忆
        mem.update_from_daily(insight)
        mem.update_from_metrics(l2_metrics)
        mem.save_to_disk()
        print(f"[XiMing] Memory updated: L1={mem.l1_count}, L2={mem.l2_count}")

        # 8. 三级目录流转：processing → processed
        dir_mgr.move_to_processed(incoming_file + ".lock")

        # 9. 更新同步时间戳
        _write_last_sync(now_ts)

        # 10. 生成每日镜鉴问候
        _generate_and_cache_greeting(mem)

        sync_ok = True

    except Exception as exc:
        print(f"[XiMing] Sync failed (silent degrade): {exc}")
    finally:
        if sync_ok:
            print("[XiMing] Sync complete.")
        else:
            print("[XiMing] Sync skipped or failed — conversation unaffected.")


# --- 每日镜鉴问候缓存（XIMING-GREETING-01） ---

def _json_dt_utcnow():
    """返回 UTC 当前 datetime（供 JSON 序列化使用）。"""
    from datetime import datetime as _dt, timezone as _tz
    return _dt.now(_tz.utc)


def _save_greeting(result: "GreetingResult") -> None:
    """将生成的问候缓存到本地 JSON 文件。"""
    try:
        import json as _json
        payload = {
            "date": _json_dt_utcnow().strftime("%Y-%m-%d"),
            "text": result.text,
            "pattern": result.pattern,
            "reason": result.reason,
            "generated_at": time.time(),
            "displayed": False,
        }
        os.makedirs(os.path.dirname(GREETING_CACHE_FILE), exist_ok=True)
        with open(GREETING_CACHE_FILE, "w", encoding="utf-8") as f:
            _json.dump(payload, f, ensure_ascii=False, indent=2)
        print(
            f"[Greeting] Cached: pattern={result.pattern}, text='{result.text}'")
    except Exception as exc:
        print(f"[Greeting] Cache write failed: {exc}")


def _load_cached_greeting() -> dict | None:
    """读取缓存的问候数据。文件不存在或损坏返回 None。"""
    try:
        import json as _json
        with open(GREETING_CACHE_FILE, "r", encoding="utf-8") as f:
            return _json.load(f)
    except (FileNotFoundError, Exception):
        return None


def _should_show_greeting(cached: dict) -> bool:
    """判断是否应该展示缓存的问候：今日未展示 + 晨间窗口。"""
    from memory.greeting_engine import is_morning_window
    if not cached:
        return False
    if cached.get("displayed", False):
        return False
    today = _json_dt_utcnow().strftime("%Y-%m-%d")
    if cached.get("date") != today:
        return False
    if not is_morning_window():
        return False
    return True


def _mark_greeting_displayed() -> None:
    """标记缓存的问候为已展示。"""
    try:
        cached = _load_cached_greeting()
        if cached:
            cached["displayed"] = True
            os.makedirs(os.path.dirname(GREETING_CACHE_FILE), exist_ok=True)
            import json as _json
            with open(GREETING_CACHE_FILE, "w", encoding="utf-8") as f:
                _json.dump(cached, f, ensure_ascii=False, indent=2)
    except Exception as exc:
        print(f"[Greeting] Mark displayed failed: {exc}")


def _generate_and_cache_greeting(memory_core):
    """生成每日镜鉴问候并缓存。失败静默降级。"""
    try:
        from memory.greeting_engine import GreetingEngine
        engine = GreetingEngine(memory_core)
        result = engine.generate_greeting()
        _save_greeting(result)
    except Exception as exc:
        print(f"[Greeting] Generation failed (silent degrade): {exc}")


# --- 复用 launch.pyw 的基础设施 ---
WINDOW_WIDTH, WINDOW_HEIGHT, RIGHT_PADDING, TOP_PADDING = 600, 900, 0, 100
script_dir = os.path.dirname(os.path.abspath(__file__))
frontends_dir = os.path.join(script_dir, "frontends")

FLAG_FILE = os.path.join(script_dir, "huihui_initialized.flag")
GREETING_CACHE_FILE = os.path.join(script_dir, "memory", "last_greeting.json")
LAST_SYNC_FILE = os.path.join(script_dir, "memory", "last_sync.txt")


def find_free_port(lo=18501, hi=18599):
    ports = list(range(lo, hi + 1))
    random.shuffle(ports)
    for p in ports:
        try:
            s = socket.socket()
            s.bind(("127.0.0.1", p))
            s.close()
            return p
        except OSError:
            continue
    raise RuntimeError(f"No free port in {lo}-{hi}")


def start_streamlit(port):
    global proc
    cmd = [
        sys.executable, "-m", "streamlit", "run",
        os.path.join(frontends_dir, "stapp.py"),
        "--server.port", str(port),
        "--server.address", "localhost",
        "--server.headless", "true",
    ]
    proc = subprocess.Popen(cmd)
    atexit.register(proc.kill)


# ---- 初见仪式：消息注入 ----

_INIT_INJECT_JS = r"""
(function() {
    // 在 Streamlit 聊天容器中插入慧惠的初始化消息
    const container = document.querySelector('[data-testid="stChatMessageContainer"]');
    if (!container) return false;

    const msg = document.createElement('div');
    msg.setAttribute('data-testid', 'stChatMessage');
    msg.className = 'stChatMessage st-emotion-cache-1c7y2kd e1f1d6gn4';
    msg.innerHTML = `<div class="stChatMessage st-emotion-cache-4z0i4m e1f1d6gn4">
        <div class="stChatMessage st-emotion-cache-1c7y2kd">MSG_PLACEHOLDER</div>
    </div>`;

    container.appendChild(msg);
    container.scrollTop = container.scrollHeight;
    return true;
})();
"""


def show_init_message(window, message_text):
    """向 Streamlit 聊天界面注入一条来自慧惠的消息。"""
    # 转义消息中的特殊字符
    safe_msg = message_text.replace("\\", "\\\\").replace(
        "`", "\\`").replace("$", "\\$")
    js_code = _INIT_INJECT_JS.replace("MSG_PLACEHOLDER", safe_msg)
    try:
        window.evaluate_js(js_code)
        return True
    except Exception as e:
        print(f"[Init] Failed to show message: {e}")
        return False


def run_initialization(window):
    """执行初见仪式，逐条显示初始化消息。"""
    from core.initializer import InitializationHandler

    handler = InitializationHandler()

    def _dummy_sync(h):
        """模拟后台同步（逐步推进进度）。"""
        import time as _time
        for p in (0.05, 0.12, 0.22, 0.35, 0.50, 0.65, 0.78, 0.88, 0.95, 1.0):
            _time.sleep(5.0)
            h.set_progress(p)

    print("[Huihui] Starting first encounter...")
    start_time = time.time()

    for elapsed, message in handler.start(sync_func=_dummy_sync):
        actual = time.time() - start_time
        print(f"[Huihui] {actual:.1f}s → {message}")
        show_init_message(window, message)

    # 创建标志文件，标记初始化完成
    with open(FLAG_FILE, "w", encoding="utf-8") as f:
        f.write(f"initialized_at={time.strftime('%Y-%m-%dT%H:%M:%S')}\n")

    print(f"[Huihui] Initialization complete. State: {handler.state.value}")


def is_first_launch():
    """检查是否为首次启动。"""
    return not os.path.exists(FLAG_FILE)


# ---- 主入口 ----

if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser()
    parser.add_argument("port", nargs="?", default="0")
    parser.add_argument("--tg", action="store_true")
    parser.add_argument("--qq", action="store_true")
    parser.add_argument("--feishu", "--fs", dest="feishu", action="store_true")
    parser.add_argument("--wecom", action="store_true")
    parser.add_argument("--dingtalk", "--dt",
                        dest="dingtalk", action="store_true")
    parser.add_argument("--sched", action="store_true")
    parser.add_argument("--llm_no", type=int, default=0)
    args = parser.parse_args()

    port = str(find_free_port()) if args.port == "0" else args.port
    print(f"[Huihui] Using port {port}")

    # 启动 Streamlit 服务器
    threading.Thread(target=start_streamlit, args=(port,), daemon=True).start()

    # 创建 webview 窗口
    if os.name == "nt":
        try:
            import ctypes
            screen_width = ctypes.windll.user32.GetSystemMetrics(0)
        except Exception:
            screen_width = 1920
        x_pos = screen_width - WINDOW_WIDTH - RIGHT_PADDING
    else:
        x_pos = 100

    time.sleep(2)  # 等 Streamlit 就绪

    window = webview.create_window(
        title="慧惠",
        url=f"http://localhost:{port}",
        width=WINDOW_WIDTH,
        height=WINDOW_HEIGHT,
        x=x_pos,
        y=TOP_PADDING,
        resizable=True,
        text_select=True,
    )

    # 初见仪式 or 直接进入
    if is_first_launch():
        # 在 webview 启动后、用户交互前，执行初始化
        def _do_init():
            time.sleep(1.5)  # 等待页面完全加载
            run_initialization(window)

        threading.Thread(target=_do_init, daemon=True).start()
    else:
        print("[Huihui] Welcome back. Skipping initialization.")
        # 晨间问候注入：非首次启动时检查并注入缓存问候

        def _show_morning_greeting():
            time.sleep(2.0)  # 等待页面加载
            # 短轮询：等待问候缓存生成（最多等 8 秒）
            for _ in range(8):
                cached = _load_cached_greeting()
                if cached and not cached.get("displayed", False):
                    break
                time.sleep(1.0)
            cached = _load_cached_greeting()
            if _should_show_greeting(cached):
                show_init_message(window, cached["text"])
                _mark_greeting_displayed()
                print(f"[Greeting] Injected: {cached['text']}")
        threading.Thread(target=_show_morning_greeting, daemon=True).start()

    # 五行流转引擎：启动时自动检查并触发审计（后台线程，不阻塞）
    _run_wuxing_audit_on_startup()

    # 袭明数据同步：后台线程执行完整同步流程（不阻塞 UI）
    threading.Thread(
        target=_run_ximing_sync, daemon=True, name="ximing-sync",
    ).start()

    webview.start()
