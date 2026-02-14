"""
Unit tests for research tools.

Tests Semantic Scholar, arXiv, and citation analyzer tools with mocked responses.
"""

import pytest
import json
from pathlib import Path
from unittest.mock import Mock, patch, AsyncMock
import httpx

# Import tools to test
from src.tools.semantic_scholar_tool import (
    search_semantic_scholar,
    search_semantic_scholar_async,
    deduplicate_papers,
    merge_paper_lists,
)
from src.tools.arxiv_tool import search_arxiv, search_arxiv_async
from src.tools.citation_analyzer import (
    get_paper_citations,
    build_citation_graph,
    find_influential_papers,
)


# Load test fixtures
@pytest.fixture
def sample_papers():
    """Load sample papers from fixtures."""
    fixtures_path = Path(__file__).parent / "fixtures" / "sample_papers.json"
    with open(fixtures_path) as f:
        return json.load(f)


# ==================== Semantic Scholar Tests ====================


def test_semantic_scholar_search_mock(sample_papers):
    """Test Semantic Scholar search with mocked API response."""
    mock_response = Mock()
    mock_response.json.return_value = {"data": sample_papers["semantic_scholar_papers"]}
    mock_response.status_code = 200

    with patch("httpx.get", return_value=mock_response):
        results = search_semantic_scholar("graph neural networks", limit=3)

        assert len(results) == 3
        assert results[0]["source"] == "semantic_scholar"
        assert "Graph Attention Networks" in results[0]["title"]
        assert results[0]["year"] == 2018
        assert results[0]["citation_count"] == 12543


@pytest.mark.asyncio
async def test_semantic_scholar_async_search(sample_papers):
    """Test async Semantic Scholar search."""
    mock_response = Mock()
    mock_response.json.return_value = {"data": sample_papers["semantic_scholar_papers"]}
    mock_response.status_code = 200

    async def mock_get(*args, **kwargs):
        return mock_response

    with patch("httpx.AsyncClient.get", new=AsyncMock(return_value=mock_response)):
        results = await search_semantic_scholar_async("GNN", limit=2)

        assert len(results) == 3  # All papers returned
        assert results[0]["source"] == "semantic_scholar"


def test_semantic_scholar_empty_result():
    """Test handling of empty search results."""
    mock_response = Mock()
    mock_response.json.return_value = {"data": []}
    mock_response.status_code = 200

    with patch("httpx.get", return_value=mock_response):
        results = search_semantic_scholar("nonexistent query")

        assert len(results) == 0


def test_semantic_scholar_api_error():
    """Test handling of API errors."""
    from src.utils.retry import APIError

    with patch("httpx.get", side_effect=httpx.HTTPStatusError("500 error", request=Mock(), response=Mock(status_code=500))):
        # Server errors (500) are wrapped in APIError after retries
        with pytest.raises(APIError):
            search_semantic_scholar("test query")


# ==================== arXiv Tests ====================


def test_arxiv_search_mock(sample_papers):
    """Test arXiv search with mocked results."""
    # Create mock arxiv.Result objects
    mock_results = []
    for paper_data in sample_papers["arxiv_papers"]:
        mock_result = Mock()
        mock_result.entry_id = paper_data["entry_id"]
        mock_result.title = paper_data["title"]
        mock_result.summary = paper_data["summary"]
        mock_result.authors = [Mock(name=name) for name in paper_data["authors"]]
        mock_result.published = Mock(year=2021, strftime=lambda x: "2021-03-25")
        mock_result.updated = Mock(strftime=lambda x: "2021-03-25")
        mock_result.categories = paper_data["categories"]
        mock_result.pdf_url = paper_data["pdf_url"]
        mock_results.append(mock_result)

    mock_client = Mock()
    mock_client.results.return_value = mock_results

    with patch("arxiv.Client", return_value=mock_client):
        results = search_arxiv("graph transformers", max_results=2)

        assert len(results) == 2
        assert results[0]["source"] == "arxiv"
        assert "Graph Transformer" in results[0]["title"]


@pytest.mark.asyncio
async def test_arxiv_async_search():
    """Test async arXiv search."""
    # Mock the sync search function since arxiv doesn't have native async
    with patch("src.tools.arxiv_tool.search_arxiv", return_value=[{"title": "Test"}]):
        results = await search_arxiv_async("test", max_results=1)

        assert len(results) == 1
        assert results[0]["title"] == "Test"


def test_arxiv_error_handling():
    """Test arXiv error handling (should return empty list, not raise)."""
    with patch("arxiv.Client", side_effect=Exception("API error")):
        results = search_arxiv("test query")

        # Should return empty list, not raise exception
        assert results == []


# ==================== Citation Analyzer Tests ====================


def test_get_paper_citations_mock(sample_papers):
    """Test fetching paper citations with mocked API."""
    paper_id = "e23dc55ec50a996d01baa56c3a1407a28e17ddea"
    citation_data = sample_papers["citation_data"][paper_id]

    mock_response = Mock()
    mock_response.json.return_value = {
        "references": [{"paperId": pid} for pid in citation_data["references"]],
        "citations": [{"paperId": pid} for pid in citation_data["citations"]],
        "influentialCitationCount": citation_data["influentialCitationCount"],
    }
    mock_response.status_code = 200

    with patch("httpx.get", return_value=mock_response):
        result = get_paper_citations(paper_id)

        assert result["paper_id"] == paper_id
        assert len(result["references"]) == 3
        assert len(result["citations"]) == 4
        assert result["influential_citations"] == 450


def test_build_citation_graph(sample_papers):
    """Test building citation graph."""
    paper_ids = list(sample_papers["citation_data"].keys())

    def mock_get_citations(paper_id, *args, **kwargs):
        data = sample_papers["citation_data"].get(paper_id, {})
        return {
            "paper_id": paper_id,
            "references": data.get("references", []),
            "citations": data.get("citations", []),
            "reference_count": len(data.get("references", [])),
            "citation_count": len(data.get("citations", [])),
            "influential_citations": data.get("influentialCitationCount", 0),
        }

    with patch("src.tools.citation_analyzer.get_paper_citations", side_effect=mock_get_citations):
        graph = build_citation_graph(paper_ids)

        assert "nodes" in graph
        assert "edges" in graph
        assert graph["node_count"] > 0
        assert graph["edge_count"] > 0
        assert len(graph["metadata"]) == len(paper_ids)


def test_find_influential_papers(sample_papers):
    """Test finding influential papers."""
    paper_ids = list(sample_papers["citation_data"].keys())

    def mock_get_citations(paper_id, *args, **kwargs):
        data = sample_papers["citation_data"].get(paper_id, {})
        return {
            "paper_id": paper_id,
            "citation_count": len(data.get("citations", [])),
            "influential_citations": data.get("influentialCitationCount", 0),
        }

    with patch("src.tools.citation_analyzer.get_paper_citations", side_effect=mock_get_citations):
        influential = find_influential_papers(paper_ids, top_k=2)

        assert len(influential) == 2
        # Check sorted by influence score
        assert influential[0]["influence_score"] >= influential[1]["influence_score"]


# ==================== Deduplication Tests ====================


def test_deduplicate_papers():
    """Test paper deduplication logic."""
    papers = [
        {"id": "123", "title": "Graph Neural Networks", "abstract": "Test"},
        {"id": "123", "title": "Graph Neural Networks", "abstract": "Test"},  # Duplicate ID
        {"id": "456", "title": "graph neural networks", "abstract": "Test2"},  # Duplicate title (case-insensitive)
        {"id": "789", "title": "Different Paper", "abstract": "Test3"},
    ]

    unique = deduplicate_papers(papers)

    assert len(unique) == 2  # Should remove 2 duplicates
    assert unique[0]["id"] == "123"
    assert unique[1]["id"] == "789"


def test_merge_paper_lists():
    """Test merging multiple paper lists."""
    list1 = [
        {"id": "1", "title": "Paper A", "source": "semantic_scholar"},
        {"id": "2", "title": "Paper B", "source": "semantic_scholar"},
    ]
    list2 = [
        {"id": "2", "title": "Paper B", "source": "arxiv"},  # Duplicate
        {"id": "3", "title": "Paper C", "source": "arxiv"},
    ]

    merged = merge_paper_lists(list1, list2)

    assert len(merged) == 3  # Should have 3 unique papers
    # Check all IDs present
    ids = [p["id"] for p in merged]
    assert "1" in ids
    assert "2" in ids
    assert "3" in ids


# ==================== Integration Tests ====================


@pytest.mark.asyncio
async def test_parallel_search_simulation(sample_papers):
    """Simulate parallel search across Semantic Scholar and arXiv."""
    import asyncio

    # Mock both APIs
    ss_mock = Mock()
    ss_mock.json.return_value = {"data": sample_papers["semantic_scholar_papers"][:2]}

    arxiv_mock_results = []
    for paper in sample_papers["arxiv_papers"][:1]:
        mock_result = Mock()
        mock_result.entry_id = paper["entry_id"]
        mock_result.title = paper["title"]
        mock_result.summary = paper["summary"]
        mock_result.authors = [Mock(name=n) for n in paper["authors"]]
        mock_result.published = Mock(year=2021, strftime=lambda x: "2021-03-25")
        mock_result.updated = Mock(strftime=lambda x: "2021-03-25")
        mock_result.categories = paper["categories"]
        mock_result.pdf_url = paper["pdf_url"]
        arxiv_mock_results.append(mock_result)

    with patch("httpx.AsyncClient.get", new=AsyncMock(return_value=ss_mock)):
        with patch("arxiv.Client", return_value=Mock(results=lambda x: arxiv_mock_results)):
            # Run searches in parallel
            ss_task = search_semantic_scholar_async("GNN", limit=2)
            arxiv_task = search_arxiv_async("GNN", max_results=1)

            ss_results, arxiv_results = await asyncio.gather(ss_task, arxiv_task)

            # Merge results
            all_results = merge_paper_lists(ss_results, arxiv_results)

            assert len(all_results) >= 2  # At least some results
            # Check both sources present
            sources = [p["source"] for p in all_results]
            assert "semantic_scholar" in sources
            assert "arxiv" in sources


# ==================== Error Handling Tests ====================


def test_retry_on_rate_limit():
    """Test retry logic on rate limit error."""
    # First call fails with 429, second succeeds
    error_response = Mock(status_code=429)
    success_response = Mock()
    success_response.json.return_value = {"data": []}
    success_response.status_code = 200

    call_count = 0

    def mock_get(*args, **kwargs):
        nonlocal call_count
        call_count += 1
        if call_count == 1:
            raise httpx.HTTPStatusError("429", request=Mock(), response=error_response)
        return success_response

    with patch("httpx.get", side_effect=mock_get):
        # Should succeed on retry
        results = search_semantic_scholar("test")

        assert call_count == 2  # First failed, second succeeded
        assert results == []  # Empty results but no exception


def test_no_retry_on_auth_error():
    """Test that authentication errors don't retry."""
    error_response = Mock(status_code=401)

    with patch("httpx.get", side_effect=httpx.HTTPStatusError("401", request=Mock(), response=error_response)):
        with pytest.raises(httpx.HTTPStatusError):
            search_semantic_scholar("test")
