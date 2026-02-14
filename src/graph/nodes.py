"""
LangGraph node functions for research workflow.

Each node is a pure function that takes state and returns a state update.
Nodes are connected in workflow.py to form the complete research agent.
"""

import asyncio
import time
from typing import Dict, Any, List

from src.graph.state import ResearchState, NodeUpdate
from src.api.client import llm_client
from src.tools.semantic_scholar_tool import (
    search_semantic_scholar_async,
    merge_paper_lists,
    deduplicate_papers,
)
from src.tools.arxiv_tool import search_arxiv_async
from src.tools.citation_analyzer import build_citation_graph, find_influential_papers
from src.prompts.decomposer import (
    get_decomposition_prompt,
    SubQueryList,
    DECOMPOSITION_SYSTEM_PROMPT,
)
from src.prompts.analyzer import (
    get_analysis_prompt,
    PaperAnalysis,
    ANALYSIS_SYSTEM_PROMPT,
)
from src.prompts.synthesizer import (
    get_synthesis_prompt,
    get_reflection_prompt,
    SYNTHESIS_SYSTEM_PROMPT,
)
from src.utils.logger import setup_logger

logger = setup_logger(__name__)


# ==================== Node 1: Decompose Query ====================


def decompose_query_node(state: ResearchState) -> NodeUpdate:
    """
    Decompose research question into focused sub-queries.

    Uses LLM with structured output to generate 3-5 searchable sub-queries
    that cover different aspects of the original question.

    Args:
        state: Current research state

    Returns:
        State update with sub_queries and current_step

    Example:
        >>> state = {"original_query": "What are recent advances in GNNs?", ...}
        >>> update = decompose_query_node(state)
        >>> len(update["sub_queries"])
        4
    """
    logger.info(f"🔍 Decomposing query: '{state['original_query'][:60]}...'")

    try:
        # Generate decomposition prompt
        prompt = get_decomposition_prompt(state["original_query"])

        # Call LLM with structured output
        result = llm_client.generate_structured(
            prompt=prompt,
            output_schema=SubQueryList,
            temperature=0.7,
        )

        sub_queries = result.queries
        logger.info(f"✓ Generated {len(sub_queries)} sub-queries:")
        for i, q in enumerate(sub_queries, 1):
            logger.info(f"  {i}. {q}")

        return {
            "sub_queries": sub_queries,
            "current_step": "decomposed",
        }

    except Exception as e:
        logger.error(f"Error in decompose_query_node: {e}")
        return {
            "error_count": state.get("error_count", 0) + 1,
            "current_step": "error_decomposition",
        }


# ==================== Node 2: Human Approval (HITL) ====================


def human_approval_node(state: ResearchState) -> NodeUpdate:
    """
    Human-in-the-loop approval of sub-queries.

    Displays sub-queries to user and allows approval, editing, or rejection.
    This leverages LangGraph's checkpointing for interactive workflows.

    Args:
        state: Current research state

    Returns:
        State update with user_approved flag

    Example:
        >>> update = human_approval_node(state)
        # User is prompted to approve queries
        >>> update["user_approved"]
        True
    """
    logger.info("\n📋 Sub-Queries for Approval:")
    logger.info("=" * 60)

    for i, query in enumerate(state["sub_queries"], 1):
        logger.info(f"{i}. {query}")

    logger.info("=" * 60)

    # Interactive approval
    print("\n💡 Review the sub-queries above.")
    print("Options:")
    print("  [y] Approve and continue")
    print("  [e] Edit queries")
    print("  [n] Reject and abort")

    choice = input("\nYour choice (y/e/n): ").strip().lower()

    if choice == 'y':
        logger.info("✓ User approved sub-queries")
        return {
            "user_approved": True,
            "current_step": "approved",
        }

    elif choice == 'e':
        logger.info("User chose to edit queries")
        edited_queries = []

        for i, query in enumerate(state["sub_queries"], 1):
            print(f"\nCurrent query {i}: {query}")
            new_query = input(f"Edit (press Enter to keep): ").strip()
            edited_queries.append(new_query if new_query else query)

        logger.info("✓ Queries edited and approved")
        return {
            "sub_queries": edited_queries,
            "user_approved": True,
            "current_step": "approved",
        }

    else:  # 'n' or anything else
        logger.warning("User rejected sub-queries")
        raise InterruptedError("User rejected sub-queries. Workflow aborted.")


# ==================== Node 3: Parallel Search ====================


def parallel_search_node(state: ResearchState) -> NodeUpdate:
    """
    Execute parallel searches across Semantic Scholar and arXiv.

    For each sub-query, searches both APIs concurrently, then merges
    and deduplicates results.

    Args:
        state: Current research state

    Returns:
        State update with papers and current_step

    Example:
        >>> update = parallel_search_node(state)
        >>> len(update["papers"])
        25  # Papers from all sources
    """
    logger.info(f"🔎 Parallel search for {len(state['sub_queries'])} sub-queries")

    all_papers = []

    # Run async searches in sync context
    import asyncio

    async def async_search():
        all_papers_async = []
        for sub_query in state["sub_queries"]:
            logger.info(f"  Searching: '{sub_query[:50]}...'")

            # Search both APIs in parallel
            ss_task = search_semantic_scholar_async(
                sub_query,
                limit=5,
                year_min=2022  # Focus on recent papers
            )
            arxiv_task = search_arxiv_async(
                sub_query,
                max_results=3
            )

            # Wait for both
            ss_results, arxiv_results = await asyncio.gather(
                ss_task,
                arxiv_task,
                return_exceptions=True
            )

            # Handle exceptions
            if isinstance(ss_results, Exception):
                logger.warning(f"Semantic Scholar search failed: {ss_results}")
                ss_results = []

            if isinstance(arxiv_results, Exception):
                logger.warning(f"arXiv search failed: {arxiv_results}")
                arxiv_results = []

            # Merge results for this query
            query_papers = merge_paper_lists(ss_results, arxiv_results)
            all_papers_async.extend(query_papers)

            logger.info(f"  Found {len(query_papers)} papers for this query")

        return all_papers_async

    try:
        # Run async function in sync context
        all_papers = asyncio.run(async_search())

        # Deduplicate across all queries
        unique_papers = deduplicate_papers(all_papers)

        logger.info(f"✓ Total papers found: {len(unique_papers)} (after deduplication)")

        return {
            "papers": unique_papers,
            "current_step": "searched",
        }

    except Exception as e:
        logger.error(f"Error in parallel_search_node: {e}")
        return {
            "error_count": state.get("error_count", 0) + 1,
            "current_step": "error_search",
        }


# ==================== Node 4: Analyze Papers ====================


def analyze_papers_node(state: ResearchState) -> NodeUpdate:
    """
    Extract structured information from each paper using LLM.

    For each paper, uses LLM to extract:
    - Main contribution
    - Methodology
    - Results
    - Limitations
    - Relevance score

    Args:
        state: Current research state

    Returns:
        State update with analyzed_papers

    Example:
        >>> update = analyze_papers_node(state)
        >>> update["analyzed_papers"][0]["contribution"]
        "Introduces graph attention networks with masked self-attention..."
    """
    papers = state["papers"]
    logger.info(f"📊 Analyzing {len(papers)} papers...")

    analyzed = []

    try:
        for i, paper in enumerate(papers, 1):
            logger.info(f"  [{i}/{len(papers)}] Analyzing: {paper.get('title', 'Unknown')[:50]}...")

            # Generate analysis prompt
            prompt = get_analysis_prompt(paper, state["original_query"])

            # Call LLM with structured output
            try:
                analysis = llm_client.generate_structured(
                    prompt=prompt,
                    output_schema=PaperAnalysis,
                    temperature=0.3,  # Lower temperature for factual extraction
                )

                # Merge analysis into paper dict
                analyzed_paper = {
                    **paper,  # Keep original fields
                    "contribution": analysis.contribution,
                    "methodology": analysis.methodology,
                    "results": analysis.results,
                    "limitations": analysis.limitations,
                    "relevance_score": analysis.relevance_score,
                }

                analyzed.append(analyzed_paper)

            except Exception as e:
                logger.warning(f"Failed to analyze paper {i}: {e}")
                # Add paper without analysis
                analyzed.append({
                    **paper,
                    "contribution": "Analysis failed",
                    "relevance_score": 3,  # Default medium relevance
                })

        # Sort by relevance score (highest first)
        analyzed.sort(key=lambda p: p.get("relevance_score", 0), reverse=True)

        logger.info(f"✓ Analyzed {len(analyzed)} papers")
        logger.info(f"  Relevance scores: {[p.get('relevance_score', 0) for p in analyzed[:5]]}")

        return {
            "analyzed_papers": analyzed,
            "current_step": "analyzed",
        }

    except Exception as e:
        logger.error(f"Error in analyze_papers_node: {e}")
        return {
            "error_count": state.get("error_count", 0) + 1,
            "current_step": "error_analysis",
        }


# ==================== Node 5: Build Citation Network ====================


def build_citation_network_node(state: ResearchState) -> NodeUpdate:
    """
    Construct citation graph from Semantic Scholar data.

    Builds a network of paper citations to identify:
    - Most influential papers
    - Citation relationships
    - Research clusters

    Args:
        state: Current research state

    Returns:
        State update with citation_network

    Example:
        >>> update = build_citation_network_node(state)
        >>> update["citation_network"]["node_count"]
        45
    """
    # Only use Semantic Scholar papers (they have paper IDs)
    ss_papers = [
        p for p in state["analyzed_papers"]
        if p.get("source") == "semantic_scholar" and p.get("id")
    ]

    logger.info(f"🕸️  Building citation network for {len(ss_papers)} Semantic Scholar papers")

    if len(ss_papers) < 2:
        logger.warning("Not enough Semantic Scholar papers for citation network")
        return {
            "citation_network": None,
            "current_step": "citations_built",
        }

    try:
        # Limit to top 10 papers by relevance to avoid API overload
        top_papers = ss_papers[:10]
        paper_ids = [p["id"] for p in top_papers]

        # Build citation graph
        graph = build_citation_graph(paper_ids, max_references=10, max_citations=10)

        # Find influential papers
        influential = find_influential_papers(paper_ids, top_k=5)

        # Add influential papers to graph metadata
        graph["most_influential"] = [
            (p["paper_id"], p["influence_score"])
            for p in influential
        ]

        logger.info(f"✓ Citation network built:")
        logger.info(f"  Nodes: {graph['node_count']}")
        logger.info(f"  Edges: {graph['edge_count']}")
        logger.info(f"  Most influential: {[p[0][:15] for p in graph['most_influential'][:3]]}")

        return {
            "citation_network": graph,
            "current_step": "citations_built",
        }

    except Exception as e:
        logger.error(f"Error in build_citation_network_node: {e}")
        return {
            "citation_network": None,
            "error_count": state.get("error_count", 0) + 1,
            "current_step": "citations_built",  # Continue even if citation building fails
        }


# ==================== Node 6: Synthesize Findings ====================


def synthesize_findings_node(state: ResearchState) -> NodeUpdate:
    """
    Generate structured research report from analyzed papers.

    Creates a comprehensive report with:
    - Executive summary
    - Key findings organized by theme
    - Methodological approaches
    - Research gaps
    - References

    Args:
        state: Current research state

    Returns:
        State update with final_report, key_findings, research_gaps

    Example:
        >>> update = synthesize_findings_node(state)
        >>> "# Research Report" in update["final_report"]
        True
    """
    logger.info(f"📝 Synthesizing findings from {len(state['analyzed_papers'])} papers")

    try:
        # Generate synthesis prompt
        prompt = get_synthesis_prompt(
            original_query=state["original_query"],
            analyzed_papers=state["analyzed_papers"],
            citation_network=state.get("citation_network"),
        )

        # Generate report
        logger.info("  Generating research report...")
        report = llm_client.generate(
            prompt=prompt,
            temperature=0.5,
        )

        # Extract key findings and gaps from report
        # (Simple extraction - could be made more sophisticated)
        key_findings = extract_findings_from_report(report)
        research_gaps = extract_gaps_from_report(report)

        logger.info(f"✓ Report generated:")
        logger.info(f"  Key findings: {len(key_findings)}")
        logger.info(f"  Research gaps: {len(research_gaps)}")
        logger.info(f"  Report length: {len(report)} characters")

        return {
            "final_report": report,
            "key_findings": key_findings,
            "research_gaps": research_gaps,
            "current_step": "synthesized",
        }

    except Exception as e:
        logger.error(f"Error in synthesize_findings_node: {e}")
        return {
            "final_report": "Error generating report",
            "error_count": state.get("error_count", 0) + 1,
            "current_step": "error_synthesis",
        }


# ==================== Node 7: Reflection ====================


def reflection_node(state: ResearchState) -> NodeUpdate:
    """
    Self-evaluate research quality and decide next steps.

    Evaluates:
    - Coverage: Are all aspects addressed?
    - Recency: Are papers recent enough?
    - Depth: Is there sufficient detail?

    Decides: COMPLETE (end) or CONTINUE (gather more papers)

    Args:
        state: Current research state

    Returns:
        State update with current_step ("complete" or "continue")

    Example:
        >>> update = reflection_node(state)
        >>> update["current_step"]
        "complete"
    """
    logger.info("🤔 Reflecting on research quality...")

    # Simple heuristics for now (could use LLM for more sophisticated reflection)
    papers_count = len(state["analyzed_papers"])
    high_relevance_count = sum(
        1 for p in state["analyzed_papers"]
        if p.get("relevance_score", 0) >= 4
    )

    logger.info(f"  Total papers: {papers_count}")
    logger.info(f"  High relevance (4-5): {high_relevance_count}")

    # Decision criteria
    if papers_count >= 10 and high_relevance_count >= 5:
        logger.info("✓ Research quality sufficient - COMPLETE")
        return {"current_step": "complete"}

    elif papers_count >= 20:
        # Even if relevance is low, stop after 20 papers to avoid excessive API calls
        logger.info("✓ Maximum papers reached - COMPLETE")
        return {"current_step": "complete"}

    elif state.get("error_count", 0) > 3:
        logger.warning("⚠️  Too many errors - COMPLETE")
        return {"current_step": "complete"}

    else:
        logger.info("→ Need more papers - CONTINUE")
        return {"current_step": "continue"}


# ==================== Helper Functions ====================


def extract_findings_from_report(report: str) -> List[str]:
    """
    Extract key findings from generated report.

    Looks for "Key Findings" section and extracts bullet points.

    Args:
        report: Generated markdown report

    Returns:
        List of key finding strings

    Example:
        >>> findings = extract_findings_from_report(report)
        >>> len(findings)
        5
    """
    findings = []

    # Simple pattern matching for bullet points under "Key Findings"
    lines = report.split('\n')
    in_findings_section = False

    for line in lines:
        # Check for section header
        if 'key finding' in line.lower() or 'main finding' in line.lower():
            in_findings_section = True
            continue

        # Stop at next header
        if in_findings_section and line.startswith('#'):
            break

        # Extract bullet points
        if in_findings_section and line.strip().startswith(('-', '*', '•')):
            finding = line.strip().lstrip('-*•').strip()
            if finding:
                findings.append(finding)

    # If no findings extracted, provide default
    if not findings:
        findings = ["See full report for detailed findings"]

    return findings[:7]  # Max 7 findings


def extract_gaps_from_report(report: str) -> List[str]:
    """
    Extract research gaps from generated report.

    Looks for "Research Gaps" section and extracts bullet points.

    Args:
        report: Generated markdown report

    Returns:
        List of research gap strings

    Example:
        >>> gaps = extract_gaps_from_report(report)
        >>> len(gaps)
        3
    """
    gaps = []

    # Pattern matching for research gaps section
    lines = report.split('\n')
    in_gaps_section = False

    for line in lines:
        # Check for section header
        if 'research gap' in line.lower() or 'future work' in line.lower():
            in_gaps_section = True
            continue

        # Stop at next header
        if in_gaps_section and line.startswith('#'):
            break

        # Extract bullet points
        if in_gaps_section and line.strip().startswith(('-', '*', '•')):
            gap = line.strip().lstrip('-*•').strip()
            if gap:
                gaps.append(gap)

    # Default if no gaps found
    if not gaps:
        gaps = ["See full report for research gaps"]

    return gaps[:5]  # Max 5 gaps
