from app.core.config import get_settings
from app.providers.embedding.ollama import create_ollama_embeddings
from app.rag.indexer import KnowledgeIndexer
from app.rag.langchain_chroma_store import create_remote_chroma
from app.rag.repository import KnowledgeRepository


def main() -> None:
    settings = get_settings()
    repository = KnowledgeRepository(settings.data_dir / "knowledge")
    embeddings = create_ollama_embeddings(
        model=settings.ollama_embedding_model,
        base_url=settings.ollama_base_url,
        timeout_seconds=settings.embedding_timeout_seconds,
    )
    store = create_remote_chroma(
        chroma_url=settings.chroma_url,
        collection_name=settings.rag_collection_name,
        embedding_function=embeddings,
    )
    count = KnowledgeIndexer(store).rebuild(repository.list_cards())
    print(
        f"Indexed {count} approved knowledge cards into "
        f"{settings.rag_collection_name} at {settings.chroma_url}."
    )


if __name__ == "__main__":
    main()

