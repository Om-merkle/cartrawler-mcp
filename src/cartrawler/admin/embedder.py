"""
CarTrawler Embedding Builder — importable module
=================================================
Uses the app's own engine and settings so it works on Render
without any extra config. Called from the /admin/embed endpoint.
"""
from __future__ import annotations

import logging

from openai import AsyncOpenAI
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from cartrawler.config import settings
from cartrawler.db.database import engine
from cartrawler.db.models import KnowledgeBase, KnowledgeBaseEmbedding

logger = logging.getLogger("cartrawler.admin.embedder")


async def _embed_batch(texts: list[str]) -> list[list[float]]:
    client = AsyncOpenAI(api_key=settings.openai_api_key)
    response = await client.embeddings.create(
        model=settings.openai_embedding_model,
        input=texts,
    )
    return [item.embedding for item in response.data]


async def run_embed(rebuild: bool = True, batch_size: int = 20) -> dict:
    """
    Generate OpenAI embeddings for all KnowledgeBase rows and store
    them in knowledge_base_embeddings. Returns a summary dict.
    """
    if not settings.openai_api_key:
        raise RuntimeError("OPENAI_API_KEY is not set.")

    async with AsyncSession(engine) as session:
        stmt = select(KnowledgeBase) if rebuild else select(KnowledgeBase).where(
            KnowledgeBase.embedding_ready == False  # noqa: E712
        )
        result = await session.execute(stmt)
        kb_rows = result.scalars().all()

    if not kb_rows:
        return {"embedded": 0, "message": "No rows needed embedding."}

    logger.info("Building embeddings for %d rows (batch=%d)…", len(kb_rows), batch_size)
    total = 0
    errors = []

    for i in range(0, len(kb_rows), batch_size):
        batch = kb_rows[i: i + batch_size]
        texts = [row.content for row in batch]
        try:
            vectors = await _embed_batch(texts)
        except Exception as exc:
            logger.error("OpenAI error on batch %d: %s", i // batch_size, exc)
            errors.append(str(exc))
            continue

        async with AsyncSession(engine) as session:
            for row, vector in zip(batch, vectors):
                if rebuild:
                    existing = await session.execute(
                        select(KnowledgeBaseEmbedding).where(
                            KnowledgeBaseEmbedding.kb_id == row.kb_id
                        )
                    )
                    for old in existing.scalars().all():
                        await session.delete(old)

                session.add(KnowledgeBaseEmbedding(
                    kb_id=row.kb_id,
                    topic=row.topic,
                    content=row.content,
                    embedding=vector,
                ))
                await session.execute(
                    update(KnowledgeBase)
                    .where(KnowledgeBase.kb_id == row.kb_id)
                    .values(embedding_ready=True)
                )
            await session.commit()
            total += len(batch)
            logger.info("  stored %d embeddings (total: %d)", len(batch), total)

    logger.info("Embedding complete. %d rows processed.", total)
    return {"embedded": total, "errors": errors}
