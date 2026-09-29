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
TOP_K = 5
COLLECTION_NAME = "knowledge_base"
