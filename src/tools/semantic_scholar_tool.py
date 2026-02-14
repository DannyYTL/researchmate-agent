"""
Semantic Scholar API tool for academic paper search.

Provides both synchronous and asynchronous search functions with
automatic retry logic and deduplication.
"""

import os
from typing import List, Dict, Optional
import httpx
from dotenv import load_dotenv

from src.utils.logger import setup_logger
from src.utils.retry import retry_with_backoff, call_with_retry_async

load_dotenv()
logger = setup_logger(__name__)

# Semantic Scholar API configuration
SEMANTIC_SCHOLAR_API_BASE = "https://api.semanticscholar.org/graph/v1"
SEMANTIC_SCHOLAR_API_KEY = os.getenv("SEMANTIC_SCHOLAR_API_KEY")


def search_semantic_scholar(
    query: str,
    limit: int = 10,
    fields: Optional[List[str]] = None,
    year_min: Optional[int] = None,
    year_max: Optional[int] = None,
) -> List[Dict]:
    """
    Search Semantic Scholar for academic papers (synchronous).

    Args:
        query: Search query string
        limit: Maximum number of papers to return (default 10, max 100)
        fields: List of fields to return. Defaults to essential fields.
        year_min: Minimum publication year (optional)
        year_max: Maximum publication year (optional)

    Returns:
        List of paper dictionaries with standardized fields

    Raises:
        httpx.HTTPError: If API request fails after retries

    Example:
        >>> papers = search_semantic_scholar("graph neural networks", limit=5)
        >>> print(papers[0]['title'])
        "Graph Attention Networks"
    """
    # Default fields for paper retrieval
    if fields is None:
        fields = [
            "paperId",
            "title",
            "abstract",
            "authors",
            "year",
            "citationCount",
            "url",
            "venue",
            "publicationDate",
        ]

    # Build query parameters
    params = {
        "query": query,
        "limit": min(limit, 100),  # API max is 100
        "fields": ",".join(fields),
    }

    # Add year filters if specified
    if year_min:
        params["year"] = f"{year_min}-"
    if year_max:
        if year_min:
            params["year"] = f"{year_min}-{year_max}"
        else:
            params["year"] = f"-{year_max}"

    # Build headers
    headers = {}
    if SEMANTIC_SCHOLAR_API_KEY:
        headers["x-api-key"] = SEMANTIC_SCHOLAR_API_KEY
        logger.debug("Using Semantic Scholar API key")

    url = f"{SEMANTIC_SCHOLAR_API_BASE}/paper/search"

    logger.info(f"Searching Semantic Scholar: '{query}' (limit={limit})")

    try:
        # Use retry wrapper
        @retry_with_backoff(max_attempts=3)
        def _fetch():
            response = httpx.get(url, params=params, headers=headers, timeout=30.0)
            response.raise_for_status()
            return response.json()

        data = _fetch()
        papers = data.get("data", [])

        # Standardize paper format
        standardized = [_standardize_paper(paper) for paper in papers]

        logger.info(f"✓ Found {len(standardized)} papers from Semantic Scholar")
        return standardized

    except httpx.HTTPError as e:
        logger.error(f"Semantic Scholar API error: {e}")
        raise


async def search_semantic_scholar_async(
    query: str,
    limit: int = 10,
    fields: Optional[List[str]] = None,
    year_min: Optional[int] = None,
    year_max: Optional[int] = None,
) -> List[Dict]:
    """
    Search Semantic Scholar for academic papers (asynchronous).

    Same as search_semantic_scholar but async for parallel execution.

    Args:
        query: Search query string
        limit: Maximum number of papers to return
        fields: List of fields to return
        year_min: Minimum publication year
        year_max: Maximum publication year

    Returns:
        List of standardized paper dictionaries

    Example:
        >>> papers = await search_semantic_scholar_async("transformers", limit=10)
    """
    # Default fields
    if fields is None:
        fields = [
            "paperId",
            "title",
            "abstract",
            "authors",
            "year",
            "citationCount",
            "url",
            "venue",
            "publicationDate",
        ]

    # Build query parameters
    params = {
        "query": query,
        "limit": min(limit, 100),
        "fields": ",".join(fields),
    }

    # Add year filters
    if year_min:
        params["year"] = f"{year_min}-"
    if year_max:
        if year_min:
            params["year"] = f"{year_min}-{year_max}"
        else:
            params["year"] = f"-{year_max}"

    # Build headers
    headers = {}
    if SEMANTIC_SCHOLAR_API_KEY:
        headers["x-api-key"] = SEMANTIC_SCHOLAR_API_KEY

    url = f"{SEMANTIC_SCHOLAR_API_BASE}/paper/search"

    logger.info(f"Async searching Semantic Scholar: '{query}' (limit={limit})")

    async def _fetch():
        async with httpx.AsyncClient() as client:
            response = await client.get(url, params=params, headers=headers, timeout=30.0)
            response.raise_for_status()
            return response.json()

    try:
        data = await call_with_retry_async(_fetch, max_attempts=3)
        papers = data.get("data", [])

        # Standardize format
        standardized = [_standardize_paper(paper) for paper in papers]

        logger.info(f"✓ Async found {len(standardized)} papers from Semantic Scholar")
        return standardized

    except httpx.HTTPError as e:
        logger.error(f"Semantic Scholar async API error: {e}")
        raise


def _standardize_paper(paper: Dict) -> Dict:
    """
    Standardize paper data to consistent format.

    Converts Semantic Scholar format to unified format used across tools.

    Args:
        paper: Raw paper data from Semantic Scholar

    Returns:
        Standardized paper dictionary
    """
    # Extract author names
    authors = []
    if "authors" in paper and paper["authors"]:
        authors = [author.get("name", "Unknown") for author in paper["authors"]]

    return {
        "id": paper.get("paperId", ""),
        "source": "semantic_scholar",
        "title": paper.get("title", "Untitled"),
        "abstract": paper.get("abstract", ""),
        "authors": authors,
        "year": paper.get("year"),
        "citation_count": paper.get("citationCount", 0),
        "url": paper.get("url", ""),
        "venue": paper.get("venue", ""),
        "publication_date": paper.get("publicationDate", ""),
    }


def deduplicate_papers(papers: List[Dict]) -> List[Dict]:
    """
    Remove duplicate papers from a list.

    Deduplication is based on paper ID and title similarity.

    Args:
        papers: List of paper dictionaries

    Returns:
        Deduplicated list of papers

    Example:
        >>> papers = [{"id": "123", "title": "GNN"}, {"id": "123", "title": "GNN"}]
        >>> deduplicate_papers(papers)
        [{"id": "123", "title": "GNN"}]
    """
    seen_ids = set()
    seen_titles = set()
    unique_papers = []

    for paper in papers:
        paper_id = paper.get("id", "")
        title = paper.get("title", "").lower().strip()

        # Skip if ID already seen
        if paper_id and paper_id in seen_ids:
            logger.debug(f"Skipping duplicate ID: {paper_id}")
            continue

        # Skip if very similar title seen (fuzzy matching)
        if title and title in seen_titles:
            logger.debug(f"Skipping duplicate title: {title[:50]}")
            continue

        # Add to unique list
        unique_papers.append(paper)
        if paper_id:
            seen_ids.add(paper_id)
        if title:
            seen_titles.add(title)

    if len(papers) > len(unique_papers):
        logger.info(f"Deduplicated: {len(papers)} → {len(unique_papers)} papers")

    return unique_papers


def merge_paper_lists(*paper_lists: List[Dict]) -> List[Dict]:
    """
    Merge multiple paper lists and deduplicate.

    Args:
        *paper_lists: Variable number of paper lists

    Returns:
        Merged and deduplicated list

    Example:
        >>> semantic_papers = search_semantic_scholar("GNN")
        >>> arxiv_papers = search_arxiv("GNN")
        >>> all_papers = merge_paper_lists(semantic_papers, arxiv_papers)
    """
    # Flatten all lists
    all_papers = []
    for paper_list in paper_lists:
        all_papers.extend(paper_list)

    # Deduplicate
    return deduplicate_papers(all_papers)
