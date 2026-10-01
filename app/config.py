import os
from pathlib import Path

from dotenv import load_dotenv


PROJECT_ROOT = Path(__file__).resolve().parent.parent
KNOWLEDGE_BASE_DIR = PROJECT_ROOT / "data" / "knowledge" / "starbridge-rag-starter" / "knowledge_base"

load_dotenv(PROJECT_ROOT / ".env")

POSTGRES_URI = os.getenv("DB_URL")
MILVUS_URI = os.getenv("MILVUS_URI")
DEEPSEEK_API_KEY = os.getenv("DEEPSEEK_API_KEY")
ZHIPUAI_API_KEY = os.getenv("ZHIPUAI_API_KEY")
SUPPORT_ACCESS_TOKEN = os.getenv("SUPPORT_ACCESS_TOKEN")
TOP_K = 5
COLLECTION_NAME = "knowledge_base"
JINA_API_KEY = os.getenv("JINA_API_KEY")
JINA_RERANK_URL = os.getenv("JINA_RERANK_URL", "https://api.jina.ai/v1/rerank")
RERANK_ENABLED = os.getenv("RERANK_ENABLED", "true").lower() in {"1", "true", "yes", "on"}
RERANK_CANDIDATE_K = max(TOP_K, int(os.getenv("RERANK_CANDIDATE_K", "20")))
