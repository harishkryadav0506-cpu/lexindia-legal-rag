"""
tests/test_phase5.py — Test suite for LexIndia Phase 5 Retrieval Pipeline.

Verifies SPEC.md section #6 and section #15 (Phase 5):
- query_expander.py produces exactly 3 variants (legal, layman, Hinglish/boosted).
- hybrid_search.py executes BM25 + kNN per variant, fuses with RRF (k=60), and filters correctly.
- reranker.py computes neural cross-encoder scores and applies statutory authority weighting.
- citation_graph.py builds NetworkX DiGraph and executes 2-hop expansion (+4 chunks).
"""

import pytest
from src.retrieval import QueryExpander, HybridSearcher, Reranker, CitationGraph, AUTHORITY_WEIGHTS


@pytest.fixture(scope="module")
def query_expander():
    return QueryExpander()


@pytest.fixture(scope="module")
def hybrid_searcher(query_expander):
    return HybridSearcher(query_expander=query_expander)


@pytest.fixture(scope="module")
def reranker():
    return Reranker()


@pytest.fixture(scope="module")
def citation_graph():
    return CitationGraph()


def test_query_expander_produces_3_variants(query_expander):
    query = "Can I claim both HRA and home loan interest deduction?"
    variants = query_expander.expand(query)
    assert isinstance(variants, list), "Expected list of variants"
    assert len(variants) == 3, f"Expected exactly 3 variants, got {len(variants)}"
    for idx, v in enumerate(variants):
        assert isinstance(v, str) and len(v.strip()) > 0, f"Variant {idx+1} is empty"


def test_query_expander_hinglish_handling(query_expander):
    hinglish_query = "kya main apne rent ka deduction le sakta hu?"
    variants = query_expander._rule_based_fallback(hinglish_query)
    assert len(variants) == 3
    # Check that variant 3 or variant 1 translated or reformulated
    assert any("rent" in v.lower() or "hra" in v.lower() or "10(13a)" in v.lower() for v in variants)


def test_hybrid_search_rrf_fusion(hybrid_searcher):
    query = "deduction under section 80C maximum limit"
    candidates = hybrid_searcher.search(query, top_k=15)
    assert len(candidates) > 0, "No candidates returned by hybrid search"
    assert len(candidates) <= 15

    # Check RRF scores are positive and descending
    scores = [c["rrf_score"] for c in candidates]
    assert all(s > 0 for s in scores), "RRF scores must be positive"
    assert scores == sorted(scores, reverse=True), "Candidates must be sorted descending by RRF score"

    # Verify chunk structure
    top_c = candidates[0]
    assert "chunk_id" in top_c
    assert "text" in top_c
    assert "section_id" in top_c
    assert "authority_level" in top_c


def test_hybrid_search_metadata_filter(hybrid_searcher):
    query = "audit of accounts and turnover requirements"
    candidates = hybrid_searcher.search(query, doc_type="rules", top_k=10)
    assert len(candidates) > 0, "No candidates returned for rules filter"
    for c in candidates:
        assert c["doc_type"] == "rules", f"Expected doc_type='rules', got {c['doc_type']}"


def test_reranker_and_authority_weighting(reranker, hybrid_searcher):
    query = "Section 44AB tax audit turnover threshold"
    candidates = hybrid_searcher.search(query, top_k=10)
    assert len(candidates) > 0

    top_results = reranker.rerank(query, candidates, top_n=5)
    assert len(top_results) <= 5

    for c in top_results:
        assert "rerank_score" in c
        assert "authority_weight" in c
        assert "final_score" in c
        auth_level = c.get("authority_level", 4)
        expected_weight = AUTHORITY_WEIGHTS.get(auth_level, 0.60)
        assert c["authority_weight"] == pytest.approx(expected_weight)
        assert c["final_score"] == pytest.approx(c["rerank_score"] * expected_weight)
        assert c["graph_expanded"] is False

    # Check descending order
    final_scores = [c["final_score"] for c in top_results]
    assert final_scores == sorted(final_scores, reverse=True)


def test_citation_graph_structure(citation_graph):
    g = citation_graph.graph
    assert g.number_of_nodes() > 100, f"Expected > 100 nodes, got {g.number_of_nodes()}"
    assert g.number_of_edges() > 200, f"Expected > 200 edges, got {g.number_of_edges()}"


def test_citation_graph_2hop_expansion(citation_graph, reranker, hybrid_searcher):
    query = "HRA exemption calculation under Section 10(13A)"
    candidates = hybrid_searcher.search(query, top_k=10)
    top_chunks = reranker.rerank(query, candidates, top_n=6)

    expanded = citation_graph.expand_chunks(top_chunks, max_expansion=4)
    base_count = sum(1 for c in expanded if not c["graph_expanded"])
    graph_count = sum(1 for c in expanded if c["graph_expanded"])

    assert base_count == len(top_chunks), "Base chunks count preserved"
    assert graph_count <= 4, f"Expansion should not exceed 4, got {graph_count}"
    assert len(expanded) == base_count + graph_count


def test_citation_graph_subgraph_extraction(citation_graph):
    sub = citation_graph.get_subgraph("Section 80C", hops=2)
    assert "nodes" in sub
    assert "edges" in sub
    assert isinstance(sub["nodes"], list)
    assert isinstance(sub["edges"], list)
    assert len(sub["nodes"]) > 0, "Subgraph for Section 80C should contain nodes"
