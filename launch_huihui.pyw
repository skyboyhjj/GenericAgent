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


# --- 复用 launch.pyw 的基础设施 ---
WINDOW_WIDTH, WINDOW_HEIGHT, RIGHT_PADDING, TOP_PADDING = 600, 900, 0, 100
script_dir = os.path.dirname(os.path.abspath(__file__))
frontends_dir = os.path.join(script_dir, "frontends")

FLAG_FILE = os.path.join(script_dir, "huihui_initialized.flag")


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

    # 五行流转引擎：启动时自动检查并触发审计（后台线程，不阻塞）
    _run_wuxing_audit_on_startup()

    webview.start()
