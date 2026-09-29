def retriever(client, collection_name, query, embedding_model, limit=3):
    query_vector = embedding_model.embed_query(query)
    results = client.search(
        collection_name=collection_name,
        data=[query_vector],
        limit=limit,
        output_fields=[
            "text",
            "source",
            "source_name",
            "doc_id",
            "title",
            "page",
            "start_index",
        ],
    )
    return results[0]
