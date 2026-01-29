# AI Orchestrator Comparison

Comparative evaluation of AI orchestrator frameworks for multi-agent research gap analysis.

## Repository Structure

- **orchestrators/** - Framework-specific implementations (Strands, LangGraph, AutoGen, OpenAI Swarm)
- **shared/** - Code shared across all orchestrators (metadata, tools, prompts)
- **config/** - Static configuration files (agent configs, YAML manifests)
- **data/** - Input data (paper datasets)
- **scripts/** - Executable scripts (bootstrap, download, PDF generation)
- **results/** - Output files (reports, PDFs, metadata) organized by orchestrator

## Setup

### 1. Install Dependencies

```bash
# Create and activate virtual environment
python -m venv .venv
source .venv/bin/activate  # or `.venv\Scripts\activate` on Windows

# Install all dependencies
pip install -r requirements.txt
```

### 2. Configure Environment

Create `.env` file with your API keys:

```bash
# LaunchDarkly (required)
LD_SDK_KEY=sdk-key-xxxxx        # Your LaunchDarkly SDK key
LD_API_KEY=api-key-xxxxx        # Your LaunchDarkly API key
LAUNCHDARKLY_PROJECT_KEY=orchestrator-agents

# Model Provider API Keys (at least one required)
ANTHROPIC_API_KEY=sk-ant-xxxxx  # For Claude models via Anthropic
OPENAI_API_KEY=sk-xxxxx         # For GPT models via OpenAI

# AWS (optional - for Bedrock models)
AWS_PROFILE=your-profile
AWS_REGION=us-east-1
```

### 3. Bootstrap LaunchDarkly Agents

```bash
# Create AI agent configs in LaunchDarkly
python scripts/launchdarkly/bootstrap.py config/research_gap_manifest_robust.yaml
```

After bootstrapping, enable all 4 agents in the LaunchDarkly UI:
- paper-reader
- approach-analyzer
- contradiction-detector
- gap-synthesizer

### 4. Setup Metrics Dashboard (Optional)

```bash
# Configure LaunchDarkly metrics for monitoring
python scripts/launchdarkly/setup_metrics.py
```

### 5. Download Papers (Optional)

```bash
# Download papers from arXiv for analysis
python scripts/download_papers.py

# Or use the included test paper
# test_paper.json is already provided for quick testing
```

## Running Gap Analysis

All orchestrator runners accept **only** `--papers-json` as input and load all agents/tools from LaunchDarkly.

### With Strands

```bash
python orchestrators/strands/run_gap_analysis.py --papers-json data/gap_analysis_papers.json
```

### With LangGraph

```bash
python orchestrators/langgraph/run_swarm.py --papers-json data/gap_analysis_papers.json
```

### With AutoGen

```bash
python orchestrators/autogen/run_gap_analysis.py --papers-json data/gap_analysis_papers.json
```

### With OpenAI Swarm

```bash
python orchestrators/openai_swarm/run_gap_analysis.py --papers-json data/gap_analysis_papers.json
```

## Output Format

Each orchestrator generates:
- Text report: `results/<orchestrator>/YYYYMMDD_HHMMSS_gap_analysis_report.txt`
- Metadata JSON: `results/<orchestrator>/YYYYMMDD_HHMMSS_metadata.json`

### Converting Reports

Generate markdown from reports:
```bash
python scripts/convert_to_markdown.py
```

## Agent Architecture

All orchestrators use the same 4-agent pipeline:

1. **Paper Reading Specialist** - Reads abstracts from all papers
2. **Research Approach Analyzer** - Identifies methodological themes
3. **Contradiction Detection Specialist** - Finds conflicting findings
4. **Research Gap Synthesizer** - Synthesizes gaps and generates report

## Comparing Orchestrators

To compare different orchestration frameworks:

1. Run gap analysis with each orchestrator
2. Compare metadata JSON files (execution time, iterations, configurations)
3. Compare report quality (completeness, citation accuracy, gap identification)