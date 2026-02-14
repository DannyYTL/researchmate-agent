# ResearchMate 🔬

**Multi-Step Research Agent with Tool Use for Academic Literature Analysis**

ResearchMate is an autonomous research agent that automates academic literature review using LangGraph orchestration, external API tools, and multi-step reasoning.

## 🎯 Features

- **🧠 Multi-Step Reasoning**: Decomposes research questions into focused sub-queries
- **🔍 Dual Search**: Searches Semantic Scholar + arXiv APIs in parallel
- **🕸️ Citation Analysis**: Builds citation networks to identify seminal papers
- **👤 Human-in-the-Loop**: Approve sub-queries before search execution
- **📊 Formal Evaluation**: Precision, recall, and coverage metrics
- **📄 Report Export**: Generate reports in Markdown, HTML, and PDF
- **💰 Zero Cost**: Uses DeepSeek R1 (free via OpenRouter) with Claude fallback

## 🏗️ Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                    ResearchMate Workflow                     │
└─────────────────────────────────────────────────────────────┘
                             │
                             ▼
                    ┌────────────────┐
                    │   Decompose    │  Break question into sub-queries
                    │     Query      │
                    └────────┬───────┘
                             │
                             ▼
                    ┌────────────────┐
                    │     Human      │  User approves/edits queries
                    │    Approval    │  (checkpoint-based)
                    └────────┬───────┘
                             │
                             ▼
                    ┌────────────────┐
                    │    Parallel    │  Search Semantic Scholar + arXiv
                    │     Search     │  (async, deduplicated)
                    └────────┬───────┘
                             │
                             ▼
                    ┌────────────────┐
                    │    Analyze     │  Extract findings, methods, results
                    │     Papers     │  (LLM-based extraction)
                    └────────┬───────┘
                             │
                             ▼
                    ┌────────────────┐
                    │  Build Citation│  Construct citation graph
                    │    Network     │  (identify influential papers)
                    └────────┬───────┘
                             │
                             ▼
                    ┌────────────────┐
                    │   Synthesize   │  Generate structured report
                    │    Findings    │  (with key findings & gaps)
                    └────────┬───────┘
                             │
                             ▼
                    ┌────────────────┐
                    │    Reflect     │  Self-evaluate quality
                    │                │  (decide: continue or end)
                    └────────┬───────┘
                             │
                    ┌────────┴────────┐
                    │                 │
                   END          Loop back to
                                Parallel Search
```

**Key Design Principles:**
- **Graph-based orchestration** (LangGraph) for explicit control flow
- **Typed state management** (TypedDict + reducers) for deterministic updates
- **Async/parallel execution** for API efficiency
- **Retry logic with exponential backoff** for resilience

## 📦 Installation

### Prerequisites

- Python 3.10 or higher
- OpenRouter API key (free tier: 50 requests/day) OR Anthropic API key

### Setup

1. **Clone the repository**
```bash
cd /Users/danny/Desktop/Internship/ResearchMate_agent
```

2. **Create virtual environment**
```bash
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
```

3. **Install dependencies**
```bash
pip install -r requirements.txt
```

4. **Configure API keys**
```bash
cp .env.example .env
# Edit .env and add your API keys
```

Required API keys:
- **OPENROUTER_API_KEY**: Get free key at [openrouter.ai/keys](https://openrouter.ai/keys)
- **ANTHROPIC_API_KEY** (optional): Fallback option at [console.anthropic.com](https://console.anthropic.com/settings/keys)

### Verify Setup

```bash
python examples/test_llm_client.py
```

Expected output:
```
✓ OpenRouter client initialized (DeepSeek R1)
✓ Anthropic client initialized (Claude Sonnet 4.5)
✓ Response: [Generated text about GNNs]
✓ Parsed structured output:
  1. Graph neural network architectures 2024-2026
  2. GNN applications in drug discovery
  ...
🎉 All tests passed! LLM client is ready.
```

## 🚀 Quick Start

### Basic Research Query

```python
from src.graph.workflow import create_research_graph

# Create the research workflow
graph = create_research_graph()

# Run a research query
result = graph.invoke({
    "original_query": "What are recent advances in graph neural networks?"
})

# Access the generated report
print(result["final_report"])
```

### Example Output

```markdown
# Recent Advances in Graph Neural Networks

## Executive Summary
This literature review analyzes 12 recent papers on graph neural networks...

## Key Findings
1. **Architecture Innovations**: GraphGPS and Graph Transformers combine...
2. **Scalability**: New sampling techniques enable training on billion-node graphs...
3. **Applications**: Significant progress in molecular property prediction...

## Research Gaps
- Limited evaluation on real-world heterogeneous graphs
- Few studies on GNN interpretability

## References
[1] Rampášek et al. (2024). Recipe for a General, Powerful, Scalable Graph Transformer...
```

## 📁 Project Structure

```
ResearchMate_agent/
├── src/
│   ├── graph/              # LangGraph orchestration
│   │   ├── state.py        # State schema (TypedDict)
│   │   ├── nodes.py        # Node functions (decompose, search, etc.)
│   │   └── workflow.py     # Graph construction
│   ├── tools/              # External API tools
│   │   ├── semantic_scholar_tool.py
│   │   ├── arxiv_tool.py
│   │   └── citation_analyzer.py
│   ├── prompts/            # LLM prompt templates
│   ├── utils/              # Utilities (retry, logging, formatting)
│   └── api/                # LLM client (DeepSeek + Claude)
├── examples/               # Demo scripts
├── tests/                  # Unit & integration tests
├── evaluations/            # Benchmark queries & metrics
└── visualizations/         # Citation graphs & report export
```

## 🧪 Development Status

**Week 1 Progress:**
- [x] Day 1-2: Project structure + LLM client
- [ ] Day 3-4: Tools layer (Semantic Scholar, arXiv)
- [ ] Day 5-6: Graph nodes + workflow
- [ ] Day 7: Initial testing

**Week 2 Goals:**
- [ ] Human-in-the-loop approval
- [ ] Citation network visualization
- [ ] Batch processing
- [ ] HTML/PDF export
- [ ] Evaluation framework
- [ ] Documentation + demo video

## 🛠️ Technology Stack

- **Framework**: LangGraph 0.3+ (agent orchestration)
- **LLM**: DeepSeek R1 (primary, free), Claude Sonnet 4.5 (fallback)
- **APIs**: Semantic Scholar, arXiv
- **Utilities**: httpx (async), tenacity (retry), networkx (graphs)
- **Testing**: pytest, pytest-asyncio, pytest-mock

## 📊 Evaluation Metrics

ResearchMate tracks the following metrics:

- **Precision**: % of retrieved papers relevant to query
- **Coverage**: % of expected research aspects addressed
- **Success Rate**: % of queries completed successfully
- **Latency**: Average execution time per query
- **Token Usage**: Total LLM tokens consumed

**Target Performance** (Week 2):
- Precision ≥ 70%
- Coverage ≥ 60%
- Success Rate ≥ 80%
- Latency < 60 seconds

## 🤝 Contributing

This is a research internship application project. Feedback and suggestions are welcome!

## 📄 License

MIT License - see LICENSE file for details

## 🙏 Acknowledgments

- Built with [LangGraph](https://github.com/langchain-ai/langgraph)
- Powered by [DeepSeek R1](https://github.com/deepseek-ai/DeepSeek-R1) and [Anthropic Claude](https://www.anthropic.com/claude)
- Data from [Semantic Scholar](https://www.semanticscholar.org/) and [arXiv](https://arxiv.org/)

## 📞 Contact

For questions or internship inquiries, please contact [your.email@example.com]

---

**Status**: 🚧 In Development (Week 1, Day 1 Complete)
