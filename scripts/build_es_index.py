"""
scripts/build_es_index.py — Build Elasticsearch 8.13 Index with Dense Vector Embeddings.

Strictly adheres to SPEC.md section #5 and section #15 (Phase 4):
- Connects to ES 8.13 service (single-node, security disabled for dev).
- Creates index `lexindia_corpus` with:
  * text: english analyzer
  * embedding: dense_vector dims=768, cosine similarity
  * keyword/int metadata: section_id, doc_type, authority_level, fy_valid_from, fy_valid_to, page_number, source_url
- Embeds all chunks from data/processed/chunks.jsonl using BAAI/bge-base-en-v1.5 locally in batches of 64.
- Verifies document count matches chunks.jsonl.
- Runs and prints 3 sanity queries (BM25 lexical, kNN dense vector, and hybrid filtered).
"""

import os
import json
import logging
import time
from pathlib import Path
from typing import List, Dict, Any

from elasticsearch import Elasticsearch, helpers
from sentence_transformers import SentenceTransformer

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("LexIndiaESIndexer")

import argparse

INDEX_NAME = os.getenv("ES_INDEX", "lexindia-v2")
ES_HOST = os.getenv("ELASTICSEARCH_URL", "http://localhost:9200")
EMBEDDING_MODEL_NAME = "BAAI/bge-base-en-v1.5"
CHUNKS_PATH = Path("data/processed/chunks.jsonl")
BATCH_SIZE = 64

INDEX_MAPPING = {
    "settings": {
        "number_of_shards": 1,
        "number_of_replicas": 0,
        "analysis": {
            "analyzer": {
                "default": {
                    "type": "english"
                }
            }
        }
    },
    "mappings": {
        "properties": {
            "chunk_id": {"type": "keyword"},
            "doc_id": {"type": "keyword"},
            "act_name": {"type": "text"},
            "text": {
                "type": "text",
                "analyzer": "english"
            },
            "section_id": {"type": "keyword"},
            "chapter": {"type": "keyword"},
            "doc_type": {"type": "keyword"},
            "authority_level": {"type": "integer"},
            "fy_valid_from": {"type": "keyword"},
            "fy_valid_to": {"type": "keyword"},
            "page_number": {"type": "integer"},
            "source_url": {"type": "keyword"},
            "citations": {"type": "keyword"},
            "cross_references": {
                "type": "object",
                "properties": {
                    "target": {"type": "keyword"},
                    "relation": {"type": "keyword"}
                }
            },
            "embedding": {
                "type": "dense_vector",
                "dims": 768,
                "index": True,
                "similarity": "cosine"
            }
        }
    }
}


def get_es_client() -> Elasticsearch:
    """Initialize Elasticsearch client."""
    client = Elasticsearch(ES_HOST, request_timeout=60)
    if not client.ping():
        raise ConnectionError(f"Cannot connect to Elasticsearch cluster at {ES_HOST}")
    return client


def recreate_index(client: Elasticsearch, index_name: str = INDEX_NAME):
    """Delete and create the versioned index with the required schema."""
    if client.indices.exists(index=index_name):
        logger.info(f"Index {index_name} exists. Deleting...")
        client.indices.delete(index=index_name)
    
    logger.info(f"Creating index {index_name} with 768-dim dense_vector mapping and english analyzer...")
    client.indices.create(index=index_name, body=INDEX_MAPPING)
    logger.info(f"Index {index_name} created successfully.")


def load_chunks(chunks_path: Path = CHUNKS_PATH) -> List[Dict[str, Any]]:
    """Load chunks from jsonl."""
    if not chunks_path.exists():
        raise FileNotFoundError(f"Chunks file not found at {chunks_path}")
    
    chunks = []
    with open(chunks_path, "r", encoding="utf-8") as f:
        for line in f:
            if line.strip():
                chunks.append(json.loads(line))
    logger.info(f"Loaded {len(chunks)} chunks from {chunks_path}")
    return chunks


def build_index(index_name: str = INDEX_NAME, chunks_path: Path = CHUNKS_PATH):
    """Embed all chunks and index them into Elasticsearch."""
    es = get_es_client()
    recreate_index(es, index_name=index_name)

    chunks = load_chunks(chunks_path)
    total_chunks = len(chunks)

    logger.info(f"Loading embedding model: {EMBEDDING_MODEL_NAME}...")
    model = SentenceTransformer(EMBEDDING_MODEL_NAME)

    logger.info(f"Starting embedding & indexing of {total_chunks} chunks into {index_name} (batch_size={BATCH_SIZE})...")
    t0 = time.time()
    indexed_count = 0

    for i in range(0, total_chunks, BATCH_SIZE):
        batch = chunks[i : i + BATCH_SIZE]
        texts = [c["text"] for c in batch]

        # Generate 768-dim normalized embeddings
        embeddings = model.encode(texts, batch_size=BATCH_SIZE, normalize_embeddings=True, show_progress_bar=False)

        actions = []
        for chunk, emb in zip(batch, embeddings):
            doc = {**chunk, "embedding": emb.tolist()}
            actions.append({
                "_index": index_name,
                "_id": chunk["chunk_id"],
                "_source": doc
            })

        success, failed = helpers.bulk(es, actions, refresh=False)
        indexed_count += success
        
        if (i // BATCH_SIZE) % 5 == 0 or (i + BATCH_SIZE >= total_chunks):
            elapsed = time.time() - t0
            rate = indexed_count / elapsed if elapsed > 0 else 0
            logger.info(f"Indexed [{indexed_count}/{total_chunks}] chunks ({rate:.1f} chunks/sec)")

    # Force refresh index
    es.indices.refresh(index=index_name)
    elapsed_total = time.time() - t0
    logger.info(f"Indexing completed in {elapsed_total:.2f}s! Total docs indexed: {indexed_count}")

    # Verify doc count
    count_res = es.count(index=index_name)
    actual_count = count_res["count"]
    logger.info(f"ES verified document count in {index_name}: {actual_count}")
    assert actual_count == total_chunks, f"Mismatch: expected {total_chunks}, found {actual_count}"

    return es, model


def run_sanity_queries(es: Elasticsearch, model: SentenceTransformer, index_name: str = INDEX_NAME):
    """Execute and print 3 distinct sanity queries per SPEC requirement."""
    print("\n" + "=" * 80)
    print(f"RUNNING 3 SANITY SEARCHES ON ELASTICSEARCH 8.13 ({index_name})")
    print("=" * 80)

    # Sanity Query 1: BM25 Lexical search on Section 80C
    q1_text = "deduction under section 80C maximum limit and eligible investments"
    print(f"\n[SANITY QUERY 1 - BM25 Lexical Search]")
    print(f"Query: \"{q1_text}\"")
    res1 = es.search(
        index=index_name,
        body={
            "query": {
                "match": {
                    "text": q1_text
                }
            },
            "size": 3
        }
    )
    for rank, hit in enumerate(res1["hits"]["hits"], 1):
        src = hit["_source"]
        print(f"  Rank #{rank} [Score: {hit['_score']:.4f}] Section: {src['section_id']} | DocType: {src['doc_type']} | Page: {src['page_number']}")
        print(f"    Chunk ID: {src['chunk_id']}")
        print(f"    Snippet: {src['text'][:140]}...\n")

    # Sanity Query 2: kNN Dense Vector Search on HRA under Rule 2A / Section 10(13A)
    q2_text = "house rent allowance exemption calculation formula under Rule 2A"
    print(f"[SANITY QUERY 2 - kNN Dense Vector Search (Cosine Similarity)]")
    print(f"Query: \"{q2_text}\"")
    q2_emb = model.encode(q2_text, normalize_embeddings=True).tolist()
    res2 = es.search(
        index=index_name,
        body={
            "knn": {
                "field": "embedding",
                "query_vector": q2_emb,
                "k": 3,
                "num_candidates": 50
            },
            "size": 3
        }
    )
    for rank, hit in enumerate(res2["hits"]["hits"], 1):
        src = hit["_source"]
        print(f"  Rank #{rank} [Score: {hit['_score']:.4f}] Section: {src['section_id']} | DocType: {src['doc_type']} | Page: {src['page_number']}")
        print(f"    Chunk ID: {src['chunk_id']}")
        print(f"    Snippet: {src['text'][:140]}...\n")

    # Sanity Query 3: Filtered Hybrid Search (Section 44AB + authority_level <= 2)
    q3_text = "tax audit turnover limit under section 44AB for businesses and professions"
    print(f"[SANITY QUERY 3 - Filtered Hybrid Search (Authority <= 2)]")
    print(f"Query: \"{q3_text}\"")
    q3_emb = model.encode(q3_text, normalize_embeddings=True).tolist()
    res3 = es.search(
        index=index_name,
        body={
            "query": {
                "match": {
                    "text": q3_text
                }
            },
            "knn": {
                "field": "embedding",
                "query_vector": q3_emb,
                "k": 3,
                "num_candidates": 50,
                "filter": [
                    {"range": {"authority_level": {"lte": 2}}}
                ]
            },
            "size": 3
        }
    )
    for rank, hit in enumerate(res3["hits"]["hits"], 1):
        src = hit["_source"]
        print(f"  Rank #{rank} [Score: {hit['_score']:.4f}] Section: {src['section_id']} | Authority: {src['authority_level']} | Doc: {src['doc_id']}")
        print(f"    Chunk ID: {src['chunk_id']}")
        print(f"    Snippet: {src['text'][:140]}...\n")

    print("=" * 80)
    print("ALL 3 SANITY SEARCHES COMPLETED SUCCESSFULLY!")
    print("=" * 80)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Build versioned Elasticsearch index for LexIndia")
    parser.add_argument("--index-name", default=os.getenv("ES_INDEX", "lexindia-v2"), help="Target ES index name")
    parser.add_argument("--chunks-path", default="data/processed/chunks.jsonl", help="Path to chunks jsonl")
    args = parser.parse_args()

    es_client, emb_model = build_index(index_name=args.index_name, chunks_path=Path(args.chunks_path))
    run_sanity_queries(es_client, emb_model, index_name=args.index_name)
