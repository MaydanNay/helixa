from qdrant_client import QdrantClient
from qdrant_client.http import models
import os
import asyncio
import uuid
import logging
from app.services.gemini_client import gemini_client

logger = logging.getLogger(__name__)

class MemoryService:
    def __init__(self):
        qdrant_url = os.getenv("QDRANT_URL", "http://qdrant:6333")
        try:
            self.client = QdrantClient(url=qdrant_url)
            self.client.get_collections()
            logger.info("Connected to Qdrant at %s", qdrant_url)
        except Exception:
            logger.warning("Could not connect to Qdrant at '%s'. Using in-memory storage.", qdrant_url)
            self.client = QdrantClient(":memory:")

    async def init_collection(self, collection_name: str):
        """
        Creates a collection for a specific AI Model's memory.
        """
        exists = await asyncio.to_thread(self.client.collection_exists, collection_name)
        if not exists:
            await asyncio.to_thread(
                self.client.create_collection,
                collection_name=collection_name,
                vectors_config=models.VectorParams(size=1536, distance=models.Distance.COSINE),
            )

    # Alias used by router.py
    async def create_collection_if_not_exists(self, collection_name: str):
        await self.init_collection(collection_name)

    async def add_memory(self, collection_name: str, text: str, vector: list[float], metadata: dict = None):
        """
        Adds a piece of memory (fact, interaction) to the model's vector store.
        """
        if not vector:
            logger.warning("Attempted to add memory to '%s' with None vector. Skipping.", collection_name)
            return

        point = models.PointStruct(
            id=str(uuid.uuid4()),
            vector=vector,
            payload={"text": text, **(metadata or {})}
        )
        await asyncio.to_thread(self.client.upsert, collection_name=collection_name, points=[point])

    async def add_memories(self, collection_name: str, texts: list[str], metadatas: list[dict] = None):
        """
        Bulk-adds multiple memory texts. Each text is auto-embedded via Gemini.
        Called by the memory stream endpoint in router.py.
        """
        metadatas = metadatas or [{} for _ in texts]
        points = []
        for text, meta in zip(texts, metadatas):
            try:
                vector = await gemini_client.generate_embedding(text)
                if not vector:
                    continue
                points.append(
                    models.PointStruct(
                        id=str(uuid.uuid4()),
                        vector=vector,
                        payload={"text": text, **meta}
                    )
                )
            except Exception as e:
                logger.warning("Failed to embed memory text (skipping): %s", e)
        if points:
            await asyncio.to_thread(self.client.upsert, collection_name=collection_name, points=points)
            logger.info("Added %d memories to collection %s", len(points), collection_name)

    async def delete_collection(self, collection_name: str):
        """
        Deletes a collection from Qdrant (e.g. when the agent is deleted from the DB).
        """
        try:
            exists = await asyncio.to_thread(self.client.collection_exists, collection_name)
            if exists:
                await asyncio.to_thread(self.client.delete_collection, collection_name)
                logger.info("Deleted Qdrant collection: %s", collection_name)
            return True
        except Exception as e:
            logger.warning("Could not delete Qdrant collection '%s': %s", collection_name, e)
            return False

    async def search_memory(self, collection_name: str, query: str, limit: int = 5):
        """
        Searches memory using text query (auto-embedding).
        """
        vector = await gemini_client.generate_embedding(query)
        if not vector:
            logger.warning("Failed to generate embedding for query: %s", query)
            return []
            
        search_result = await asyncio.to_thread(
            self.client.query_points,
            collection_name=collection_name,
            query=vector,
            limit=limit
        )
        return [hit.payload for hit in search_result.points]

memory_service = MemoryService()
