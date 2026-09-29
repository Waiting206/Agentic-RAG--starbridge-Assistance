from pathlib import Path

import yaml
from langchain_community.document_loaders import PyPDFLoader
from langchain_core.documents import Document
#上传文件加载器
"""
支持：
- PDF：使用 PyPDFLoader
- TXT：UTF-8 文本读取
- Markdown
- Markdown 可选 YAML 头解析
- 自动补充统一元数据
- 自动忽略 PDF 空白页
- 没有有效文本时拒绝入库
"""
SUPPORTED_EXTENSIONS = {".pdf", ".txt", ".md", ".markdown"}


def _parse_markdown_front_matter(text: str) -> tuple[str, dict]:
    """解析可选的 Markdown YAML 头；普通 Markdown 直接返回原文。"""
    if not text.startswith("---"):
        return text, {}

    parts = text.split("---", 2)
    if len(parts) != 3 or parts[0].strip():
        return text, {}

    fields = yaml.safe_load(parts[1]) or {}
    if not isinstance(fields, dict):
        raise ValueError("Markdown YAML 头必须是键值对象")

    # source 保留给本机真实文件路径，YAML 中的 source 改名保存。
    if "source" in fields:
        fields["source_type"] = fields.pop("source")

    return parts[2].strip(), fields


def load_uploaded_file(
    file_path: Path,
    original_name: str,
    doc_id: str,
    content_sha256: str,
) -> list[Document]:
    """将上传的 PDF、TXT 或 Markdown 转为带统一元数据的 Document。"""
    suffix = file_path.suffix.lower()
    if suffix not in SUPPORTED_EXTENSIONS:
        raise ValueError(f"不支持的文件类型：{suffix}")

    yaml_metadata = {}
    if suffix == ".pdf":
        documents = PyPDFLoader(str(file_path)).load()
    else:
        text = file_path.read_text(encoding="utf-8")
        if suffix in {".md", ".markdown"}:
            text, yaml_metadata = _parse_markdown_front_matter(text)
        documents = [Document(page_content=text)]

    title = yaml_metadata.get("title") or Path(original_name).stem
    common_metadata = {
        **yaml_metadata,
        "doc_id": doc_id,
        "title": title,
        "source": str(file_path),
        "source_name": original_name,
        "content_sha256": content_sha256,
        "category": yaml_metadata.get("category", "uploaded"),
        "status": yaml_metadata.get("status", "active"),
        "audience": yaml_metadata.get("audience", ["customer", "support"]),
    }

    usable_documents = []
    for document in documents:
        document.page_content = document.page_content.strip()
        if not document.page_content:
            continue
        # PDF Loader 自带的 page 元数据会被保留。
        document.metadata.update(common_metadata)
        usable_documents.append(document)

    if not usable_documents:
        raise ValueError("文件中没有可提取的文本内容")

    return usable_documents
