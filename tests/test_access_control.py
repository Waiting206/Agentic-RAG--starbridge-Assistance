import pytest
from fastapi import FastAPI, HTTPException
from fastapi.testclient import TestClient
from langchain_core.messages import AIMessage
from pydantic import ValidationError

from app.RAG.retriever import audience_filter_for_role, retriever
from app.agent.context import AgentContext
from app.agent.tools import build_search_tool
from app.api.chat import ChatRequest, _agent_config, router as chat_router
from app.config import SUPPORT_ACCESS_TOKEN
from app.security import authorize_role, checkpoint_thread_id


class FakeEmbeddingModel:
    def embed_query(self, query):
        assert query == "测试问题"
        return [0.1, 0.2]


class FakeMilvusClient:
    def __init__(self):
        self.search_kwargs = None

    def search(self, **kwargs):
        self.search_kwargs = kwargs
        return [[]]


class FakeAgent:
    def __init__(self):
        self.last_config = None
        self.last_context = None

    def invoke(self, message_input, config, context):
        self.last_config = config
        self.last_context = context
        return {"messages": [*message_input["messages"], AIMessage("测试回答")]}


def create_api_client():
    app = FastAPI()
    app.include_router(chat_router)
    app.state.agent = FakeAgent()
    return TestClient(app), app.state.agent


def test_customer_is_default_role():
    request = ChatRequest(message="测试", thread_id="session_1")
    assert request.role == "customer"


def test_unknown_role_is_rejected():
    with pytest.raises(ValidationError):
        ChatRequest(message="测试", thread_id="session_1", role="admin")


def test_support_role_requires_server_token():
    with pytest.raises(HTTPException) as exc_info:
        authorize_role("support", None)
    assert exc_info.value.status_code == 403


def test_configured_support_token_is_accepted():
    assert SUPPORT_ACCESS_TOKEN
    assert authorize_role("support", SUPPORT_ACCESS_TOKEN) == "support"


def test_roles_use_different_checkpoint_namespaces():
    assert checkpoint_thread_id("same", "customer") == "customer:same"
    assert checkpoint_thread_id("same", "support") == "support:same"
    assert _agent_config("same", "customer") != _agent_config("same", "support")


@pytest.mark.parametrize(
    ("role", "expected"),
    [
        ("customer", 'JSON_CONTAINS(audience, "customer")'),
        ("support", 'JSON_CONTAINS(audience, "support")'),
    ],
)
def test_audience_filter(role, expected):
    assert audience_filter_for_role(role) == expected


def test_retriever_passes_customer_filter_to_milvus():
    client = FakeMilvusClient()
    hits = retriever(
        client=client,
        collection_name="knowledge_base",
        query="测试问题",
        embedding_model=FakeEmbeddingModel(),
        limit=5,
        role="customer",
    )

    assert hits == []
    assert client.search_kwargs["filter"] == 'JSON_CONTAINS(audience, "customer")'
    assert "audience" in client.search_kwargs["output_fields"]


def test_runtime_context_is_hidden_from_model_tool_arguments():
    tool = build_search_tool(FakeMilvusClient(), FakeEmbeddingModel())
    assert set(tool.tool_call_schema.model_fields) == {"query"}


def test_customer_api_uses_customer_context_and_namespace():
    client, agent = create_api_client()
    response = client.post(
        "/api/chat",
        json={"message": "测试", "thread_id": "same"},
    )

    assert response.status_code == 200
    assert agent.last_context == AgentContext(role="customer")
    assert agent.last_config["configurable"]["thread_id"] == "customer:same"


def test_support_api_rejects_missing_token():
    client, _ = create_api_client()
    response = client.post(
        "/api/chat",
        json={"message": "测试", "thread_id": "same", "role": "support"},
    )
    assert response.status_code == 403


def test_support_api_accepts_configured_token_and_isolates_thread():
    client, agent = create_api_client()
    response = client.post(
        "/api/chat",
        headers={"X-Support-Token": SUPPORT_ACCESS_TOKEN},
        json={"message": "测试", "thread_id": "same", "role": "support"},
    )

    assert response.status_code == 200
    assert agent.last_context == AgentContext(role="support")
    assert agent.last_config["configurable"]["thread_id"] == "support:same"
