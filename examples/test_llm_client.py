"""
Test script to verify LLM client setup.

This script tests both basic generation and structured output.
"""

import sys
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from pydantic import BaseModel, Field
from src.api.client import llm_client
from src.utils.logger import setup_logger

logger = setup_logger(__name__)


class SubQueryList(BaseModel):
    """Example schema for structured output."""

    queries: list[str] = Field(
        description="List of 3-5 focused sub-queries",
        min_length=3,
        max_length=5,
    )


def test_basic_generation():
    """Test basic text generation."""
    logger.info("=" * 60)
    logger.info("TEST 1: Basic Text Generation")
    logger.info("=" * 60)

    prompt = "Explain what a graph neural network is in 2 sentences."

    try:
        response = llm_client.generate(prompt)
        logger.info(f"\n✓ Response:\n{response}\n")
        return True
    except Exception as e:
        logger.error(f"✗ Basic generation failed: {e}")
        return False


def test_structured_output():
    """Test structured JSON output."""
    logger.info("=" * 60)
    logger.info("TEST 2: Structured Output Generation")
    logger.info("=" * 60)

    prompt = """
    Break down the research question "What are recent advances in graph neural networks?"
    into 3-5 focused sub-queries for academic literature search.
    """

    try:
        result = llm_client.generate_structured(prompt, SubQueryList)
        logger.info(f"\n✓ Parsed structured output:")
        logger.info(f"  Number of queries: {len(result.queries)}")
        for i, query in enumerate(result.queries, 1):
            logger.info(f"  {i}. {query}")
        logger.info("")
        return True
    except Exception as e:
        logger.error(f"✗ Structured generation failed: {e}")
        return False


def test_stats():
    """Display usage statistics."""
    logger.info("=" * 60)
    logger.info("Usage Statistics")
    logger.info("=" * 60)

    stats = llm_client.get_stats()
    logger.info(f"\nPrimary model: {stats['primary_model']}")
    logger.info(f"Primary calls: {stats['primary_calls']}")
    logger.info(f"Fallback calls: {stats['fallback_calls']}")
    logger.info(f"Total calls: {stats['total_calls']}")
    logger.info(f"Total tokens: {stats['total_tokens']}")
    logger.info(f"Errors: {stats['errors']}\n")


def main():
    """Run all tests."""
    logger.info("\n🧪 Testing ResearchMate LLM Client\n")

    # Check environment
    import os

    has_openrouter = bool(os.getenv("OPENROUTER_API_KEY"))
    has_anthropic = bool(os.getenv("ANTHROPIC_API_KEY"))

    logger.info("Environment check:")
    logger.info(f"  OPENROUTER_API_KEY: {'✓ Set' if has_openrouter else '✗ Not set'}")
    logger.info(f"  ANTHROPIC_API_KEY: {'✓ Set' if has_anthropic else '✗ Not set'}\n")

    if not has_openrouter and not has_anthropic:
        logger.error("❌ No API keys found. Please set at least one:")
        logger.error("   - OPENROUTER_API_KEY (for free DeepSeek access)")
        logger.error("   - ANTHROPIC_API_KEY (for Claude fallback)")
        logger.error("\nCopy .env.example to .env and add your keys.")
        sys.exit(1)

    # Run tests
    results = []
    results.append(("Basic Generation", test_basic_generation()))
    results.append(("Structured Output", test_structured_output()))

    # Show stats
    test_stats()

    # Summary
    logger.info("=" * 60)
    logger.info("Test Summary")
    logger.info("=" * 60)

    for test_name, passed in results:
        status = "✓ PASS" if passed else "✗ FAIL"
        logger.info(f"{status} - {test_name}")

    passed_count = sum(1 for _, passed in results if passed)
    total_count = len(results)

    logger.info(f"\nResult: {passed_count}/{total_count} tests passed\n")

    if passed_count == total_count:
        logger.info("🎉 All tests passed! LLM client is ready.\n")
        return 0
    else:
        logger.error("❌ Some tests failed. Check the errors above.\n")
        return 1


if __name__ == "__main__":
    sys.exit(main())
