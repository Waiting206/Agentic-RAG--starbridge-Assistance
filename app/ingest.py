from RAG.Loader import load_documents
from RAG.spiltter import document_spitter
from RAG.vector_store import init_milvus, create_embedding_model, index_documents


def ingest(recreate: bool = False) -> int:
    """加载知识库、切分文本并写入 Milvus。"""
    documents = load_documents()
    chunks = document_spitter(documents)
    client = init_milvus(recreate=recreate)
    embedding_model = create_embedding_model()
    index_documents(client, chunks, embedding_model)

    print(f"索引完成：{len(documents)} 份文档，{len(chunks)} 个片段。")
    return len(chunks)