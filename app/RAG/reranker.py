"""对已通过权限过滤的 Milvus 候选片段进行重排序。"""

import logging
import math

import requests

from app.config import JINA_API_KEY, JINA_RERANK_URL

logger = logging.getLogger(__name__)


def rerank(query: str, hits: list[dict], top_k: int = 5) -> list[dict]:
    """调用 Jina；服务不可用时保留 Milvus 原有排序。"""
    if not hits:
        return []

    fallback = hits[:top_k]
    if not JINA_API_KEY or JINA_API_KEY == "replace-me":
        logger.warning("未配置 JINA_API_KEY，使用 Milvus 原排序")
        return fallback

    payload = {
        "model": "jina-reranker-v3.5",
        "query": query,
        "documents": [hit["entity"]["text"] for hit in hits],
        "top_n": min(top_k, len(hits)),
        "return_documents": False,
    }

    try:
        response = requests.post(
            JINA_RERANK_URL,
            json=payload,
            headers={"Authorization": f"Bearer {JINA_API_KEY}"},
            timeout=(3, 15),
        )
        response.raise_for_status()
        results = response.json()["results"]
        if not isinstance(results, list) or not results:
            raise ValueError("Jina 未返回重排序结果")

        reranked_hits = []
        seen_indices = set()
        for item in results:
            index = item["index"]
            score = float(item["relevance_score"])
            if (
                not isinstance(index, int)
                or isinstance(index, bool)
                or not 0 <= index < len(hits)
                or index in seen_indices
                or not math.isfinite(score)
            ):
                raise ValueError("Jina 返回了无效的片段索引或分数")
            seen_indices.add(index)
            reranked_hits.append({**hits[index], "rerank_score": score})

        return reranked_hits[:top_k]
    except (requests.RequestException, KeyError, TypeError, ValueError) as exc:
        # 不记录请求正文、文档内容或 API Key。
        logger.warning("Jina 重排序失败（%s），使用 Milvus 原排序", type(exc).__name__)
        return fallback
