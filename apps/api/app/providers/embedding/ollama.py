from langchain_ollama import OllamaEmbeddings


def create_ollama_embeddings(
    *,
    model: str,
    base_url: str,
    timeout_seconds: float = 120,
) -> OllamaEmbeddings:
    return OllamaEmbeddings(
        model=model,
        base_url=base_url,
        client_kwargs={"timeout": timeout_seconds},
        async_client_kwargs={"timeout": timeout_seconds},
    )

