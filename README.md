# One Agent Graph, N Orchestrators

A research-gap-analysis workflow whose topology lives in **one shared LaunchDarkly agent graph** (`intake → [approach-analyzer ∥ contradiction-detector] → gap-synthesizer`). Four frameworks — LangGraph, Strands, OpenAI Agents, Google ADK — all execute that same graph via a generic dispatcher, selected per request by an `orchestrator` flag. A LaunchDarkly experiment ranks them on **end-to-end latency and tokens** with the model held constant, while an LLM-judge **quality guardrail** confirms no framework degrades the output.

Sequel to [*Framework-Agnostic AI Swarms*](https://launchdarkly.com/docs/tutorials/ai-orchestrators).

## Setup

With [uv](https://docs.astral.sh/uv/) (recommended — installs from the lockfile, no venv to activate):

```bash
uv sync
cp .env.example .env   # fill in keys; set LD_PROJECT_KEY to your project
```

Then prefix the commands below with `uv run` (e.g. `uv run python orchestrators/verify_run.py langgraph`).

Or with pip:

```bash
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
```

With an activated venv, drop the `uv run` prefix and call `python` directly.

Needs Python 3.11+, a LaunchDarkly account with AgentControl, and `ANTHROPIC_API_KEY` (the pinned model). `OPENAI_API_KEY` / `GOOGLE_API_KEY` are only needed for the native-model bake-off.

## Run

1. **Create a LaunchDarkly project** (MCP / skill / UI) and set `LD_PROJECT_KEY` to its key.
2. **Bootstrap** the node configs, agent graph, `orchestrator` flag, and judge:
   ```bash
   uv run python scripts/launchdarkly/bootstrap.py config/graph_experiment_manifest.yaml
   ```
3. **Create the experiment** in the LaunchDarkly UI: treatment = `orchestrator` flag, randomization unit = `request`, primary metric = end-to-end graph latency, secondaries = the gap-quality judge (guardrail) + graph total tokens (the cost ranking at a pinned model). Start an iteration.
4. **Drive traffic.** Each run feeds a topic's **full** paper set through the graph (gap analysis needs every paper) and the judge scores the report. Two modes:
   - **Matched head-to-head** (`uv run python scripts/run_experiment.py --all-frameworks`): every topic runs through all four orchestrators once — apples-to-apples, read the per-framework means in the harness summary. Best for a small, fixed topic set.
   - **Randomized experiment** (default `uv run python scripts/run_experiment.py`): the `orchestrator` flag assigns each run one framework; the LD experiment attributes metrics per variation. Confidence bands tighten as you add **topics** (real traffic), so scale the query set for statistical power.
   - Smoke test: `uv run python orchestrators/verify_run.py langgraph` (one framework) or `verify_run.py all` (all four, with a pass/fail summary).
5. Read the per-variation winner in the UI (or the matched means in the harness output).

## Papers (the query set)

The experiment runs over the arXiv topic files in `data/` — auto-discovered, one file per
topic. The shipped set is six **complete niche literatures** (every paper arXiv has on the
topic in the last 3 years, no sampling):

| Topic | Query | Papers |
|---|---|---|
| Length generalization | `ti:"length generalization"` | 49 |
| Model collapse | `ti:"model collapse"` | 55 |
| Reward hacking | `ti:"reward hacking"` | 67 |
| Process reward models | `ti:"process reward model"` | 73 |
| Sycophancy | `ti:"sycophancy"` | 94 |
| Activation steering | `ti:"activation steering"` | 99 |

**The dataset IS the topic.** Gap analysis only works on a topic's *full* literature — a
capped sample of a broad query yields "gaps" that are artifacts of the sample. So never cap
results; instead pick a **narrow query** (title-phrase `ti:"..."` searches work well) whose
complete literature is run-sized (~10–100 papers). The downloader fetches all matches and
warns if the query is too broad.

To add or replace a topic (auto-discovered on the next run — no code change):

```bash
uv run python scripts/download_papers.py --query 'ti:"your niche topic"'
```

The agents analyze abstracts; the `fetch_paper` tool pulls a paper's full text on demand when
an abstract isn't enough.
