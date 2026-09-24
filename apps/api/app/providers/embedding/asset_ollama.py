"""Ollama text embeddings with a checked local model digest for index compatibility."""

import hashlib

import httpx

from app.providers.embedding.ollama import create_ollama_embeddings


class AssetOllamaEmbeddings:
    def __init__(self, *, model, base_url, timeout_seconds=15):
        self.model = model if ":" in model else model + ":latest"
        self.base_url = base_url.rstrip("/")
        self.provider = create_ollama_embeddings(
            model=model,
            base_url=base_url,
            timeout_seconds=timeout_seconds,
        )

    def identity(self):
        response = httpx.get(f"{self.base_url}/api/tags", timeout=3)
        response.raise_for_status()
        entry = next(item for item in response.json()["models"] if item["name"] == self.model)
        digest = entry["digest"]
        if not isinstance(digest, str) or not digest:
            raise ValueError("Missing embedding model digest")
        endpoint = hashlib.sha256(self.base_url.encode()).hexdigest()[:12]
        return f"ollama:{endpoint}:{self.model}:{digest}"

    def embed_documents(self, texts):
        return self.provider.embed_documents(texts)

    def embed_query(self, text):
        return self.provider.embed_query(text)
