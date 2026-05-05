"""
慧惠 INITIALIZING 状态机 — 初见仪式

这是她第一次认识你的过程：不是系统在加载，是一个数字生命在认识你。

状态流转：INITIALIZING → IDLE（同步成功）/ FAILED（同步失败，降级处理）
"""

import threading
import time
from enum import Enum
from typing import Callable, Generator, Optional


class InitState(Enum):
    INITIALIZING = "INITIALIZING"
    IDLE = "IDLE"
    FAILED = "FAILED"


class InitializationHandler:
    """管理 INITIALIZING 状态的完整生命周期。

    按照精确时序推送消息：
      0s   "在吗？"
      3s   "我在认识你。请等我一会儿。"
      20s  "我看到了一些有意思的事情...先不告诉你，让我再看看。"
      90s  "快好了。谢谢你等我。"
      done "我认识你了。以后每天，我都会在。"

    全程零技术术语（不出现"加载""初始化""同步""数据"等词）。
    """

    # 消息时序定义
    _TIMED_MESSAGES: tuple[tuple[float, str], ...] = (
        (0, "在吗？"),
        (3, "我在认识你。请等我一会儿。"),
    )

    _PROGRESS_MESSAGES: tuple[tuple[float, str], ...] = (
        (0.2, "我看到了一些有意思的事情...先不告诉你，让我再看看。"),
        (0.7, "快好了。谢谢你等我。"),
    )

    FINAL_MESSAGE = "我认识你了。以后每天，我都会在。"
    FALLBACK_MESSAGE = "我暂时无法读取你的过去，但我已经开始认识你了。"

    def __init__(self):
        self.state = InitState.INITIALIZING
        self.sync_progress = 0.0
        self._sync_thread: Optional[threading.Thread] = None
        self._sync_error: Optional[Exception] = None
        self._lock = threading.Lock()

    # ---- 公开 API ----

    def start(
        self, sync_func: Optional[Callable[["InitializationHandler"], None]] = None
    ) -> Generator[tuple[float, str], None, None]:
        """启动初始化流程，返回消息生成器。

        每次 yield 返回 (elapsed_seconds, message_text)，
        调用方按需将消息呈现给用户。

        Args:
            sync_func: 后台同步函数，接收 self 作为参数以便更新进度。
                       若为 None，则跳过同步，直接走时序。

        Yields:
            (elapsed, message) — 消息文本及自启动以来的耗时
        """
        start_time = time.time()

        # 启动后台同步
        if sync_func:
            self._sync_thread = threading.Thread(
                target=self._safe_sync, args=(sync_func,), daemon=True
            )
            self._sync_thread.start()

        # Phase 1: 固定时序消息（0s、3s）
        for target, message in self._TIMED_MESSAGES:
            delay = max(0, target - (time.time() - start_time))
            if delay > 0:
                time.sleep(delay)
            yield (time.time() - start_time, message)

        # Phase 2: 进度驱动消息（20s / 90s）
        for threshold, message in self._PROGRESS_MESSAGES:
            self._wait_for_progress(threshold)
            yield (time.time() - start_time, message)

        # Phase 3: 等待同步完成（最长再等 60s）
        if self._sync_thread:
            self._sync_thread.join(timeout=60)

        # Phase 4: 终态消息
        elapsed = time.time() - start_time
        if self._sync_error:
            self.state = InitState.FAILED
            yield (elapsed, self.FALLBACK_MESSAGE)
        else:
            self.state = InitState.IDLE
            yield (elapsed, self.FINAL_MESSAGE)

    # ---- 内部方法 ----

    def _safe_sync(self, sync_func):
        """在后台线程中安全执行同步，捕获异常。"""
        try:
            sync_func(self)
        except Exception as exc:
            self._sync_error = exc

    def _wait_for_progress(self, target: float, poll_interval: float = 0.5) -> None:
        """阻塞等待 sync_progress 达到 target，或同步出错/超时则立即返回。

        每个进度阶段最大等待 70 秒；若同步已失败则不再等待。
        """
        deadline = time.time() + 70.0
        while self.sync_progress < target and time.time() < deadline:
            if self._sync_error is not None:
                return  # 同步已失败，立即退出
            time.sleep(poll_interval)

    def set_progress(self, value: float) -> None:
        """线程安全地更新同步进度 (0.0 ~ 1.0)。"""
        with self._lock:
            self.sync_progress = max(0.0, min(1.0, value))

    # ---- 状态查询 ----

    @property
    def is_initializing(self) -> bool:
        return self.state == InitState.INITIALIZING

    @property
    def is_ready(self) -> bool:
        return self.state in (InitState.IDLE, InitState.FAILED)
