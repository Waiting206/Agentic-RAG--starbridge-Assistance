"""访问角色校验与会话命名空间。"""

import secrets
from typing import Literal

from fastapi import HTTPException, status

from app.config import SUPPORT_ACCESS_TOKEN


AccessRole = Literal["customer", "support"]


def authorize_role(role: AccessRole, support_token: str | None) -> AccessRole:
    """校验请求角色；客服角色必须持有服务端配置的密钥。"""
    if role == "customer":
        return role

    if (
        not SUPPORT_ACCESS_TOKEN
        or not support_token
        or not secrets.compare_digest(support_token, SUPPORT_ACCESS_TOKEN)
    ):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="无权使用客服知识库。",
        )
    return role


def checkpoint_thread_id(thread_id: str, role: AccessRole) -> str:
    """按角色隔离Checkpointer，避免相同thread_id共享内部对话历史。"""
    return f"{role}:{thread_id}"
