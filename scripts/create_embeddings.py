"""
CarTrawler Embedding Builder
=============================
Reads KnowledgeBase rows that don't yet have embeddings,
generates OpenAI text-embedding-3-small vectors, and stores
them in the knowledge_base_embeddings table (pgvector).

Also sets knowledge_base.embedding_ready = True when done.

Usage:
    uv run python scripts/create_embeddings.py
    uv run python scripts/create_embeddings.py --batch 50
    uv run python scripts/create_embeddings.py --rebuild   # regenerate all
"""
from __future__ import annotations

import asyncio
import logging
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "src"))

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.pool import NullPool

from cartrawler.config import settings
from cartrawler.db.models import KnowledgeBase, KnowledgeBaseEmbedding

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger("embeddings")


# ─────────────────────────────────────────────────────────────────────────────
# OpenAI embedding call
# ─────────────────────────────────────────────────────────────────────────────

async def _embed_batch(texts: list[str]) -> list[list[float]]:
    """Call OpenAI embeddings API for a batch of texts."""
    from openai import AsyncOpenAI

    client = AsyncOpenAI(api_key=settings.openai_api_key)
    response = await client.embeddings.create(
        model=settings.openai_embedding_model,
        input=texts,
    )
    return [item.embedding for item in response.data]


# ─────────────────────────────────────────────────────────────────────────────
# Main build logic
# ─────────────────────────────────────────────────────────────────────────────

async def build_embeddings(batch_size: int = 20, rebuild: bool = False) -> None:
    if not settings.openai_api_key:
        logger.error("OPENAI_API_KEY is not set. Cannot build embeddings.")
        sys.exit(1)

    engine = create_async_engine(settings.database_url, poolclass=NullPool, echo=False)

    async with AsyncSession(engine) as session:
        # Fetch KB rows that need embeddings
        if rebuild:
            stmt = select(KnowledgeBase)
        else:
            stmt = select(KnowledgeBase).where(KnowledgeBase.embedding_ready == False)  # noqa: E712

        result = await session.execute(stmt)
        kb_rows = result.scalars().all()

    if not kb_rows:
        logger.info("No KB rows need embeddings. Done.")
        await engine.dispose()
        return

    logger.info("Building embeddings for %d KB rows (batch=%d)...", len(kb_rows), batch_size)
    total_embedded = 0

    # Process in batches
    for i in range(0, len(kb_rows), batch_size):
        batch = kb_rows[i : i + batch_size]
        texts = [row.content for row in batch]

        logger.info("  Batch %d/%d: embedding %d texts...",
                    i // batch_size + 1,
                    (len(kb_rows) + batch_size - 1) // batch_size,
                    len(texts))

        try:
            vectors = await _embed_batch(texts)
        except Exception as exc:
            logger.error("  OpenAI API error: %s — skipping batch", exc)
            continue

        async with AsyncSession(engine) as session:
            for row, vector in zip(batch, vectors):
                if rebuild:
                    # Delete existing embedding for this kb_id
                    existing = await session.execute(
                        select(KnowledgeBaseEmbedding).where(
                            KnowledgeBaseEmbedding.kb_id == row.kb_id
                        )
                    )
                    for old in existing.scalars().all():
                        await session.delete(old)

                emb = KnowledgeBaseEmbedding(
                    kb_id=row.kb_id,
                    topic=row.topic,
                    content=row.content,
                    embedding=vector,
                )
                session.add(emb)

                # Mark as ready
                await session.execute(
                    update(KnowledgeBase)
                    .where(KnowledgeBase.kb_id == row.kb_id)
                    .values(embedding_ready=True)
                )

            await session.commit()
            total_embedded += len(batch)
            logger.info("  ✓ Stored %d embeddings (total: %d)", len(batch), total_embedded)

    logger.info("Embedding build complete. %d rows processed.", total_embedded)
    await engine.dispose()


def main() -> None:
    import argparse

    parser = argparse.ArgumentParser(description="Build pgvector embeddings for FAQ knowledge base")
    parser.add_argument("--batch", type=int, default=20, help="Batch size for OpenAI API calls")
    parser.add_argument("--rebuild", action="store_true", help="Regenerate all embeddings (not just missing)")
    args = parser.parse_args()

    asyncio.run(build_embeddings(batch_size=args.batch, rebuild=args.rebuild))


if __name__ == "__main__":
    main()
