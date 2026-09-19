"""
src/retrieval/hybrid_search.py — Hybrid BM25 + kNN Search with Reciprocal Rank Fusion (RRF).

Strictly adheres to SPEC.md section #6:
- Per variant, runs ES hybrid query: BM25 on text + kNN on embedding, top 20 each.
- Fuses ALL variant result lists using Reciprocal Rank Fusion (k=60).
- Supports metadata filters: financial_year, doc_type, min_authority_level.
- Returns top candidates (default 30) sorted by RRF score for downstream reranking.
"""

import logging
from typing import List, Dict, Any, Optional
from collections import defaultdict

from elasticsearch import Elasticsearch
from sentence_transformers import SentenceTransformer

from src.config import settings
from src.retrieval.query_expander import QueryExpander

logger = logging.getLogger("LexIndiaHybridSearch")


class HybridSearcher:
    def __init__(
        self,
        es_client: Optional[Elasticsearch] = None,
        embedding_model: Optional[SentenceTransformer] = None,
        query_expander: Optional[QueryExpander] = None,
        index_name: str = settings.ES_INDEX,
        rrf_k: int = 60
    ):
        self.es = es_client or Elasticsearch(settings.ES_URL, request_timeout=30)
        self.embedding_model = embedding_model or SentenceTransformer(settings.EMBEDDING_MODEL_NAME)
        self.query_expander = query_expander or QueryExpander()
        self.index_name = index_name
        self.rrf_k = rrf_k

    def _build_filters(
        self,
        financial_year: Optional[str] = None,
        doc_type: Optional[str] = None,
        min_authority_level: Optional[int] = None
    ) -> List[Dict[str, Any]]:
        """Construct Elasticsearch filter clauses for metadata constraints."""
        filters = []

        if doc_type:
            filters.append({"term": {"doc_type": doc_type}})

        if min_authority_level is not None:
            filters.append({"range": {"authority_level": {"lte": min_authority_level}}})

        if financial_year:
            # Match documents valid for the requested financial year, or perpetual/current documents
            filters.append({
                "bool": {
                    "should": [
                        {"term": {"fy_valid_from": financial_year}},
                        {"term": {"fy_valid_to": financial_year}},
                        {"term": {"fy_valid_to": "current"}},
                        {"term": {"fy_valid_from": "1962-63"}}
                    ],
                    "minimum_should_match": 1
                }
            })

        return filters

    def search_single_variant(
        self,
        variant_text: str,
        filters: List[Dict[str, Any]],
        top_n: int = 20
    ) -> List[Dict[str, Any]]:
        """Execute ES hybrid query (BM25 + kNN) for a single query variant."""
        # Generate 768-dim normalized embedding
        query_vec = self.embedding_model.encode(variant_text, normalize_embeddings=True).tolist()

        # Statutory citation boosting: detect Section \d+ and inject BM25 must clause
        import re
        sections = re.findall(r'Section\s+[0-9]+[A-Za-z]*(?:\([0-9A-Za-z]+\))*', variant_text, re.IGNORECASE)

        must_clauses: List[Dict[str, Any]] = [
            {"match": {"text": {"query": variant_text, "boost": 1.0}}}
        ]
        for sec in sections:
            must_clauses.append({
                "bool": {
                    "should": [
                        {"match_phrase": {"section_id": {"query": sec, "boost": 3.0}}},
                        {"match_phrase": {"text": {"query": sec, "boost": 2.0}}}
                    ],
                    "minimum_should_match": 1
                }
            })

        body: Dict[str, Any] = {
            "size": top_n,
            "query": {
                "bool": {
                    "must": must_clauses
                }
            },
            "knn": {
                "field": "embedding",
                "query_vector": query_vec,
                "k": top_n,
                "num_candidates": max(top_n * 3, 60),
                "boost": 1.0
            }
        }

        if filters:
            body["query"]["bool"]["filter"] = filters
            body["knn"]["filter"] = filters

        res = self.es.search(index=self.index_name, body=body)
        hits = res.get("hits", {}).get("hits", [])
        return hits

    def search(
        self,
        query: str,
        financial_year: Optional[str] = None,
        doc_type: Optional[str] = None,
        min_authority_level: Optional[int] = None,
        top_k: int = 30
    ) -> List[Dict[str, Any]]:
        """
        Execute full multi-variant hybrid search with Reciprocal Rank Fusion (RRF).
        
        1. Generates 3 query variants via QueryExpander.
        2. Executes hybrid search for query and each variant (top 20 each).
        3. Fuses all ranked lists using RRF with k=60.
        4. Returns top_k deduplicated candidates sorted by RRF score.
        """
        query_variants = self.query_expander.expand(query)
        all_variants = [query] + [v for v in query_variants if v and v != query]
        return self.search_with_variants(
            query=query,
            variants=all_variants,
            financial_year=financial_year,
            doc_type=doc_type,
            min_authority_level=min_authority_level,
            top_k=top_k
        )

    def search_with_variants(
        self,
        query: str,
        variants: List[str],
        financial_year: Optional[str] = None,
        doc_type: Optional[str] = None,
        min_authority_level: Optional[int] = None,
        top_k: int = 30
    ) -> List[Dict[str, Any]]:
        """Execute hybrid search given pre-computed query variants."""
        all_variants = list(variants) if variants else [query]
        if query not in all_variants:
            all_variants = [query] + all_variants

        filters = self._build_filters(
            financial_year=financial_year,
            doc_type=doc_type,
            min_authority_level=min_authority_level
        )

        variant_hits: List[List[Dict[str, Any]]] = []
        for v in all_variants:
            hits = self.search_single_variant(v, filters, top_n=20)
            variant_hits.append(hits)

        # Reciprocal Rank Fusion (RRF k=60)
        doc_scores = defaultdict(float)
        doc_map = {}
        variant_rank_history = defaultdict(list)

        for v_idx, hits in enumerate(variant_hits):
            for rank_0, hit in enumerate(hits):
                rank = rank_0 + 1  # 1-indexed rank
                doc_id = hit["_id"]
                rrf_increment = 1.0 / (self.rrf_k + rank)
                doc_scores[doc_id] += rrf_increment
                variant_rank_history[doc_id].append({"variant_idx": v_idx, "rank": rank})
                if doc_id not in doc_map:
                    doc_map[doc_id] = hit["_source"]

        # Sort all candidate chunks by fused RRF score descending
        sorted_doc_ids = sorted(doc_scores.keys(), key=lambda did: doc_scores[did], reverse=True)

        results = []
        for did in sorted_doc_ids[:top_k]:
            item = dict(doc_map[did])
            item["rrf_score"] = doc_scores[did]
            item["variant_matches"] = len(variant_rank_history[did])
            results.append(item)

        logger.info(
            f"Hybrid search fused {len(all_variants)} variants into {len(results)} candidate chunks for: '{query}'"
        )
        return results
