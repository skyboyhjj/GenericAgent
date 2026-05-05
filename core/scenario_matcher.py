"""场景匹配器 —— 为慧惠在生成回复时检索最相关的场景模板

基于关键词命中率的轻量级匹配，延迟 < 1ms，确保不影响回复生成速度。

匹配策略：
1. 优先使用精确子串匹配
2. 对中文关键词，启用字符级模糊匹配（关键词所有字符均在输入中出现即命中）
3. 按命中率排序，返回最相关的场景
"""

from typing import Any


def _chinese_char_match(keyword: str, text: str) -> bool:
    """中文关键词的字符级匹配：关键词的所有字符是否均在文本中出现。

    用于处理中文关键词无法精确子串匹配的情况。
    例如：关键词 "今天要做" 可匹配输入 "我今天有6件事要做"（所有字符均出现）
    """
    return all(ch in text for ch in keyword)


class ScenarioMatcher:
    """基于关键词的轻量级场景匹配器。

    匹配算法：
    1. 标准化用户输入（小写、去空白）
    2. 对每个场景，计算 intent_keywords 在输入中的命中率
       - 精确子串匹配优先
       - 中文关键词启用字符级模糊匹配
    3. 过滤低于 min_score 的场景
    4. 按相关度降序排列
    5. 返回前 max_results 个结果
    """

    def __init__(self, min_score: float = 0.6):
        """初始化匹配器。

        Args:
            min_score: 最低匹配分数阈值（0.0~1.0），低于此值不返回。
                       表示关键词命中数占总关键词数的比例下限。
        """
        self.min_score = min_score

    def _keyword_hits(self, keywords: list[str], text: str) -> int:
        """计算关键词在文本中的命中数。

        对每个关键词依次尝试：
        1. 精确子串匹配（不区分大小写）
        2. 中文关键词：字符级模糊匹配
        """
        hits = 0
        for kw in keywords:
            kw_lower = kw.lower()
            if kw_lower in text:
                hits += 1
            elif any('\u4e00' <= ch <= '\u9fff' for ch in kw):
                # 中文关键词：尝试字符级匹配
                if _chinese_char_match(kw_lower, text):
                    hits += 1
        return hits

    def match(
        self,
        user_input: str,
        scenarios: list[dict[str, Any]],
        max_results: int = 3,
    ) -> list[dict[str, Any]]:
        """匹配与用户输入最相关的场景模板。

        Args:
            user_input: 用户输入文本
            scenarios: 场景模板列表（JSON 数组）
            max_results: 最大返回数量（默认 3）

        Returns:
            按相关度降序排列的场景列表，最多 max_results 个；
            若无匹配返回空列表。
        """
        if not user_input or not scenarios:
            return []

        normalized = user_input.lower().strip()
        scored: list[tuple[float, dict[str, Any]]] = []

        for scene in scenarios:
            keywords: list[str] = scene.get("intent_keywords", [])
            if not keywords:
                continue

            hits = self._keyword_hits(keywords, normalized)
            score = hits / len(keywords)

            if score >= self.min_score:
                scored.append((score, scene))

        # 按相关度降序排列
        scored.sort(key=lambda x: x[0], reverse=True)

        return [scene for _, scene in scored[:max_results]]
