"""
LangGraph workflow construction for ResearchMate.

This module defines the complete research agent workflow by connecting
all nodes into a directed graph with conditional edges.
"""

from langgraph.graph import StateGraph, END
try:
    from langgraph.checkpoint.sqlite import SqliteSaver
except ImportError:
    # Fallback for different LangGraph versions
    SqliteSaver = None

from src.graph.state import ResearchState, create_initial_state
from src.graph.nodes import (
    decompose_query_node,
    human_approval_node,
    parallel_search_node,
    analyze_papers_node,
    build_citation_network_node,
    synthesize_findings_node,
    reflection_node,
)
from src.utils.logger import setup_logger

logger = setup_logger(__name__)


def should_continue_research(state: ResearchState) -> str:
    """
    Conditional edge function to decide workflow continuation.

    Based on reflection node's assessment, decides whether to:
    - "end": Complete the research and generate final report
    - "continue": Loop back to search for more papers

    Args:
        state: Current research state

    Returns:
        "end" or "continue"

    Example:
        >>> state = {"current_step": "complete", ...}
        >>> should_continue_research(state)
        "end"
    """
    current_step = state.get("current_step", "")

    if current_step == "complete":
        logger.info("→ Workflow complete")
        return "end"
    elif current_step == "continue":
        logger.info("→ Continuing research (need more papers)")
        return "continue"
    else:
        # Default to end if unclear
        logger.warning(f"Unclear state '{current_step}', defaulting to end")
        return "end"


def create_research_workflow(enable_hitl: bool = True) -> StateGraph:
    """
    Create and compile the research agent workflow.

    The workflow follows this structure:

    START → decompose → [human_approval] → parallel_search →
    analyze → build_citations → synthesize → reflect → END
                                                     ↓
                                              (conditional)
                                                     ↓
                                              parallel_search (loop)

    Args:
        enable_hitl: Whether to include human-in-the-loop approval node.
                     Set to False for fully automated execution.

    Returns:
        Compiled LangGraph workflow ready for execution

    Example:
        >>> workflow = create_research_workflow(enable_hitl=True)
        >>> result = workflow.invoke({"original_query": "What are GNNs?"})
    """
    logger.info(f"Creating research workflow (HITL: {enable_hitl})")

    # Create StateGraph with ResearchState type
    workflow = StateGraph(ResearchState)

    # Add all nodes
    workflow.add_node("decompose", decompose_query_node)

    if enable_hitl:
        workflow.add_node("human_approval", human_approval_node)

    workflow.add_node("parallel_search", parallel_search_node)
    workflow.add_node("analyze", analyze_papers_node)
    workflow.add_node("build_citations", build_citation_network_node)
    workflow.add_node("synthesize", synthesize_findings_node)
    workflow.add_node("reflect", reflection_node)

    # Define workflow edges
    workflow.set_entry_point("decompose")

    if enable_hitl:
        workflow.add_edge("decompose", "human_approval")
        workflow.add_edge("human_approval", "parallel_search")
    else:
        workflow.add_edge("decompose", "parallel_search")

    workflow.add_edge("parallel_search", "analyze")
    workflow.add_edge("analyze", "build_citations")
    workflow.add_edge("build_citations", "synthesize")
    workflow.add_edge("synthesize", "reflect")

    # Conditional edge from reflect
    workflow.add_conditional_edges(
        "reflect",
        should_continue_research,
        {
            "continue": "parallel_search",  # Loop back for more papers
            "end": END,
        },
    )

    # Add SQLite checkpointer for persistence (in-memory for now)
    if SqliteSaver:
        checkpointer = SqliteSaver.from_conn_string(":memory:")
        compiled = workflow.compile(checkpointer=checkpointer)
    else:
        # No checkpointer available
        compiled = workflow.compile()

    logger.info("✓ Workflow graph constructed")
    return compiled


def create_automated_workflow() -> StateGraph:
    """
    Create fully automated workflow without human approval.

    Convenience function for batch processing or automated runs.

    Returns:
        Compiled workflow without HITL node

    Example:
        >>> workflow = create_automated_workflow()
        >>> results = workflow.invoke({"original_query": "..."}  )
    """
    return create_research_workflow(enable_hitl=False)


# Pre-compiled workflows for convenience
research_workflow = create_research_workflow(enable_hitl=True)
automated_workflow = create_automated_workflow()


def run_research(
    query: str,
    enable_hitl: bool = True,
    verbose: bool = True
) -> ResearchState:
    """
    Convenience function to run a complete research query.

    Args:
        query: Research question
        enable_hitl: Whether to include human approval
        verbose: Whether to log progress

    Returns:
        Final research state with report

    Example:
        >>> result = run_research("What are recent advances in GNNs?")
        >>> print(result["final_report"])
    """
    if verbose:
        logger.info(f"\n{'='*60}")
        logger.info(f"🔬 Starting Research: '{query}'")
        logger.info(f"{'='*60}\n")

    # Create initial state
    initial_state = create_initial_state(query)

    # Select workflow
    workflow = research_workflow if enable_hitl else automated_workflow

    # Execute workflow
    import time
    start_time = time.time()

    try:
        final_state = workflow.invoke(initial_state)

        # Add execution time
        final_state["execution_time"] = time.time() - start_time

        if verbose:
            logger.info(f"\n{'='*60}")
            logger.info(f"✅ Research Complete!")
            logger.info(f"{'='*60}")
            logger.info(f"Papers analyzed: {len(final_state.get('analyzed_papers', []))}")
            logger.info(f"Key findings: {len(final_state.get('key_findings', []))}")
            logger.info(f"Execution time: {final_state['execution_time']:.1f}s")
            logger.info(f"{'='*60}\n")

        return final_state

    except Exception as e:
        logger.error(f"❌ Research failed: {e}")
        raise
