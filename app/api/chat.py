"""聊天接口：普通 JSON 响应与 SSE 流式响应。"""

import json
import logging
from typing import Annotated

from fastapi import APIRouter, Header, Request,status
from fastapi.responses import StreamingResponse
from langchain_core.messages import AIMessageChunk, HumanMessage,ToolMessage
from pydantic import BaseModel, Field

from app.agent.context import AgentContext
from app.security import AccessRole, authorize_role, checkpoint_thread_id

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api", tags=["chat"])


class ChatRequest(BaseModel):# 定义请求数据应该长什么样 在告诉 FastAPI：我预计客户端传过来的 body 应该长这样
    message: str = Field(min_length=1, max_length=4_000)
    thread_id: str = Field(min_length=1, max_length=128)
    role: AccessRole = "customer"


class ChatResponse(BaseModel):
    answer: str
    thread_id: str


def _agent_config(thread_id: str, role: AccessRole) -> dict:
    return {"configurable": {"thread_id": checkpoint_thread_id(thread_id, role)}}#防止客户和客服碰巧使用相同thread_id后共享历史记录。


def _message_input(message: str) -> dict:
    return {"messages": [HumanMessage(message.strip())]}


@router.post("/chat", response_model=ChatResponse)
def chat(
    request_data: ChatRequest,
    request: Request,
    support_token: Annotated[
        str | None,
        Header(alias="X-Support-Token"),
    ] = None,
) -> ChatResponse:
    """返回完整回答，适合先在 Swagger 中调试。"""
    role = authorize_role(request_data.role, support_token)
    agent = request.app.state.agent
    result = agent.invoke(
        _message_input(request_data.message),
        config=_agent_config(request_data.thread_id, role),
        context=AgentContext(role=role),
    )
    answer = result["messages"][-1]
    return ChatResponse(
        answer=answer.content if isinstance(answer.content, str) else str(answer.content),
        thread_id=request_data.thread_id,
    )


def _sse(event: str, data: dict) -> str:
    return f"event: {event}\ndata: {json.dumps(data, ensure_ascii=False)}\n\n"

#流式接口
@router.post("/chat/stream")
def stream_chat(
    request_data: ChatRequest,
    request: Request,
    support_token: Annotated[
        str | None,
        Header(alias="X-Support-Token"),
    ] = None,
) -> StreamingResponse:
    """只把最终回答的文字片段以 SSE 返回，不暴露工具和摘要内部消息。"""
    role = authorize_role(request_data.role, support_token)
    agent = request.app.state.agent

    def event_stream():
        sources_by_chunk = {}
        try:
            for message, metadata in agent.stream(
                _message_input(request_data.message),
                stream_mode="messages",
                config=_agent_config(request_data.thread_id, role),
                context=AgentContext(role=role),
            ):
                # 捕获知识库工具返回的结构化来源
                if isinstance(message, ToolMessage):
                    artifact = message.artifact
                    if isinstance(artifact, list):
                        for source in artifact:
                            chunk_id = source.get("chunk_id")
                            if chunk_id:
                                sources_by_chunk[chunk_id] = source
                # 过滤 只保留最终回答的文字片段
                is_final_answer_chunk = (
                    metadata.get("langgraph_node") == "model"
                    and isinstance(message, AIMessageChunk)
                    and bool(message.content)
                )
                if is_final_answer_chunk:
                    yield _sse("message", {"delta": message.content})

            # 回答完成后只发送一次检索来源。
            yield _sse(
                "sources",
                {"sources": list(sources_by_chunk.values())},
            )
            yield _sse("done", {"thread_id": request_data.thread_id})
        except Exception:
            logger.exception("聊天流生成失败")
            yield _sse("error", {"detail": "回答生成失败，请稍后重试。"})

    return StreamingResponse(
        event_stream(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )
