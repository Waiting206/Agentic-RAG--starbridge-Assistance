from langchain_text_splitters import RecursiveCharacterTextSplitter


def document_spitter(docs):
    splitter = RecursiveCharacterTextSplitter(
        chunk_size=400,
        chunk_overlap=0,
        add_start_index=True,
        length_function=len
    )
    chunks = splitter.split_documents(docs)
    return chunks
