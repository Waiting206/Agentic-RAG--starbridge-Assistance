import hashlib

from langchain.embeddings import init_embeddings
from langchain_core.documents import Document
from pymilvus import MilvusClient

from app.config import COLLECTION_NAME, MILVUS_URI, ZHIPUAI_API_KEY

#本文件负责向量化和Milvus写入
def create_embedding_model():
    if not ZHIPUAI_API_KEY:
        raise RuntimeError("未配置 ZHIPUAI_API_KEY，请检查 .env 文件")

    return init_embeddings(
        model="openai:embedding-3",
        api_key=ZHIPUAI_API_KEY,
        base_url="https://open.bigmodel.cn/api/paas/v4",
    )


def embedding(chunks, embedding_model=None):
    embedding_model = embedding_model or create_embedding_model()
    return embedding_model.embed_documents([chunk.page_content for chunk in chunks])


def init_milvus(uri: str | None = MILVUS_URI, recreate: bool = False):
    """连接 Milvus，并确保知识库集合存在。"""
    if not uri:
        raise RuntimeError("未配置 MILVUS_URI，请检查 .env 文件")

    client = MilvusClient(uri)
    database_name = "starbridge_rag"
    if database_name not in client.list_databases():
        client.create_database(database_name)
    client.use_database(database_name)

    exists = COLLECTION_NAME in client.list_collections()
    if exists and recreate:
        client.drop_collection(COLLECTION_NAME)
        exists = False

    if not exists:
        client.create_collection(
            collection_name=COLLECTION_NAME,
            dimension=2048,
            metric_type="COSINE",
            enable_dynamic_field=True,
        )

    return client


def create_chunk_id(chunk: Document) -> int:
    """根据文档身份和片段位置生成可重复计算的 Milvus Int64 主键。"""
    # doc_id 区分不同文档。上传接口会根据文件内容哈希生成唯一 doc_id。
    doc_id = chunk.metadata.get("doc_id")
    # PDF Loader 会提供页码；Markdown/TXT 没有页码时统一按第 0 页处理。
    page = chunk.metadata.get("page", 0)
    # splitter 的 add_start_index=True 会记录片段在当前文档/页面中的起点。
    start_index = chunk.metadata.get("start_index")

    if not doc_id:
        raise ValueError("文档缺少 doc_id，无法生成 chunk_id")
    if start_index is None:
        raise ValueError(f"文档 {doc_id} 的片段缺少 start_index")

    # 相同文档、页码和起点始终得到相同字符串，因此重复导入会命中同一主键。
    raw_id = f"{doc_id}:{page}:{start_index}"
    # BLAKE2b 将可读身份压缩成固定 8 字节；碰撞概率对当前项目规模可忽略。
    digest = hashlib.blake2b(raw_id.encode("utf-8"), digest_size=8).digest()

    # Collection 的主键是有符号 Int64。清除最高符号位，保证结果位于 0～2^63-1。
    return int.from_bytes(digest, byteorder="big", signed=False) & ((1 << 63) - 1)


def insert_to_milvus(chunks, vectors, client):
    data = []
    optional_metadata = (
        "source_name",
        "title",
        "category",
        "status",
        "version",
        "audience",
        "content_sha256",
    )

    for chunk, vector in zip(chunks, vectors, strict=True):
        record = {
            "id": create_chunk_id(chunk),
            "text": chunk.page_content,
            "vector": vector,
            "source": chunk.metadata.get("source", "unknown"),
            "doc_id": chunk.metadata["doc_id"],
            "start_index": chunk.metadata.get("start_index", 0),
            "page": chunk.metadata.get("page", 0),
        }
        for field in optional_metadata:
            value = chunk.metadata.get(field)
            if value is not None:
                record[field] = value
        data.append(record)

    client.upsert(data=data, collection_name=COLLECTION_NAME)


def index_documents(client, chunks, embedding_model=None):
    vectors = embedding(chunks, embedding_model)
    insert_to_milvus(chunks, vectors, client)
