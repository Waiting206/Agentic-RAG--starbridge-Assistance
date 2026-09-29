"""首次部署时为一个空的 Milvus 集合写入项目内置知识库。"""

from app.RAG.Loader import load_documents
from app.RAG.spiltter import document_spitter
from app.RAG.vector_store import (
    COLLECTION_NAME,
    create_embedding_model,
    index_documents,
    init_milvus,
)


def main() -> None:
    client = init_milvus()
    try:
        stats = client.get_collection_stats(COLLECTION_NAME)
        if int(stats.get("row_count", 0)) > 0:
            print(f"Milvus 已有 {stats['row_count']} 个知识片段，跳过初始化。")
            return

        documents = load_documents()
        chunks = document_spitter(documents)
        index_documents(client, chunks, create_embedding_model())
        client.flush(COLLECTION_NAME)
        print(f"知识库初始化完成：{len(documents)} 份文档，{len(chunks)} 个片段。")
    finally:
        client.close()


if __name__ == "__main__":
    main()
