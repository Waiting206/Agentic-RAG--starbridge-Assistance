import hashlib
import logging
from pathlib import Path
from typing import Annotated, Literal

from fastapi import APIRouter, File, HTTPException, Request, UploadFile, status
from fastapi.concurrency import run_in_threadpool
from pydantic import BaseModel

from app.RAG.spiltter import document_spitter
from app.RAG.upload_loader import SUPPORTED_EXTENSIONS, load_uploaded_file
from app.RAG.vector_store import index_documents
from app.config import COLLECTION_NAME, PROJECT_ROOT
#文件上传接口


logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/knowledge", tags=["knowledge"])

UPLOAD_DIR = PROJECT_ROOT / "data" / "uploads"
MAX_FILE_SIZE = 10 * 1024 * 1024


class UploadResponse(BaseModel):
    status: Literal["success", "exists"]
    message: str
    filename: str
    doc_id: str
    chunks: int

#用来检验文件是否存在
def _existing_chunks(client, doc_id: str) -> list[dict]:
    return client.query(
        collection_name=COLLECTION_NAME,
        filter=f'doc_id == "{doc_id}"',
        output_fields=["id"],
        limit=16_384,
    )


def _index_uploaded_file(request: Request, saved_path: Path, original_name: str, doc_id: str, digest: str) -> int:
    documents = load_uploaded_file(saved_path, original_name, doc_id, digest)
    chunks = document_spitter(documents)
    if not chunks:
        raise ValueError("文件切分后没有可写入的知识片段")

    index_documents(
        request.app.state.milvus_client,
        chunks,
        request.app.state.embedding_model,
    )
    # 确保接口返回后新知识立即对检索可见。
    request.app.state.milvus_client.flush(COLLECTION_NAME)
    return len(chunks)


@router.post(
    "/upload",
    response_model=UploadResponse,
    status_code=status.HTTP_201_CREATED,
)
async def upload_knowledge(
    file: Annotated[UploadFile, File()],
    request: Request,
) -> UploadResponse:
    original_name = Path(file.filename or "").name
    suffix = Path(original_name).suffix.lower()

    if not original_name or suffix not in SUPPORTED_EXTENSIONS:
        raise HTTPException(
            status_code=status.HTTP_415_UNSUPPORTED_MEDIA_TYPE,
            detail="仅支持 PDF、TXT 和 Markdown 文件。",
        )

    content = await file.read(MAX_FILE_SIZE + 1)
    await file.close()

    if not content:
        raise HTTPException(status_code=400, detail="上传文件不能为空。")
    if len(content) > MAX_FILE_SIZE:
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail="文件不能超过 10 MB。",
        )

    digest = hashlib.sha256(content).hexdigest()
    doc_id = f"UPLOAD-{digest[:16].upper()}"

    existing = await run_in_threadpool(
        _existing_chunks,
        request.app.state.milvus_client,
        doc_id,
    )
    if existing:
        return UploadResponse(
            status="exists",
            message=f"该文件已存在，共 {len(existing)} 个知识片段。",
            filename=original_name,
            doc_id=doc_id,
            chunks=len(existing),
        )

    UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
    saved_path = UPLOAD_DIR / f"{doc_id}{suffix}"
    await run_in_threadpool(saved_path.write_bytes, content)#让同步任务在线程池中运行

    try:#文档处理阶段
        chunk_count = await run_in_threadpool(
            _index_uploaded_file,
            request,
            saved_path,
            original_name,
            doc_id,
            digest,
        )
    except ValueError as exc:
        saved_path.unlink(missing_ok=True)
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    except Exception as exc:
        logger.exception("知识文件处理失败：filename=%s doc_id=%s", original_name, doc_id)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="文件解析或向量化失败。",
        ) from exc

    return UploadResponse(
        status="success",
        message=f"上传成功，已写入 {chunk_count} 个知识片段。",
        filename=original_name,
        doc_id=doc_id,
        chunks=chunk_count,
    )
