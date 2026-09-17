"""
LexIndia Retrieval Pipeline Package.
Provides query expansion, multi-variant hybrid search with RRF,
cross-encoder reranking with authority weighting, and 2-hop citation graph traversal.
"""

from src.retrieval.query_expander import QueryExpander
from src.retrieval.hybrid_search import HybridSearcher
from src.retrieval.reranker import Reranker, AUTHORITY_WEIGHTS
from src.retrieval.citation_graph import CitationGraph

__all__ = [
    "QueryExpander",
    "HybridSearcher",
    "Reranker",
    "CitationGraph",
    "AUTHORITY_WEIGHTS",
]
