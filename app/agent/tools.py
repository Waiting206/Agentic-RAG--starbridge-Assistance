from pathlib import Path

from langchain.tools import tool

from app.RAG.retriever import retriever
from app.config import COLLECTION_NAME


def build_search_tool(client, embedding_model):
    @tool(response_format="content_and_artifact")
    def search_knowledge_base(query: str) -> tuple[str, list[dict]]:
        """查询星桥协作的企业知识库。

        用于查询产品功能、套餐额度、政策规则、版本变化、
        操作步骤和客服排查流程。

        普通问候、闲聊、用户姓名、用户之前说过的话等，
        不要调用此工具。

        Args:
            query: 用户问题。
        """
        hits = retriever(
            client=client,
            collection_name=COLLECTION_NAME,
            query=query,
            embedding_model=embedding_model,
            limit=5,
        )

        if not hits:
            return "知识库中没有找到相关资料。", []

        context_blocks = []
        sources = []

        for hit in hits:
            entity = hit["entity"]
            text = entity.get("text", "")
            doc_id = entity.get("doc_id", "unknown")
            source_path = entity.get("source", "unknown")
            source_name = entity.get("source_name") or Path(source_path).name

            context_blocks.append(
                f"文档编号：{doc_id}\n"
                f"来源：{source_name}\n"
                f"内容：{text}"
            )
            sources.append(
                {
                    "source": source_name,
                    "doc_id": doc_id,
                    "title": entity.get("title", source_name),
                    "chunk_id": f"chunk_{hit['id']}",
                    "text": text,
                    "score": float(hit.get("distance", 0)),
                }
            )

        return "\n\n".join(context_blocks), sources

    return search_knowledge_base
