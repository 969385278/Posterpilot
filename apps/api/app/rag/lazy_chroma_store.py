"""Connect on demand so an offline vector service does not prevent API startup."""

import asyncio
from urllib.parse import urlparse

from app.rag.langchain_chroma_store import ChromaVectorStore, create_remote_chroma


class LazyRemoteChromaStore:
    def __init__(self, *, chroma_url, collection_name, embedding_function):
        parsed = urlparse(chroma_url)
        if parsed.scheme not in {"http", "https"} or not parsed.hostname:
            raise ValueError("CHROMA_URL must be an http or https URL")
        self.options = {
            "chroma_url": chroma_url,
            "collection_name": collection_name,
            "embedding_function": embedding_function,
        }
        self._store = None
        self._connection = None

    @staticmethod
    def _observe_result(task):
        # A request can disconnect while its shielded connection attempt continues.
        # Retrieve failures even when that attempt currently has no waiting caller.
        if not task.cancelled():
            task.exception()

    async def _connect(self):
        chroma = await asyncio.to_thread(create_remote_chroma, **self.options)
        return ChromaVectorStore(chroma)

    async def _get_store(self):
        if self._store is not None:
            return self._store
        pending = self._connection
        if pending is None or (
            pending.done() and (pending.cancelled() or pending.exception() is not None)
        ):
            pending = asyncio.create_task(self._connect())
            pending.add_done_callback(self._observe_result)
            self._connection = pending
        # Cancelling one search must not cancel a connection shared by other runs,
        # or cause duplicate background initialization on the next search.
        store = await asyncio.shield(pending)
        self._store = store
        return store

    async def search(self, query, *, candidate_ids, limit):
        if not candidate_ids:
            return []
        store = await self._get_store()
        try:
            return await store.search(query, candidate_ids=candidate_ids, limit=limit)
        except Exception:
            # A restarted server may invalidate a collection handle. Reconnect on
            # the next request; never replace this failed result with fake hits.
            if self._store is store:
                self._store = None
                self._connection = None
            raise
