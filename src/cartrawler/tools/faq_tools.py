"""
MCP FAQ Tool
=============
No authentication required.
Uses the RAG pipeline (pgvector + GPT-4o-mini) to answer
questions about flights, car rentals, refunds, loyalty, etc.
"""
from __future__ import annotations

from cartrawler.rag.pipeline import get_faq_pipeline


async def answer_faq(question: str) -> dict:
    """
    Answer a frequently asked question about CarTrawler services.

    No login required. Covers topics:
    - Flight booking & check-in rules
    - Car rental policies (age, deposit, fuel, insurance)
    - Refund & cancellation policies
    - Loyalty program tiers and points
    - Available offers and coupons
    - Airport information
    - Payment methods
    - Travel tips

    Args:
        question: The user's question in natural language
    """
    if not question or not question.strip():
        return {
            "success": False,
            "answer": "Please provide a question.",
            "sources": [],
        }

    pipeline = get_faq_pipeline()
    return await pipeline.ask(question.strip())
