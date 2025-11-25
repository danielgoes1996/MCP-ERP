"""
Retrieval services for Phase 2B (candidate selection).

Available services:
- LLM-based retrieval (Solution A): Fast implementation, high accuracy, ~$0.001/invoice
- Enriched embeddings (Solution B): Scalable, architectural best practice, free after setup
"""

from .llm_retrieval_service import (
    LLMRetrievalService,
    retrieve_candidates_with_llm
)

__all__ = [
    'LLMRetrievalService',
    'retrieve_candidates_with_llm'
]
