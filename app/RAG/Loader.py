from pathlib import Path

import yaml
from langchain_community.document_loaders import DirectoryLoader, TextLoader

from app.config import KNOWLEDGE_BASE_DIR


def load_documents(path: str | Path = KNOWLEDGE_BASE_DIR, glob: str = "**/*.md"):
    """加载 Markdown 知识库，并把 YAML 头写入文档元数据。"""
    loader = DirectoryLoader(
        path=str(path),
        glob=glob,
        use_multithreading=True,
        show_progress=True,
        loader_cls=TextLoader,
        loader_kwargs={"encoding": "utf-8"},
    )
    docs = loader.load()
#解析YAML开头
    for doc in docs:
        parts = doc.page_content.split("---", 2)
        if len(parts) != 3 or parts[0].strip():
            raise ValueError(f"缺少 YAML 头：{doc.metadata.get('source')}")

        fields = yaml.safe_load(parts[1])
        if not isinstance(fields, dict):
            raise ValueError(f"YAML 格式有误：{doc.metadata.get('source')}")

        # YAML 的 source=synthetic 不覆盖 TextLoader 记录的真实文件路径。
        if "source" in fields:
            fields["source_type"] = fields.pop("source")

        doc.metadata.update(fields)
        doc.page_content = parts[2].strip()

    return docs


if __name__ == "__main__":
    print(f"已加载 {len(load_documents())} 份文档")
