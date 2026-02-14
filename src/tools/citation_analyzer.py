"""
Citation analysis tool using Semantic Scholar API.

Provides functionality to fetch citation data and build citation networks.
"""

import os
from typing import List, Dict, Optional, Set
import httpx
from dotenv import load_dotenv

from src.utils.logger import setup_logger
from src.utils.retry import retry_with_backoff

load_dotenv()
logger = setup_logger(__name__)

SEMANTIC_SCHOLAR_API_BASE = "https://api.semanticscholar.org/graph/v1"
SEMANTIC_SCHOLAR_API_KEY = os.getenv("SEMANTIC_SCHOLAR_API_KEY")


def get_paper_citations(
    paper_id: str,
    max_references: int = 50,
    max_citations: int = 50,
) -> Dict:
    """
    Fetch citation data for a paper from Semantic Scholar.

    Args:
        paper_id: Semantic Scholar paper ID
        max_references: Maximum number of references to fetch
        max_citations: Maximum number of citations to fetch

    Returns:
        Dictionary with:
            - references: List of paper IDs cited by this paper
            - citations: List of paper IDs citing this paper
            - influential_citations: Count of influential citations
            - reference_count: Total number of references
            - citation_count: Total number of citations

    Example:
        >>> data = get_paper_citations("649def34f8be52c8b66281af98ae884c09aef38b")
        >>> print(f"Referenced {len(data['references'])} papers")
    """
    logger.debug(f"Fetching citations for paper: {paper_id}")

    # Build headers
    headers = {}
    if SEMANTIC_SCHOLAR_API_KEY:
        headers["x-api-key"] = SEMANTIC_SCHOLAR_API_KEY

    url = f"{SEMANTIC_SCHOLAR_API_BASE}/paper/{paper_id}"
    params = {
        "fields": "references,references.paperId,citations,citations.paperId,influentialCitationCount"
    }

    try:
        @retry_with_backoff(max_attempts=3)
        def _fetch():
            response = httpx.get(url, params=params, headers=headers, timeout=30.0)
            response.raise_for_status()
            return response.json()

        data = _fetch()

        # Extract reference IDs
        references = []
        if "references" in data and data["references"]:
            references = [
                ref["paperId"]
                for ref in data["references"][:max_references]
                if ref and "paperId" in ref and ref["paperId"]
            ]

        # Extract citation IDs
        citations = []
        if "citations" in data and data["citations"]:
            citations = [
                cit["paperId"]
                for cit in data["citations"][:max_citations]
                if cit and "paperId" in cit and cit["paperId"]
            ]

        result = {
            "paper_id": paper_id,
            "references": references,
            "citations": citations,
            "reference_count": len(references),
            "citation_count": len(citations),
            "influential_citations": data.get("influentialCitationCount", 0),
        }

        logger.debug(
            f"✓ Paper {paper_id}: {result['reference_count']} refs, "
            f"{result['citation_count']} cites"
        )
        return result

    except httpx.HTTPError as e:
        logger.warning(f"Failed to fetch citations for {paper_id}: {e}")
        # Return empty result instead of raising
        return {
            "paper_id": paper_id,
            "references": [],
            "citations": [],
            "reference_count": 0,
            "citation_count": 0,
            "influential_citations": 0,
        }


def build_citation_graph(
    paper_ids: List[str],
    max_references: int = 20,
    max_citations: int = 20,
) -> Dict:
    """
    Build a citation graph from a list of papers.

    Args:
        paper_ids: List of Semantic Scholar paper IDs
        max_references: Max references per paper
        max_citations: Max citations per paper

    Returns:
        Dictionary with:
            - nodes: List of paper IDs in the graph
            - edges: List of (source, target) citation edges
            - metadata: Paper-level metadata (citation counts, etc.)

    Example:
        >>> graph = build_citation_graph(["id1", "id2", "id3"])
        >>> print(f"Graph has {len(graph['nodes'])} nodes and {len(graph['edges'])} edges")
    """
    logger.info(f"Building citation graph for {len(paper_ids)} papers")

    # Track all papers in graph
    all_paper_ids: Set[str] = set(paper_ids)
    edges: List[tuple] = []
    metadata: Dict[str, Dict] = {}

    # Fetch citations for each paper
    for paper_id in paper_ids:
        citation_data = get_paper_citations(paper_id, max_references, max_citations)

        # Store metadata
        metadata[paper_id] = {
            "reference_count": citation_data["reference_count"],
            "citation_count": citation_data["citation_count"],
            "influential_citations": citation_data["influential_citations"],
        }

        # Add edges for references (this paper cites others)
        for ref_id in citation_data["references"]:
            if ref_id:
                edges.append((paper_id, ref_id))
                all_paper_ids.add(ref_id)

        # Add edges for citations (others cite this paper)
        for cit_id in citation_data["citations"]:
            if cit_id:
                edges.append((cit_id, paper_id))
                all_paper_ids.add(cit_id)

    graph = {
        "nodes": list(all_paper_ids),
        "edges": edges,
        "metadata": metadata,
        "node_count": len(all_paper_ids),
        "edge_count": len(edges),
    }

    logger.info(
        f"✓ Citation graph built: {graph['node_count']} nodes, {graph['edge_count']} edges"
    )
    return graph


def find_influential_papers(
    paper_ids: List[str],
    top_k: int = 5,
) -> List[Dict]:
    """
    Find the most influential papers in a set.

    Influential = high citation count + high influential citation count.

    Args:
        paper_ids: List of Semantic Scholar paper IDs
        top_k: Number of top papers to return

    Returns:
        List of paper dictionaries sorted by influence score

    Example:
        >>> influential = find_influential_papers(["id1", "id2", ...], top_k=3)
        >>> print(influential[0]['paper_id'], influential[0]['influence_score'])
    """
    logger.info(f"Finding top {top_k} influential papers from {len(paper_ids)} papers")

    papers_with_scores = []

    for paper_id in paper_ids:
        citation_data = get_paper_citations(paper_id)

        # Calculate influence score
        # Weight: influential citations count more than regular citations
        influence_score = (
            citation_data["citation_count"] + citation_data["influential_citations"] * 3
        )

        papers_with_scores.append(
            {
                "paper_id": paper_id,
                "citation_count": citation_data["citation_count"],
                "influential_citations": citation_data["influential_citations"],
                "influence_score": influence_score,
            }
        )

    # Sort by influence score
    papers_with_scores.sort(key=lambda x: x["influence_score"], reverse=True)

    top_papers = papers_with_scores[:top_k]

    logger.info(
        f"✓ Top {len(top_papers)} papers identified (max score: "
        f"{top_papers[0]['influence_score'] if top_papers else 0})"
    )

    return top_papers


def get_common_citations(
    paper_id1: str,
    paper_id2: str,
) -> Dict:
    """
    Find common citations between two papers.

    Useful for identifying related work and shared foundations.

    Args:
        paper_id1: First paper ID
        paper_id2: Second paper ID

    Returns:
        Dictionary with:
            - common_references: Papers cited by both
            - common_citations: Papers citing both
            - jaccard_references: Jaccard similarity of references
            - jaccard_citations: Jaccard similarity of citations

    Example:
        >>> common = get_common_citations("id1", "id2")
        >>> print(f"Shared {len(common['common_references'])} references")
    """
    logger.debug(f"Finding common citations between {paper_id1} and {paper_id2}")

    # Fetch citations for both papers
    data1 = get_paper_citations(paper_id1)
    data2 = get_paper_citations(paper_id2)

    # Convert to sets
    refs1 = set(data1["references"])
    refs2 = set(data2["references"])
    cits1 = set(data1["citations"])
    cits2 = set(data2["citations"])

    # Find intersections
    common_refs = refs1.intersection(refs2)
    common_cits = cits1.intersection(cits2)

    # Calculate Jaccard similarity
    jaccard_refs = (
        len(common_refs) / len(refs1.union(refs2)) if refs1.union(refs2) else 0.0
    )
    jaccard_cits = (
        len(common_cits) / len(cits1.union(cits2)) if cits1.union(cits2) else 0.0
    )

    result = {
        "paper_id1": paper_id1,
        "paper_id2": paper_id2,
        "common_references": list(common_refs),
        "common_citations": list(common_cits),
        "jaccard_references": jaccard_refs,
        "jaccard_citations": jaccard_cits,
        "similarity_score": (jaccard_refs + jaccard_cits) / 2,  # Average
    }

    logger.debug(
        f"✓ Common: {len(common_refs)} refs, {len(common_cits)} cites "
        f"(similarity: {result['similarity_score']:.2f})"
    )

    return result


def trace_citation_path(
    source_paper_id: str,
    target_paper_id: str,
    max_depth: int = 3,
) -> Optional[List[str]]:
    """
    Find citation path between two papers (BFS).

    Args:
        source_paper_id: Starting paper ID
        target_paper_id: Target paper ID
        max_depth: Maximum path length to search

    Returns:
        List of paper IDs forming the path, or None if no path found

    Example:
        >>> path = trace_citation_path("id1", "id5", max_depth=3)
        >>> if path:
        >>>     print(" → ".join(path))
    """
    logger.debug(f"Tracing citation path: {source_paper_id} → {target_paper_id}")

    if source_paper_id == target_paper_id:
        return [source_paper_id]

    # BFS queue: (current_paper, path)
    from collections import deque

    queue = deque([(source_paper_id, [source_paper_id])])
    visited = {source_paper_id}

    while queue:
        current, path = queue.popleft()

        # Check depth limit
        if len(path) > max_depth:
            continue

        # Get citations
        citation_data = get_paper_citations(current)

        # Check references (papers cited by current)
        for ref_id in citation_data["references"]:
            if ref_id == target_paper_id:
                logger.info(f"✓ Found citation path (length {len(path) + 1})")
                return path + [ref_id]

            if ref_id not in visited:
                visited.add(ref_id)
                queue.append((ref_id, path + [ref_id]))

    logger.debug("No citation path found")
    return None
