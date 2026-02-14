"""
Prompt templates for research synthesis and report generation.

These prompts guide the LLM to synthesize findings from multiple papers
into a coherent, structured research report.
"""

from typing import List, Dict, Any, Optional
from pydantic import BaseModel, Field


class ResearchSynthesis(BaseModel):
    """Pydantic model for structured synthesis output."""

    executive_summary: str = Field(
        description="2-3 sentence overview of findings"
    )
    key_findings: List[str] = Field(
        description="List of 3-7 main discoveries or insights",
        min_length=3,
        max_length=7
    )
    research_gaps: List[str] = Field(
        description="List of 2-5 identified research gaps",
        min_length=2,
        max_length=5
    )
    methodology_trends: Optional[str] = Field(
        default="",
        description="Common methodological approaches observed"
    )


def get_synthesis_prompt(
    original_query: str,
    analyzed_papers: List[Dict[str, Any]],
    citation_network: Optional[Dict[str, Any]] = None
) -> str:
    """
    Generate prompt for synthesizing research findings.

    Args:
        original_query: Original research question
        analyzed_papers: List of analyzed paper dictionaries
        citation_network: Optional citation graph data

    Returns:
        Formatted prompt for report generation
    """
    # Build paper summaries
    papers_summary = ""
    for i, paper in enumerate(analyzed_papers[:15], 1):  # Limit to 15 most relevant
        papers_summary += f"\n**Paper {i}: {paper.get('title', 'Unknown')}**\n"
        papers_summary += f"- Year: {paper.get('year', 'Unknown')}\n"
        papers_summary += f"- Contribution: {paper.get('contribution', 'N/A')}\n"
        papers_summary += f"- Results: {paper.get('results', 'N/A')}\n"
        papers_summary += f"- Relevance: {paper.get('relevance_score', 'N/A')}/5\n"

    # Add citation context if available
    citation_context = ""
    if citation_network:
        influential = citation_network.get("most_influential", [])
        if influential:
            citation_context = "\n**Most Influential Papers (by citation network):**\n"
            for paper_id, score in influential[:3]:
                citation_context += f"- Paper ID: {paper_id} (influence score: {score})\n"

    return f"""You are writing a comprehensive research report based on academic literature review.

**Original Research Question:**
"{original_query}"

**Analyzed Papers ({len(analyzed_papers)} total):**
{papers_summary}
{citation_context}

**Your Task:**
Synthesize the findings from these papers into a structured research report with the following sections:

1. **Executive Summary** (2-3 sentences)
   - Provide a concise overview of what was learned
   - Highlight the most important insights

2. **Key Findings** (3-7 bullet points)
   - Organize by themes or topics
   - Focus on novel contributions and significant results
   - Note consensus views and contradictions
   - Reference specific papers where relevant

3. **Methodological Approaches** (brief paragraph)
   - Common methods and techniques used across papers
   - Emerging approaches or innovations
   - Standard evaluation metrics or datasets

4. **Research Gaps** (2-5 bullet points)
   - Identify areas lacking research
   - Note limitations mentioned across papers
   - Suggest future research directions

5. **References** (formatted list)
   - List all papers analyzed
   - Format: [#] Author et al. (Year). Title. Venue.

**Guidelines:**
- Write for an academic audience
- Be objective and evidence-based
- Cite papers by number when making claims
- Organize thematically, not chronologically
- Highlight connections between papers
- Note disagreements or conflicting results
- Keep the report focused on answering the original question

**Output Format:**
Use clear markdown formatting with headers, bullet points, and proper citations.
"""


def get_reflection_prompt(
    original_query: str,
    sub_queries: List[str],
    papers_found: int,
    current_report: str
) -> str:
    """
    Generate prompt for self-reflection on research quality.

    Args:
        original_query: Original research question
        sub_queries: Generated sub-queries
        papers_found: Number of papers retrieved
        current_report: Draft report generated so far

    Returns:
        Prompt for quality assessment
    """
    return f"""You are evaluating the quality and completeness of a research literature review.

**Original Research Question:**
"{original_query}"

**Sub-Queries Used:**
{chr(10).join(f'{i+1}. {q}' for i, q in enumerate(sub_queries))}

**Papers Retrieved:** {papers_found}

**Current Report Preview:**
{current_report[:500]}...

**Your Task:**
Assess the research quality across these dimensions:

1. **Coverage**: Are all aspects of the original question addressed?
   - Score: 1-5
   - Missing aspects (if any)

2. **Recency**: Are papers recent enough (2022-2026 preferred)?
   - Score: 1-5
   - Older papers acceptable if foundational

3. **Depth**: Is there sufficient detail to answer the question?
   - Score: 1-5
   - Need more papers? Different queries?

4. **Quality**: Are the papers from reputable venues/authors?
   - Score: 1-5
   - Based on citation counts, venues

**Decision:**
Based on your assessment, recommend one of:
- **COMPLETE**: Research is sufficient, proceed to final report
- **CONTINUE**: Need more papers, suggest refined sub-queries
- **REFINE**: Current results are off-topic, need better queries

Provide scores, reasoning, and clear recommendation.
"""


# System prompt for synthesis
SYNTHESIS_SYSTEM_PROMPT = """You are an expert academic writer and researcher. Your role is to synthesize findings from multiple research papers into coherent, well-structured literature reviews.

Key principles:
- Organize information thematically, not paper-by-paper
- Identify patterns, trends, and contradictions
- Maintain academic rigor and citation practices
- Write clearly and concisely
- Focus on answering the research question
- Note limitations and gaps honestly

You produce publication-quality research summaries."""
