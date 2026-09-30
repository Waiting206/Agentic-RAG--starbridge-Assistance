from app.security import AccessRole


def audience_filter_for_role(role: AccessRole) -> str:
    """只允许检索元数据audience中包含当前角色的知识片段。"""
    return f'JSON_CONTAINS(audience, "{role}")'


def retriever(
    client,
    collection_name,
    query,
    embedding_model,
    limit=3,
    role: AccessRole = "customer",
):
    query_vector = embedding_model.embed_query(query)
    results = client.search(
        collection_name=collection_name,
        data=[query_vector],
        limit=limit,
        filter=audience_filter_for_role(role),
        output_fields=[
            "text",
            "source",
            "source_name",
            "doc_id",
            "title",
            "audience",
            "page",
            "start_index",
        ],
    )
    return results[0]
