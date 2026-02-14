"""
Research workflow state schema.

Defines the shared state that flows through all graph nodes using TypedDict.
"""

from typing import TypedDict, List, Annotated, Optional, Dict, Any
from operator import add

# Reducer for merging lists (used with Annotated)
# When multiple nodes update the same field, the reducer determines how to merge


class ResearchState(TypedDict):
    """
    Central state object for the research workflow.

    This state flows through all nodes in the LangGraph workflow.
    Fields marked with Annotated[List[X], add] will accumulate values
    across multiple node updates.

    State Flow:
    1. Input phase: original_query
    2. Planning phase: sub_queries, user_approved
    3. Search phase: papers
    4. Analysis phase: analyzed_papers, citation_network
    5. Synthesis phase: key_findings, research_gaps, final_report
    6. Metadata: current_step, error_count, execution_time
    """

    # ==================== Input ====================
    original_query: str
    """User's original research question."""

    # ==================== Planning Phase ====================
    sub_queries: Annotated[List[str], add]
    """
    Decomposed sub-queries for focused search.
    Uses add reducer to accumulate across multiple decomposition steps.
    """

    user_approved: bool
    """Flag indicating human approval of sub-queries (HITL)."""

    # ==================== Search Phase ====================
    papers: Annotated[List[Dict[str, Any]], add]
    """
    Accumulated papers from all searches.
    Each paper is a dict with standardized fields (id, title, abstract, etc.)
    Uses add reducer to merge results from parallel searches.
    """

    # ==================== Analysis Phase ====================
    analyzed_papers: Annotated[List[Dict[str, Any]], add]
    """
    Papers with extracted information (contributions, methods, results).
    Uses add reducer to accumulate analysis results.
    """

    citation_network: Optional[Dict[str, Any]]
    """
    Citation graph structure with nodes, edges, and metadata.
    Format: {
        "nodes": List[str],          # Paper IDs
        "edges": List[Tuple[str, str]],  # Citation relationships
        "metadata": Dict[str, Dict],  # Per-paper metadata
        "node_count": int,
        "edge_count": int
    }
    """

    # ==================== Synthesis Phase ====================
    key_findings: List[str]
    """Main discoveries and insights extracted from papers."""

    research_gaps: List[str]
    """Identified gaps in current research."""

    final_report: str
    """Generated markdown report with structured findings."""

    # ==================== Metadata ====================
    current_step: str
    """
    Current workflow step for debugging and visualization.
    Values: "start", "decomposed", "approved", "searched",
            "analyzed", "citations_built", "synthesized", "complete"
    """

    error_count: int
    """
    Number of errors encountered during execution.
    Used for retry budget and error handling.
    """

    execution_time: float
    """
    Total execution time in seconds.
    Updated at the end of workflow for performance tracking.
    """


# Type alias for node return values
# Nodes return partial state updates as plain dicts
NodeUpdate = Dict[str, Any]


def create_initial_state(query: str) -> ResearchState:
    """
    Create initial state for a research query.

    Args:
        query: User's research question

    Returns:
        Initial ResearchState with default values

    Example:
        >>> state = create_initial_state("What are recent advances in GNNs?")
        >>> state["original_query"]
        "What are recent advances in GNNs?"
        >>> state["current_step"]
        "start"
    """
    return {
        # Input
        "original_query": query,
        # Planning
        "sub_queries": [],
        "user_approved": False,
        # Search
        "papers": [],
        # Analysis
        "analyzed_papers": [],
        "citation_network": None,
        # Synthesis
        "key_findings": [],
        "research_gaps": [],
        "final_report": "",
        # Metadata
        "current_step": "start",
        "error_count": 0,
        "execution_time": 0.0,
    }


def validate_state(state: ResearchState) -> bool:
    """
    Validate state has required fields.

    Args:
        state: Research state to validate

    Returns:
        True if valid, False otherwise

    Example:
        >>> state = create_initial_state("test query")
        >>> validate_state(state)
        True
    """
    required_fields = [
        "original_query",
        "sub_queries",
        "papers",
        "current_step",
    ]

    for field in required_fields:
        if field not in state:
            return False

    return True


def get_state_summary(state: ResearchState) -> str:
    """
    Get human-readable summary of current state.

    Args:
        state: Research state

    Returns:
        Formatted summary string

    Example:
        >>> state = create_initial_state("GNN research")
        >>> print(get_state_summary(state))
        Step: start | Query: "GNN research" | Papers: 0 | Analyzed: 0
    """
    return (
        f"Step: {state['current_step']} | "
        f"Query: \"{state['original_query'][:50]}...\" | "
        f"Sub-queries: {len(state.get('sub_queries', []))} | "
        f"Papers: {len(state.get('papers', []))} | "
        f"Analyzed: {len(state.get('analyzed_papers', []))} | "
        f"Errors: {state.get('error_count', 0)}"
    )
