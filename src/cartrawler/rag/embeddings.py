"""
Embeddings Builder
===================
Creates and stores pgvector embeddings for the knowledge_base table.
Run once after seeding: python scripts/create_embeddings.py
"""
from __future__ import annotations

import asyncio
import json

from openai import AsyncOpenAI
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from cartrawler.config import settings
from cartrawler.db.database import AsyncSessionLocal
from cartrawler.db.models import KnowledgeBase, KnowledgeBaseEmbedding


async def build_embeddings(batch_size: int = 20) -> dict:
    """
    Generate and store embeddings for all knowledge_base rows
    that do not yet have an embedding in knowledge_base_embeddings.
    """
    client = AsyncOpenAI(api_key=settings.openai_api_key)

    async with AsyncSessionLocal() as db:
        # Find KB rows without embeddings
        existing_r = await db.execute(select(KnowledgeBaseEmbedding.kb_id))
        existing_ids = {row[0] for row in existing_r.fetchall()}

        kb_r = await db.execute(select(KnowledgeBase))
        all_kb = kb_r.scalars().all()

        pending = [kb for kb in all_kb if kb.kb_id not in existing_ids]

        if not pending:
            return {"success": True, "message": "All knowledge base entries already have embeddings.", "count": 0}

        total_created = 0

        for i in range(0, len(pending), batch_size):
            batch = pending[i : i + batch_size]
            texts = [f"Topic: {kb.topic}\n{kb.content}" for kb in batch]

            try:
                response = await client.embeddings.create(
                    model=settings.openai_embedding_model,
                    input=texts,
                )
            except Exception as exc:
                return {
                    "success": False,
                    "message": f"OpenAI embedding API error: {exc}",
                    "count": total_created,
                }

            for kb, embedding_data in zip(batch, response.data):
                emb_row = KnowledgeBaseEmbedding(
                    kb_id=kb.kb_id,
                    topic=kb.topic,
                    content=kb.content,
                    embedding=embedding_data.embedding,
                )
                db.add(emb_row)

                # Mark embedding_ready
                kb.embedding_ready = True

            await db.commit()
            total_created += len(batch)
            print(f"  Embedded batch {i // batch_size + 1}: {len(batch)} entries")

    return {
        "success": True,
        "message": f"Created embeddings for {total_created} knowledge base entries.",
        "count": total_created,
    }
