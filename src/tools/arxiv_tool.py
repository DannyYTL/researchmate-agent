"""
arXiv API tool for preprint paper search.

Provides search functionality for arXiv papers (abstracts only, no PDF extraction).
"""

from typing import List, Dict, Optional
import arxiv
from datetime import datetime

from src.utils.logger import setup_logger

logger = setup_logger(__name__)


def search_arxiv(
    query: str,
    max_results: int = 10,
    sort_by: arxiv.SortCriterion = arxiv.SortCriterion.SubmittedDate,
    year_min: Optional[int] = None,
) -> List[Dict]:
    """
    Search arXiv for papers (abstracts only, no PDF extraction).

    Args:
        query: Search query string
        max_results: Maximum number of papers to return (default 10)
        sort_by: Sort criterion (SubmittedDate, Relevance, LastUpdatedDate)
        year_min: Minimum publication year (optional)

    Returns:
        List of paper dictionaries in standardized format

    Raises:
        arxiv.ArxivError: If API request fails

    Example:
        >>> papers = search_arxiv("graph neural networks", max_results=5)
        >>> print(papers[0]['title'])
    """
    logger.info(f"Searching arXiv: '{query}' (max_results={max_results})")

    # If year filter specified, add it to query
    if year_min:
        # arXiv doesn't have built-in year filter, we'll filter results
        logger.debug(f"Will filter results for year >= {year_min}")

    try:
        # Create arXiv client
        client = arxiv.Client()

        # Create search
        search = arxiv.Search(
            query=query,
            max_results=max_results * 2 if year_min else max_results,  # Fetch extra if filtering
            sort_by=sort_by,
        )

        # Fetch results
        papers = []
        for result in client.results(search):
            # Year filtering
            if year_min and result.published.year < year_min:
                continue

            paper = _standardize_arxiv_paper(result)
            papers.append(paper)

            # Stop if we have enough
            if len(papers) >= max_results:
                break

        logger.info(f"✓ Found {len(papers)} papers from arXiv")
        return papers

    except Exception as e:
        logger.error(f"arXiv API error: {e}")
        # Return empty list instead of raising - arXiv is secondary source
        return []


async def search_arxiv_async(
    query: str,
    max_results: int = 10,
    sort_by: arxiv.SortCriterion = arxiv.SortCriterion.SubmittedDate,
    year_min: Optional[int] = None,
) -> List[Dict]:
    """
    Search arXiv for papers (asynchronous version).

    Note: arxiv library doesn't have native async support, so this
    runs in executor. For true parallelism, use asyncio.to_thread.

    Args:
        query: Search query string
        max_results: Maximum number of papers to return
        sort_by: Sort criterion
        year_min: Minimum publication year

    Returns:
        List of standardized paper dictionaries

    Example:
        >>> papers = await search_arxiv_async("transformers", max_results=5)
    """
    import asyncio

    # Run sync version in executor
    return await asyncio.to_thread(
        search_arxiv,
        query=query,
        max_results=max_results,
        sort_by=sort_by,
        year_min=year_min,
    )


def _standardize_arxiv_paper(result: arxiv.Result) -> Dict:
    """
    Convert arXiv result to standardized paper format.

    Args:
        result: arxiv.Result object

    Returns:
        Standardized paper dictionary
    """
    # Extract arXiv ID from entry_id (format: http://arxiv.org/abs/2103.12345v2)
    arxiv_id = result.entry_id.split("/")[-1]

    return {
        "id": arxiv_id,
        "source": "arxiv",
        "title": result.title,
        "abstract": result.summary,
        "authors": [author.name for author in result.authors],
        "year": result.published.year,
        "citation_count": 0,  # arXiv doesn't provide citation counts
        "url": result.entry_id,
        "venue": "arXiv preprint",
        "publication_date": result.published.strftime("%Y-%m-%d"),
        # arXiv-specific fields
        "arxiv_id": arxiv_id,
        "categories": result.categories,
        "pdf_url": result.pdf_url,
        "updated": result.updated.strftime("%Y-%m-%d"),
    }


def get_recent_arxiv_papers(
    query: str,
    days: int = 30,
    max_results: int = 10,
) -> List[Dict]:
    """
    Get recently submitted arXiv papers.

    Args:
        query: Search query string
        days: Number of days to look back (default 30)
        max_results: Maximum number of papers to return

    Returns:
        List of recent papers

    Example:
        >>> recent = get_recent_arxiv_papers("deep learning", days=7)
    """
    from datetime import datetime, timedelta

    cutoff_year = (datetime.now() - timedelta(days=days)).year

    return search_arxiv(
        query=query,
        max_results=max_results,
        sort_by=arxiv.SortCriterion.SubmittedDate,
        year_min=cutoff_year,
    )


def search_arxiv_by_category(
    category: str,
    max_results: int = 10,
) -> List[Dict]:
    """
    Search arXiv by category.

    Args:
        category: arXiv category code (e.g., "cs.LG", "cs.AI", "q-bio.BM")
        max_results: Maximum number of papers to return

    Returns:
        List of papers in that category

    Common categories:
        - cs.LG: Machine Learning
        - cs.AI: Artificial Intelligence
        - cs.CV: Computer Vision
        - cs.CL: Computation and Language
        - q-bio.BM: Biomolecules

    Example:
        >>> ml_papers = search_arxiv_by_category("cs.LG", max_results=20)
    """
    logger.info(f"Searching arXiv category: {category}")

    # Use category as query with cat: prefix
    return search_arxiv(
        query=f"cat:{category}",
        max_results=max_results,
        sort_by=arxiv.SortCriterion.SubmittedDate,
    )
