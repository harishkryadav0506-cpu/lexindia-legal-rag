"""
src/retrieval/citation_graph.py — Citation & Cross-Reference NetworkX Knowledge Graph.

Strictly adheres to SPEC.md section #6:
- Builds NetworkX DiGraph from data/processed/chunks.jsonl cross-references and amendment edges.
- Typed edges: READ_WITH, SUBJECT_TO, AMENDED_BY, EXPLAINS.
- 2-hop expansion: for top-8 chunks, pulls neighbor sections via {READ_WITH, SUBJECT_TO, AMENDED_BY},
  appending up to +4 neighbor chunks flagged with graph_expanded=true.
- Exposes get_subgraph(section_id, hops) for /graph API visualization and MCP tools.
"""

import json
import logging
from pathlib import Path
from typing import List, Dict, Any, Set, Tuple, Optional

import networkx as nx

from src.config import settings

logger = logging.getLogger("LexIndiaCitationGraph")

DEFAULT_CHUNKS_PATH = settings.PROCESSED_DATA_DIR / "chunks.jsonl"
EXPANSION_RELATIONS = {"READ_WITH", "SUBJECT_TO", "AMENDED_BY"}


class CitationGraph:
    def __init__(self, chunks_path: Path = DEFAULT_CHUNKS_PATH):
        self.chunks_path = Path(chunks_path)
        self.graph = nx.DiGraph()
        self.section_to_chunks: Dict[str, List[Dict[str, Any]]] = {}
        self.chunk_id_to_chunk: Dict[str, Dict[str, Any]] = {}
        self._build_graph()

    def _build_graph(self):
        """Construct NetworkX DiGraph from chunks.jsonl."""
        if not self.chunks_path.exists():
            logger.warning(f"Chunks file not found at {self.chunks_path}, graph will be empty.")
            return

        logger.info(f"Building Citation Graph from {self.chunks_path}...")
        total_edges = 0

        with open(self.chunks_path, "r", encoding="utf-8") as f:
            for line in f:
                if not line.strip():
                    continue
                c = json.loads(line)
                cid = c["chunk_id"]
                sec = c["section_id"]
                self.chunk_id_to_chunk[cid] = c
                self.section_to_chunks.setdefault(sec, []).append(c)

                # Add or update node
                if not self.graph.has_node(sec):
                    self.graph.add_node(
                        sec,
                        section_id=sec,
                        doc_type=c.get("doc_type", "statute"),
                        authority_level=c.get("authority_level", 1),
                        act_name=c.get("act_name", ""),
                    )

                # Add cross-reference edges
                for xr in c.get("cross_references", []):
                    target = xr.get("target")
                    relation = xr.get("relation")
                    if target and relation:
                        if not self.graph.has_node(target):
                            self.graph.add_node(target, section_id=target, authority_level=2)
                        self.graph.add_edge(
                            sec,
                            target,
                            relation=relation,
                            source_chunk_id=cid,
                            source_doc=c.get("doc_id", "")
                        )
                        total_edges += 1

        logger.info(
            f"Citation Graph built: {self.graph.number_of_nodes()} nodes, "
            f"{self.graph.number_of_edges()} edges across {len(self.chunk_id_to_chunk)} chunks"
        )

    def expand_chunks(
        self,
        top_chunks: List[Dict[str, Any]],
        max_expansion: int = 4
    ) -> List[Dict[str, Any]]:
        """
        2-hop graph expansion:
        For top-8 chunks, traverse neighbors via {READ_WITH, SUBJECT_TO, AMENDED_BY}.
        Append up to max_expansion (+4) neighbor chunks with graph_expanded=True.
        """
        if not top_chunks:
            return []

        # Ensure base retrieved chunks are flagged graph_expanded=False
        result_chunks = []
        visited_chunk_ids: Set[str] = set()
        seed_sections: Set[str] = set()

        for c in top_chunks:
            c_copy = dict(c)
            c_copy["graph_expanded"] = False
            result_chunks.append(c_copy)
            visited_chunk_ids.add(c_copy["chunk_id"])
            if c_copy.get("section_id"):
                seed_sections.add(c_copy["section_id"])

        expanded_chunks: List[Dict[str, Any]] = []

        # 2-hop search across seed sections
        neighbor_sections: Set[str] = set()
        for seed in seed_sections:
            if not self.graph.has_node(seed):
                continue

            # Hop 1 neighbors
            hop1_nodes: Set[str] = set()
            # Outgoing edges
            for _, v, data in self.graph.out_edges(seed, data=True):
                if data.get("relation") in EXPANSION_RELATIONS:
                    hop1_nodes.add(v)
            # Incoming edges
            for u, _, data in self.graph.in_edges(seed, data=True):
                if data.get("relation") in EXPANSION_RELATIONS:
                    hop1_nodes.add(u)

            neighbor_sections.update(hop1_nodes)

            # Hop 2 neighbors
            for h1 in hop1_nodes:
                for _, v2, data in self.graph.out_edges(h1, data=True):
                    if data.get("relation") in EXPANSION_RELATIONS:
                        neighbor_sections.add(v2)
                for u2, _, data in self.graph.in_edges(h1, data=True):
                    if data.get("relation") in EXPANSION_RELATIONS:
                        neighbor_sections.add(u2)

        # Remove seed sections from candidates
        candidate_sections = neighbor_sections - seed_sections

        # If strict EXPANSION_RELATIONS didn't yield enough, allow EXPLAINS relations as fallback
        if len(candidate_sections) < max_expansion:
            for seed in seed_sections:
                if self.graph.has_node(seed):
                    for _, v, data in self.graph.out_edges(seed, data=True):
                        if v not in seed_sections:
                            candidate_sections.add(v)
                    for u, _, data in self.graph.in_edges(seed, data=True):
                        if u not in seed_sections:
                            candidate_sections.add(u)

        # Pull chunks from candidate neighbor sections
        for sec in candidate_sections:
            sec_chunks = self.section_to_chunks.get(sec, [])
            for sc in sec_chunks:
                cid = sc["chunk_id"]
                if cid not in visited_chunk_ids:
                    expanded_item = dict(sc)
                    expanded_item["graph_expanded"] = True
                    # Set default placeholder scores if not already present
                    if "final_score" not in expanded_item:
                        expanded_item["final_score"] = 0.50
                    expanded_chunks.append(expanded_item)
                    visited_chunk_ids.add(cid)
                    if len(expanded_chunks) >= max_expansion:
                        break
            if len(expanded_chunks) >= max_expansion:
                break

        logger.info(
            f"Graph 2-hop expansion added {len(expanded_chunks)} chunks (max allowed: {max_expansion})"
        )
        return result_chunks + expanded_chunks

    def get_subgraph(self, section_id: str, hops: int = 2) -> Dict[str, Any]:
        """
        Extract an ego subgraph centered at section_id up to `hops` distance.
        Returns a JSON-serializable dictionary with nodes and edges.
        """
        if not self.graph.has_node(section_id):
            # Try fuzzy search on section name
            matches = [n for n in self.graph.nodes if section_id.lower() in n.lower()]
            if matches:
                section_id = matches[0]
            else:
                return {"nodes": [], "edges": []}

        # Ego subgraph
        sub_nodes = {section_id}
        current_layer = {section_id}

        for _ in range(hops):
            next_layer = set()
            for node in current_layer:
                next_layer.update(self.graph.successors(node))
                next_layer.update(self.graph.predecessors(node))
            sub_nodes.update(next_layer)
            current_layer = next_layer

        sub_g = self.graph.subgraph(sub_nodes)

        nodes = []
        for n in sub_g.nodes():
            ndata = sub_g.nodes[n]
            nodes.append({
                "id": n,
                "label": n,
                "authority_level": ndata.get("authority_level", 2),
                "doc_type": ndata.get("doc_type", "statute"),
            })

        edges = []
        for u, v, data in sub_g.edges(data=True):
            edges.append({
                "source": u,
                "target": v,
                "relation": data.get("relation", "RELATES_TO"),
                "source_doc": data.get("source_doc", "")
            })

        return {"nodes": nodes, "edges": edges}
