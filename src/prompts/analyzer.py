"""
Prompt templates for paper analysis.

These prompts guide the LLM to extract structured information
from academic papers (contributions, methods, results, limitations).
"""

from typing import List, Optional
from pydantic import BaseModel, Field


class PaperAnalysis(BaseModel):
    """Pydantic model for structured paper analysis output."""

    contribution: str = Field(
        description="Main contribution in 1-2 sentences"
    )
    methodology: str = Field(
        description="Brief description of methods/approach used"
    )
    results: str = Field(
        description="Key findings and results"
    )
    limitations: Optional[str] = Field(
        default="",
        description="Mentioned limitations or future work"
    )
    relevance_score: int = Field(
        description="Relevance to original query (1-5 scale)",
        ge=1,
        le=5
    )


def get_analysis_prompt(paper: dict, original_query: str) -> str:
    """
    Generate prompt for analyzing a single paper.

    Args:
        paper: Paper dictionary with title, abstract, etc.
        original_query: Original research question for context

    Returns:
        Formatted prompt for LLM

    Example:
        >>> prompt = get_analysis_prompt(paper_dict, "GNN advances")
    """
    title = paper.get("title", "Unknown Title")
    abstract = paper.get("abstract", "No abstract available")
    authors = ", ".join(paper.get("authors", [])[:3])  # First 3 authors
    year = paper.get("year", "Unknown")

    return f"""You are analyzing an academic paper for a literature review.

**Original Research Question:**
"{original_query}"

**Paper Information:**
Title: {title}
Authors: {authors}
Year: {year}

**Abstract:**
{abstract}

**Your Task:**
Extract the following information from this paper:

1. **Contribution**: What is the main contribution or novel idea? (1-2 sentences)
2. **Methodology**: What approach/methods did they use? (brief description)
3. **Results**: What are the key findings or results? (main outcomes)
4. **Limitations**: Any mentioned limitations or future work directions? (optional)
5. **Relevance Score**: How relevant is this paper to the original research question? (1-5 scale)
   - 5 = Highly relevant, directly addresses the question
   - 4 = Very relevant, addresses key aspects
   - 3 = Moderately relevant, related but tangential
   - 2 = Somewhat relevant, peripheral connection
   - 1 = Minimally relevant, weak connection

**Guidelines:**
- Be concise and factual
- Focus on information present in the abstract
- If abstract lacks detail for a field, indicate "Not specified in abstract"
- Rate relevance based on how well it answers the original question

Provide structured analysis with all fields.
"""


def get_batch_analysis_prompt(papers: List[dict], original_query: str) -> str:
    """
    Generate prompt for analyzing multiple papers at once.

    More efficient but may sacrifice detail for individual papers.

    Args:
        papers: List of paper dictionaries
        original_query: Original research question

    Returns:
        Formatted prompt for batch analysis
    """
    papers_text = ""
    for i, paper in enumerate(papers[:10], 1):  # Limit to 10 papers
        title = paper.get("title", "Unknown")
        abstract = paper.get("abstract", "No abstract")[:300]  # Truncate
        papers_text += f"\n**Paper {i}:**\nTitle: {title}\nAbstract: {abstract}...\n"

    return f"""You are analyzing multiple academic papers for a literature review.

**Original Research Question:**
"{original_query}"

**Papers to Analyze:**
{papers_text}

**Your Task:**
For each paper, provide a brief analysis:
- Main contribution (1 sentence)
- Key results (1 sentence)
- Relevance to research question (1-5 score)

Be concise but accurate.
"""


# System prompt for paper analysis
ANALYSIS_SYSTEM_PROMPT = """You are an expert academic researcher skilled at quickly extracting key information from research papers. Your role is to analyze papers and identify their main contributions, methods, results, and relevance to specific research questions.

Key principles:
- Focus on factual information from abstracts
- Be concise but comprehensive
- Rate relevance objectively based on content overlap
- Note when information is missing rather than speculating
- Maintain academic terminology and precision

You always provide structured, parseable output."""
