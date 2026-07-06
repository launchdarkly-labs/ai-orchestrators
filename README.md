# One Agent Graph, N Orchestrators

A research-gap-analysis workflow whose topology lives in **one shared LaunchDarkly agent graph** (`intake → [approach-analyzer ∥ contradiction-detector] → gap-synthesizer`). Four frameworks — LangGraph, Strands, OpenAI Agents, Google ADK — all execute that same graph via a generic dispatcher, selected per request by an `orchestrator` flag. A LaunchDarkly experiment ranks them on **end-to-end latency and tokens** with the model held constant, while an LLM-judge **quality guardrail** confirms no framework degrades the output. Or flip on a [native-model bake-off](#native-model-bake-off-experiment-b) — each framework at its provider's best model — with no code change.

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

## Native-model bake-off (Experiment B)

The run above holds the model constant (`claude-sonnet-4-5` on every node) and varies only the
framework — an isolated read on orchestration overhead (**Experiment A**). **Experiment B** instead
lets each orchestrator run its provider's native model, ranking *each framework at its best*:

| orchestrator | model | provider |
|---|---|---|
| langgraph | claude-sonnet-4-5 | Anthropic (the base variation) |
| openai-agents | gpt-4o | OpenAI |
| google-adk | gemini-2.5-pro | Gemini |
| strands | claude-sonnet-4-5 (Bedrock) | Bedrock |

Routing is structural, not code. Each node config gets one variation per framework, and targeting
rules keyed on the `orchestrator` context attribute serve the matching model; the SDK derives the
provider from each variation's `modelConfigKey` (a model-catalog entry), so the runners route to the
right SDK unchanged. `langgraph` is served by the config fallthrough (the base Claude variation).

Set it up **after** `bootstrap.py`:

```bash
uv run python scripts/launchdarkly/setup_native_routing.py --dry-run   # preview, no writes
uv run python scripts/launchdarkly/setup_native_routing.py             # create variations + rules
```

Pick the models by editing `NATIVE_MODELS` at the top of the script. Each entry needs a
`modelConfigKey` that exists in your LaunchDarkly model catalog — list them with
`GET /api/v2/projects/{projectKey}/ai-configs/model-configs` — or the provider resolves empty and
the runner misroutes. The script is idempotent (re-run to change models) and applies to all four
node configs, so routing already works when you add `contradiction-detector` to the graph.

Credentials in `.env`: `OPENAI_API_KEY` (openai-agents), `GOOGLE_API_KEY` (google-adk / Gemini), and
AWS credentials for Bedrock (strands) — e.g. via `scripts/aws/` SSO. Bedrock serves newer Claude
models on-demand only through a cross-region inference profile; the strands runner prepends the
region geo prefix (`us.`/`eu.`/`apac.`) automatically. Confirm every route without spending tokens:

```bash
uv run python orchestrators/verify_run.py all
```

The experiment setup is unchanged (same `orchestrator` flag), but the ranking now compares whole
**orchestrator + native model** stacks — latency, tokens, and the quality judge reflect framework
*and* model together, not the framework in isolation.

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
