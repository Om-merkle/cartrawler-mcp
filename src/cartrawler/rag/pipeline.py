"""
RAG Pipeline for FAQ / Knowledge Base
=======================================
Architecture:
  User Query
    → Embedding (text-embedding-3-small)
    → pgvector cosine similarity search against knowledge_base_embeddings
    → Top-K chunks retrieved
    → LLM (GPT-4o-mini) generates grounded answer
    → Response returned to MCP caller

Uses LangChain 1.x LCEL (LangChain Expression Language) — no langchain.chains.
"""
from __future__ import annotations

from langchain_core.output_parsers import StrOutputParser
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.runnables import RunnablePassthrough
from langchain_openai import ChatOpenAI, OpenAIEmbeddings
from langchain_postgres import PGVector

from cartrawler.config import settings

# ─────────────────────────────────────────────────────────────────────────────
# Prompt template
# ─────────────────────────────────────────────────────────────────────────────

SYSTEM_PROMPT = """You are a helpful travel assistant for CarTrawler — an Indian flight and car rental booking platform.

Answer the user's question using ONLY the provided context from the knowledge base.
If the context does not contain a clear answer, politely say you don't have that information
and suggest the user contacts support or checks the website.

Context:
{context}

Rules:
- Be concise (2-4 sentences max unless a list is needed).
- Use INR (₹) for any currency figures.
- Do not make up information not present in the context.
- Always mention relevant policies or tips when applicable.
"""

HUMAN_PROMPT = "{input}"


def _to_psycopg_url(url: str) -> str:
    """Convert postgresql:// or postgresql+asyncpg:// to postgresql+psycopg:// for langchain_postgres."""
    for prefix in ("postgresql+asyncpg://", "postgresql+psycopg2://"):
        if url.startswith(prefix):
            return "postgresql+psycopg://" + url[len(prefix):]
    if url.startswith("postgresql://"):
        return "postgresql+psycopg://" + url[len("postgresql://"):]
    return url


def _format_docs(docs: list) -> str:
    return "\n\n".join(doc.page_content for doc in docs)


# ─────────────────────────────────────────────────────────────────────────────
# FAQ Pipeline class
# ─────────────────────────────────────────────────────────────────────────────

class FAQPipeline:
    """
    LangChain 1.x RAG pipeline backed by pgvector (Supabase).

    Usage:
        pipeline = FAQPipeline()
        answer = await pipeline.ask("How do I cancel my flight?")
    """

    def __init__(self) -> None:
        self._retriever = None
        self._llm_chain = None

    def _build(self) -> None:
        """Lazily build the RAG chain (expensive, done once)."""
        embeddings = OpenAIEmbeddings(
            model=settings.openai_embedding_model,
            openai_api_key=settings.openai_api_key,
        )

        vector_store = PGVector(
            embeddings=embeddings,
            collection_name=settings.vector_store_table,
            connection=_to_psycopg_url(settings.database_url_sync),
            use_jsonb=True,
        )

        self._retriever = vector_store.as_retriever(
            search_type="similarity",
            search_kwargs={"k": 5},
        )

        llm = ChatOpenAI(
            model=settings.openai_model,
            temperature=0.1,
            openai_api_key=settings.openai_api_key,
        )

        prompt = ChatPromptTemplate.from_messages(
            [("system", SYSTEM_PROMPT), ("human", HUMAN_PROMPT)]
        )

        # LCEL chain: prompt | llm | output parser
        self._llm_chain = prompt | llm | StrOutputParser()

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

        if self._retriever is None:
            self._build()

        try:
            import asyncio
            loop = asyncio.get_event_loop()

            # Step 1: retrieve relevant docs
            docs = await loop.run_in_executor(
                None, lambda: self._retriever.invoke(question)
            )

            # Step 2: generate answer with context
            context = _format_docs(docs)
            answer = await loop.run_in_executor(
                None,
                lambda: self._llm_chain.invoke({"input": question, "context": context}),
            )

            sources = [
                {
                    "content": doc.page_content,
                    "topic": doc.metadata.get("topic", "general"),
                    "kb_id": doc.metadata.get("kb_id", ""),
                }
                for doc in docs
            ]

            return {
                "success": True,
                "answer": answer,
                "sources": sources,
                "message": f"Answer generated from {len(sources)} knowledge base source(s).",
            }

        except Exception as exc:  # noqa: BLE001
            return {
                "success": False,
                "answer": f"Error generating answer: {exc}",
                "sources": [],
                "message": str(exc),
            }


# Module-level singleton (instantiated lazily)
_pipeline: FAQPipeline | None = None


def get_faq_pipeline() -> FAQPipeline:
    global _pipeline
    if _pipeline is None:
        _pipeline = FAQPipeline()
    return _pipeline
