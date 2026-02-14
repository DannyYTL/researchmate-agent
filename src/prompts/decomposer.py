"""
Prompt templates for query decomposition.

These prompts guide the LLM to break down research questions into
focused sub-queries for more effective literature search.
"""

from typing import List
from pydantic import BaseModel, Field


class SubQueryList(BaseModel):
    """Pydantic model for structured sub-query output."""

    queries: List[str] = Field(
        description="List of 3-5 focused sub-queries for academic search",
        min_length=3,
        max_length=5,
    )
    reasoning: str = Field(
        description="Brief explanation of decomposition strategy"
    )


def get_decomposition_prompt(query: str) -> str:
    """
    Generate prompt for query decomposition.

    Args:
        query: Original research question

    Returns:
        Formatted prompt for LLM

    Example:
        >>> prompt = get_decomposition_prompt("What are recent advances in GNNs?")
    """
    return f"""You are a research assistant helping to conduct academic literature review.

Your task is to decompose a broad research question into 3-5 focused sub-queries that will be used to search academic databases (Semantic Scholar and arXiv).

**Original Research Question:**
"{query}"

**Your Goal:**
Break this question down into specific, searchable sub-queries that:
1. Cover different aspects/dimensions of the topic
2. Are specific enough to retrieve relevant papers
3. Use appropriate academic terminology
4. Focus on recent work (2022-2026 when relevant)
5. Avoid redundancy - each sub-query should target a distinct aspect

**Guidelines:**
- Each sub-query should be a complete search phrase (not a question)
- Include key technical terms and concepts
- Consider: architectures, applications, methods, datasets, evaluation metrics
- Think about subdisciplines and related areas

**Example:**
Original: "How are transformers used in computer vision?"
Sub-queries:
1. "Vision transformer architectures ViT SWIN 2023-2024"
2. "Self-attention mechanisms image recognition"
3. "Transformer-based object detection DETR"
4. "Vision transformers vs CNNs comparative analysis"

Now decompose the original question into 3-5 sub-queries.

Also provide brief reasoning explaining your decomposition strategy.
"""


def get_refinement_prompt(
    original_query: str,
    initial_sub_queries: List[str],
    feedback: str
) -> str:
    """
    Generate prompt for refining sub-queries based on feedback.

    Args:
        original_query: Original research question
        initial_sub_queries: Previously generated sub-queries
        feedback: Human or automated feedback

    Returns:
        Prompt for query refinement
    """
    queries_text = "\n".join(f"{i+1}. {q}" for i, q in enumerate(initial_sub_queries))

    return f"""You are refining sub-queries for academic literature search.

**Original Research Question:**
"{original_query}"

**Current Sub-Queries:**
{queries_text}

**Feedback:**
{feedback}

**Your Task:**
Revise the sub-queries based on the feedback while maintaining:
- Coverage of different aspects
- Academic terminology
- Specificity for effective search
- Focus on recent work

Generate 3-5 improved sub-queries with reasoning.
"""


# System prompt for query decomposition
DECOMPOSITION_SYSTEM_PROMPT = """You are an expert research assistant specializing in academic literature review. Your role is to help researchers find relevant papers by decomposing broad research questions into focused, searchable sub-queries.

Key principles:
- Understand the research domain and its terminology
- Consider multiple perspectives and aspects
- Balance breadth (coverage) with depth (specificity)
- Use terms that match how papers are actually titled/described
- Focus on recent, relevant work

You always provide structured output with clear reasoning."""
