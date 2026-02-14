"""
Basic research demo for ResearchMate.

This script demonstrates end-to-end research workflow:
1. Decompose query into sub-queries
2. Search academic databases
3. Analyze papers
4. Build citation network
5. Generate research report

Usage:
    python examples/basic_research.py
    python examples/basic_research.py --query "your research question"
    python examples/basic_research.py --automated  # Skip human approval
"""

import sys
import argparse
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.graph.workflow import run_research
from src.utils.logger import setup_logger

logger = setup_logger(__name__)


def save_report(report: str, filename: str = "research_report.md"):
    """
    Save research report to file.

    Args:
        report: Generated markdown report
        filename: Output filename

    Returns:
        Path to saved file
    """
    output_path = Path("outputs") / filename
    output_path.parent.mkdir(exist_ok=True)

    with open(output_path, "w") as f:
        f.write(report)

    logger.info(f"📄 Report saved to: {output_path}")
    return output_path


def display_summary(state: dict):
    """
    Display research summary.

    Args:
        state: Final research state
    """
    print("\n" + "=" * 70)
    print("📊 RESEARCH SUMMARY")
    print("=" * 70)

    print(f"\n🔍 Original Query:")
    print(f"   {state['original_query']}")

    print(f"\n📝 Sub-Queries Generated:")
    for i, query in enumerate(state.get('sub_queries', []), 1):
        print(f"   {i}. {query}")

    print(f"\n📚 Papers Found:")
    print(f"   Total: {len(state.get('papers', []))}")
    print(f"   Analyzed: {len(state.get('analyzed_papers', []))}")

    # Show top papers
    analyzed = state.get('analyzed_papers', [])
    if analyzed:
        print(f"\n🌟 Top 3 Most Relevant Papers:")
        for i, paper in enumerate(analyzed[:3], 1):
            print(f"\n   {i}. {paper.get('title', 'Unknown')}")
            print(f"      Authors: {', '.join(paper.get('authors', [])[:2])}")
            print(f"      Year: {paper.get('year', 'N/A')}")
            print(f"      Relevance: {paper.get('relevance_score', 0)}/5")
            print(f"      Contribution: {paper.get('contribution', 'N/A')[:100]}...")

    # Citation network
    citation_network = state.get('citation_network')
    if citation_network:
        print(f"\n🕸️  Citation Network:")
        print(f"   Nodes: {citation_network.get('node_count', 0)}")
        print(f"   Edges: {citation_network.get('edge_count', 0)}")

    # Key findings
    key_findings = state.get('key_findings', [])
    if key_findings:
        print(f"\n💡 Key Findings:")
        for i, finding in enumerate(key_findings[:5], 1):
            print(f"   {i}. {finding[:100]}...")

    # Research gaps
    research_gaps = state.get('research_gaps', [])
    if research_gaps:
        print(f"\n🔬 Research Gaps:")
        for i, gap in enumerate(research_gaps[:3], 1):
            print(f"   {i}. {gap[:100]}...")

    # Execution stats
    print(f"\n⏱️  Execution Time: {state.get('execution_time', 0):.1f} seconds")
    print(f"❌ Errors: {state.get('error_count', 0)}")

    print("\n" + "=" * 70)


def main():
    """Main execution function."""
    parser = argparse.ArgumentParser(
        description="ResearchMate: Multi-Step Research Agent",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Interactive mode with default query
  python examples/basic_research.py

  # Custom query with human approval
  python examples/basic_research.py --query "recent advances in graph neural networks"

  # Automated mode (no human interaction)
  python examples/basic_research.py --automated --query "transformers for computer vision"

  # Save report with custom filename
  python examples/basic_research.py --output my_research.md
        """
    )

    parser.add_argument(
        "--query", "-q",
        type=str,
        default="What are recent advances in graph neural networks for drug discovery?",
        help="Research question to investigate"
    )

    parser.add_argument(
        "--automated", "-a",
        action="store_true",
        help="Run in automated mode (skip human approval)"
    )

    parser.add_argument(
        "--output", "-o",
        type=str,
        default="research_report.md",
        help="Output filename for research report"
    )

    parser.add_argument(
        "--no-save",
        action="store_true",
        help="Don't save report to file (display only)"
    )

    args = parser.parse_args()

    # Display configuration
    print("\n🔬 ResearchMate - Multi-Step Research Agent")
    print("=" * 70)
    print(f"Query: {args.query}")
    print(f"Mode: {'Automated' if args.automated else 'Interactive (HITL)'}")
    print("=" * 70)

    try:
        # Run research
        result = run_research(
            query=args.query,
            enable_hitl=not args.automated,
            verbose=True
        )

        # Display summary
        display_summary(result)

        # Display report
        print("\n📄 FULL RESEARCH REPORT:")
        print("=" * 70)
        print(result['final_report'])
        print("=" * 70)

        # Save report
        if not args.no_save:
            report_path = save_report(result['final_report'], args.output)
            print(f"\n✅ Report saved to: {report_path}")

        return 0

    except KeyboardInterrupt:
        print("\n\n⚠️  Research interrupted by user")
        return 1

    except Exception as e:
        print(f"\n\n❌ Error: {e}")
        import traceback
        traceback.print_exc()
        return 1


if __name__ == "__main__":
    sys.exit(main())
