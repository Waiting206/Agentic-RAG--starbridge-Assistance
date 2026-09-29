"""聊天接口：普通 JSON 响应与 SSE 流式响应。"""

import json
import logging

from fastapi import APIRouter, Request,status
from fastapi.responses import StreamingResponse
from langchain_core.messages import AIMessageChunk, HumanMessage,ToolMessage
from pydantic import BaseModel, Field


logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api", tags=["chat"])


class ChatRequest(BaseModel):
    message: str = Field(min_length=1, max_length=4_000)
    thread_id: str = Field(min_length=1, max_length=128)


class ChatResponse(BaseModel):# 定义请求数据应该长什么样 在告诉 FastAPI：我预计客户端传过来的 body 应该长这样
    answer: str
    thread_id: str


def _agent_config(thread_id: str) -> dict:
    return {"configurable": {"thread_id": thread_id}}


def _message_input(message: str) -> dict:
    return {"messages": [HumanMessage(message.strip())]}


@router.post("/chat", response_model=ChatResponse)
def chat(request_data: ChatRequest, request: Request) -> ChatResponse:
    """返回完整回答，适合先在 Swagger 中调试。"""
    agent = request.app.state.agent
    result = agent.invoke(
        _message_input(request_data.message),
        config=_agent_config(request_data.thread_id),
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
def stream_chat(request_data: ChatRequest, request: Request) -> StreamingResponse:
    """只把最终回答的文字片段以 SSE 返回，不暴露工具和摘要内部消息。"""
    agent = request.app.state.agent

    def event_stream():
        sources_by_chunk = {}
        try:
            for message, metadata in agent.stream(
                _message_input(request_data.message),
                stream_mode="messages",
                config=_agent_config(request_data.thread_id),
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
