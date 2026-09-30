from typing import Annotated
import logging
from fastapi import HTTPException, Header, Path, Query, Request, Response, status, APIRouter

from app.security import AccessRole, authorize_role, checkpoint_thread_id
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
    role: Annotated[AccessRole, Query()] = "customer",
    support_token: Annotated[str | None, Header(alias="X-Support-Token")] = None,
) -> Response:
    authorized_role = authorize_role(role, support_token)
    try:
        checkpointer = request.app.state.checkpointer
        checkpointer.delete_thread(checkpoint_thread_id(thread_id, authorized_role))
    except Exception:
        logger.exception("删除会话失败：thread_id=%s", thread_id)
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="删除会话失败，请稍后重试。",
        )

    return Response(status_code=status.HTTP_204_NO_CONTENT)
