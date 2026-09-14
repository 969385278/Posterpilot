"""Embedding provider adapters."""

from app.providers.embedding.ollama import create_ollama_embeddings

__all__ = ["create_ollama_embeddings"]

