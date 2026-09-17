#!/usr/bin/env bash
# =====================================================================
# LexIndia — Elasticsearch Index Initialization Script
# Checks cluster health and builds lexindia_corpus index if not present.
# =====================================================================

set -e

ES_URL="${ES_URL:-http://localhost:9200}"
ES_INDEX="${ES_INDEX:-lexindia_corpus}"
MAX_RETRIES=30
RETRY_INTERVAL=2

echo "[es_init] Checking Elasticsearch connection at ${ES_URL}..."

retry_count=0
until curl -s "${ES_URL}/_cluster/health" > /dev/null 2>&1; do
    retry_count=$((retry_count + 1))
    if [ $retry_count -ge $MAX_RETRIES ]; then
        echo "[es_init] ERROR: Elasticsearch did not become ready after ${MAX_RETRIES} attempts. Exiting."
        exit 1
    fi
    echo "[es_init] Waiting for Elasticsearch (${retry_count}/${MAX_RETRIES})..."
    sleep $RETRY_INTERVAL
done

echo "[es_init] Elasticsearch is online and healthy."

# Check if index exists
STATUS_CODE=$(curl -s -o /dev/null -w "%{http_code}" "${ES_URL}/${ES_INDEX}")

if [ "$STATUS_CODE" -eq 200 ]; then
    DOC_COUNT=$(curl -s "${ES_URL}/${ES_INDEX}/_count" | grep -o '"count":[0-9]*' | cut -d':' -f2)
    echo "[es_init] Index '${ES_INDEX}' already exists with ${DOC_COUNT} documents. Skipping build."
else
    echo "[es_init] Index '${ES_INDEX}' not found (HTTP ${STATUS_CODE}). Building index from chunks.jsonl..."
    if [ -f "data/processed/chunks.jsonl" ]; then
        python scripts/build_es_index.py
        echo "[es_init] Index build complete."
    else
        echo "[es_init] WARNING: data/processed/chunks.jsonl not found. Run scripts/chunk_documents.py first."
    fi
fi

echo "[es_init] Initialization finished successfully."
