"""
tests/test_phase4.py — Test suite for LexIndia Phase 4 Elasticsearch Index & Vector Search.

Verifies SPEC.md section #5 and section #15 (Phase 4):
- Index `lexindia_corpus` exists on ES 8.13.
- Mapping conforms to spec: text has english analyzer, embedding is dense_vector dims=768 cosine, keyword/int metadata.
- Document count exactly matches the chunks count (3,407).
- Sanity search 1: BM25 lexical search returns relevant results.
- Sanity search 2: kNN dense vector search returns high cosine similarity (> 0.70).
- Sanity search 3: Filtered hybrid search respects authority_level constraint.
"""

import os
import pytest
from elasticsearch import Elasticsearch
from sentence_transformers import SentenceTransformer

ES_URL = os.getenv("ELASTICSEARCH_URL", "http://localhost:9200")
INDEX_NAME = "lexindia_corpus"
EXPECTED_DOC_COUNT = 3407


@pytest.fixture(scope="module")
def es_client():
    client = Elasticsearch(ES_URL, request_timeout=30)
    assert client.ping(), f"Elasticsearch cluster unreachable at {ES_URL}"
    return client


@pytest.fixture(scope="module")
def embedding_model():
    return SentenceTransformer("BAAI/bge-base-en-v1.5")


def test_es_index_exists(es_client):
    assert es_client.indices.exists(index=INDEX_NAME), f"Index {INDEX_NAME} does not exist"


def test_es_index_mapping(es_client):
    mapping = es_client.indices.get_mapping(index=INDEX_NAME)
    props = mapping[INDEX_NAME]["mappings"]["properties"]

    # Verify text field and english analyzer
    assert "text" in props
    assert props["text"]["type"] == "text"
    assert props["text"].get("analyzer") == "english"

    # Verify dense_vector embedding mapping
    assert "embedding" in props
    emb = props["embedding"]
    assert emb["type"] == "dense_vector"
    assert emb["dims"] == 768
    assert emb["similarity"] == "cosine"

    # Verify metadata fields
    assert props["section_id"]["type"] == "keyword"
    assert props["doc_type"]["type"] == "keyword"
    assert props["authority_level"]["type"] == "integer"
    assert props["page_number"]["type"] == "integer"
    assert props["source_url"]["type"] == "keyword"


def test_es_document_count(es_client):
    count_res = es_client.count(index=INDEX_NAME)
    actual_count = count_res["count"]
    assert actual_count == EXPECTED_DOC_COUNT, f"Expected {EXPECTED_DOC_COUNT} docs, found {actual_count}"


def test_bm25_lexical_sanity_query(es_client):
    query_text = "deduction under section 80C maximum limit"
    res = es_client.search(
        index=INDEX_NAME,
        body={
            "query": {
                "match": {
                    "text": query_text
                }
            },
            "size": 5
        }
    )
    hits = res["hits"]["hits"]
    assert len(hits) > 0, "BM25 sanity search returned no hits"
    top_hit = hits[0]["_source"]
    assert "text" in top_hit
    assert any("80C" in h["_source"]["text"] or "80C" in h["_source"]["section_id"] for h in hits)


def test_knn_dense_vector_sanity_query(es_client, embedding_model):
    query_text = "house rent allowance exemption calculation formula under Rule 2A"
    query_vec = embedding_model.encode(query_text, normalize_embeddings=True).tolist()

    res = es_client.search(
        index=INDEX_NAME,
        body={
            "knn": {
                "field": "embedding",
                "query_vector": query_vec,
                "k": 5,
                "num_candidates": 50
            },
            "size": 5
        }
    )
    hits = res["hits"]["hits"]
    assert len(hits) > 0, "kNN dense vector search returned no hits"
    top_score = hits[0]["_score"]
    assert top_score >= 0.70, f"Expected cosine similarity >= 0.70, got {top_score}"


def test_filtered_hybrid_sanity_query(es_client, embedding_model):
    query_text = "tax audit of accounts requirements and turnover limits under section 44AB"
    query_vec = embedding_model.encode(query_text, normalize_embeddings=True).tolist()

    res = es_client.search(
        index=INDEX_NAME,
        body={
            "query": {
                "bool": {
                    "must": [
                        {"match": {"text": query_text}}
                    ],
                    "filter": [
                        {"range": {"authority_level": {"lte": 2}}}
                    ]
                }
            },
            "knn": {
                "field": "embedding",
                "query_vector": query_vec,
                "k": 5,
                "num_candidates": 50,
                "filter": [
                    {"range": {"authority_level": {"lte": 2}}}
                ]
            },
            "size": 5
        }
    )
    hits = res["hits"]["hits"]
    assert len(hits) > 0, "Filtered hybrid search returned no hits"
    for h in hits:
        assert h["_source"]["authority_level"] <= 2, f"Authority filter violated: {h['_source']['authority_level']}"
