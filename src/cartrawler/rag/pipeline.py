"""
RAG Pipeline for FAQ / Knowledge Base
=======================================
Architecture:
  User Query
    → Embedding (text-embedding-3-small via OpenAI async)
    → pgvector cosine similarity search directly against knowledge_base_embeddings
    → Top-K chunks retrieved
    → LLM (GPT-4o-mini) generates grounded answer
    → Response returned to MCP caller
"""
from __future__ import annotations

import logging

from openai import AsyncOpenAI
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from cartrawler.config import settings
from cartrawler.db.database import engine

logger = logging.getLogger("cartrawler.rag.pipeline")

# ─────────────────────────────────────────────────────────────────────────────
# Prompt
# ─────────────────────────────────────────────────────────────────────────────

SYSTEM_PROMPT = """You are a helpful assistant for CarTrawler — a global car rental booking platform.

Answer the user's question using ONLY the provided context from the knowledge base.
If the context does not contain a clear answer, politely say you don't have that information
and suggest the user contacts support or checks the website.

Context:
{context}

Rules:
- Be concise (2-4 sentences max unless a list is needed).
- Do not make up information not present in the context.
- Always mention relevant policies or tips when applicable.
"""


# ─────────────────────────────────────────────────────────────────────────────
# FAQ Pipeline
# ─────────────────────────────────────────────────────────────────────────────

class FAQPipeline:
    """
    RAG pipeline backed by pgvector using direct async SQL.

    Embeds the query with OpenAI, runs a cosine similarity search directly
    against `knowledge_base_embeddings`, then passes retrieved context to
    GPT-4o-mini to produce a grounded answer.
    """

    async def ask(self, question: str) -> dict:
        """
        Answer a FAQ question using retrieval-augmented generation.

        Returns:
            {
                "success": bool,
                "answer": str,
                "sources": list[dict],
                "message": str,
            }
        """
        if not settings.openai_api_key:
            return {
                "success": False,
                "answer": "AI service is not configured. Please set OPENAI_API_KEY.",
                "sources": [],
                "message": "OpenAI API key missing.",
            }

        client = AsyncOpenAI(api_key=settings.openai_api_key)

        try:
            # Step 1: embed the query
            embed_response = await client.embeddings.create(
                model=settings.openai_embedding_model,
                input=question,
            )
            query_vector = embed_response.data[0].embedding

            # Step 2: cosine similarity search against our custom table
            async with AsyncSession(engine) as session:
                rows = await session.execute(
                    text(
                        """
                        SELECT kb_id, topic, content,
                               1 - (embedding <=> CAST(:qv AS vector)) AS similarity
                        FROM knowledge_base_embeddings
                        ORDER BY embedding <=> CAST(:qv AS vector)
                        LIMIT 5
                        """
                    ),
                    {"qv": str(query_vector)},
                )
                docs = rows.fetchall()

            if not docs:
                return {
                    "success": False,
                    "answer": "No knowledge base entries found. Please run /admin/embed first.",
                    "sources": [],
                    "message": "knowledge_base_embeddings table is empty.",
                }

            # Step 3: build context string
            context = "\n\n".join(f"[{row.topic}]\n{row.content}" for row in docs)

            sources = [
                {
                    "kb_id": row.kb_id,
                    "topic": row.topic,
                    "content": row.content[:200],
                    "similarity": round(float(row.similarity), 4),
                }
                for row in docs
            ]

            # Step 4: call LLM with retrieved context
            chat_response = await client.chat.completions.create(
                model=settings.openai_model,
                temperature=0.1,
                messages=[
                    {
                        "role": "system",
                        "content": SYSTEM_PROMPT.format(context=context),
                    },
                    {"role": "user", "content": question},
                ],
            )
            answer = chat_response.choices[0].message.content

            logger.info("RAG answered '%s' using %d sources", question[:60], len(docs))

            return {
                "success": True,
                "answer": answer,
                "sources": sources,
                "message": f"Answer generated from {len(sources)} knowledge base source(s).",
            }

        except Exception as exc:
            logger.exception("RAG pipeline error: %s", exc)
            return {
                "success": False,
                "answer": f"Error generating answer: {exc}",
                "sources": [],
                "message": str(exc),
            }


# Module-level singleton
_pipeline: FAQPipeline | None = None


def get_faq_pipeline() -> FAQPipeline:
    global _pipeline
    if _pipeline is None:
        _pipeline = FAQPipeline()
    return _pipeline
