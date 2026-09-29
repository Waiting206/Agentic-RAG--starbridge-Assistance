from typing import Annotated
import logging
from fastapi import HTTPException, Path, Request, Response, status, APIRouter
logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api", tags=["threads"])
#会话删除接口
@router.delete(
    "/threads/{thread_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
def delete_chat_thread(
    thread_id: Annotated[str, Path(min_length=1, max_length=128)],
    request: Request,
) -> Response:
    try:
        checkpointer = request.app.state.checkpointer
        checkpointer.delete_thread(thread_id)
    except Exception:
        logger.exception("删除会话失败：thread_id=%s", thread_id)
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="删除会话失败，请稍后重试。",
        )

    return Response(status_code=status.HTTP_204_NO_CONTENT)