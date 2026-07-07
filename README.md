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
3. **Create the metric + experiment.** Add the custom dollar-cost metric (LD has no built-in cost metric — see [Cost & metrics](#cost--metrics)):
   ```bash
   uv run python scripts/launchdarkly/create_cost_metric.py
   ```
   Then create the experiment in the UI with treatment = `orchestrator` flag, control = `langgraph`, Bayesian. **Metrics are split by randomization unit** and an experiment's metrics must match its unit, so pick one framing:
   - **Cost + quality (recommended for the native bake-off):** randomization unit = **`user`**, primary = **AI graph cost (USD)**, guardrail = gap-quality judge, secondary = graph total tokens. *(cost / judge / tokens are all `user`-unit.)*
   - **Latency:** randomization unit = **`request`**, primary = **Graph latency**. *(latency / duration are `request`-unit; the judge/cost can't be in this one.)*

   Start an iteration.
4. **Drive traffic.** Each run feeds a topic's **full** paper set through the graph (gap analysis needs every paper) and the judge scores the report. Two modes:
   - **Matched head-to-head** (`uv run python scripts/run_experiment.py --all-frameworks`): every topic runs through all four orchestrators once — apples-to-apples, read the per-framework means in the harness summary. Best for a small, fixed topic set.
   - **Randomized experiment** (default `uv run python scripts/run_experiment.py`): the `orchestrator` flag assigns each run one framework; the LD experiment attributes metrics per variation. Confidence bands tighten as you add **topics** (real traffic), so scale the query set for statistical power.
   - Smoke test: `uv run python orchestrators/verify_run.py langgraph` (one framework) or `verify_run.py all` (all four, with a pass/fail summary).
5. Read the per-variation winner in the UI (or the matched means in the harness output).

## Native-model bake-off (Experiment B)

The run above holds the model constant (`claude-sonnet-4-5` on every node) and varies only the
framework — an isolated read on orchestration overhead (**Experiment A**). **Experiment B** instead
lets each orchestrator run its provider's native model, ranking *each framework + its model together*.
The shipped default is a **low-cost demo set** (cheapest recent tier per provider):

| orchestrator | model | provider |
|---|---|---|
| langgraph | claude-haiku-4-5 | Anthropic (direct API) |
| openai-agents | gpt-5-mini | OpenAI |
| google-adk | gemini-2.5-flash | Gemini |
| strands | claude-haiku-4-5 (Bedrock) | Bedrock |

langgraph and strands share Claude Haiku 4.5 (direct API vs Bedrock — a clean same-model
framework/runtime signal). For a production-grade comparison, edit `NATIVE_MODELS` to the flagships
(`Anthropic.claude-sonnet-5`, `OpenAI.gpt-5.1`, `Gemini.gemini-3-pro-preview`, and
`Bedrock.anthropic.claude-sonnet-5`).

**Cost** (this workflow is input-heavy — the full paper set is injected into every node, so ~110–140k
input + ~15–18k output tokens/run, plus a constant ~$0.14 Sonnet judge call):

| model set | per run | `--all-frameworks` (24 runs) | full randomized (90 runs) |
|---|---|---|---|
| demo (Haiku / GPT-5-mini / Gemini Flash) | ~$0.20–0.27 | ~$5–6 | ~$18–25 |
| flagship (Sonnet 5 / GPT-5.1 / Gemini 3 Pro) | ~$0.65–1.15 | ~$16–28 | ~$60–100 |

`gemini-2.5-flash` runs on the Gemini **free tier** — no Google billing needed for the demo. Routing
is structural, not code. Each node config gets one variation per framework, and targeting rules keyed
on the `orchestrator` context attribute serve the matching model; the SDK derives the provider from
each variation's `modelConfigKey` (a model-catalog entry), so the runners route to the right SDK
unchanged. All four frameworks get an explicit variation + rule; the config **fallthrough** stays on
the pinned `claude-sonnet-4-5`, so Experiment A (no `orchestrator` attribute) is untouched.

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
*and* model together, not the framework in isolation. The setup script also attaches the gap-quality
judge to every per-framework synthesizer variation (the manifest attaches it only to the base), so
each arm gets a quality score.

### Switching between Experiment A (pinned model) and Experiment B (native models)

The same `setup_native_routing.py` script toggles the two experiment shapes — no variation rewrites,
fully reversible:

```bash
# Experiment B — each framework on its own native model (per-framework targeting rules)
uv run python scripts/launchdarkly/setup_native_routing.py

# Experiment A — pin ALL frameworks to one model, isolating orchestration overhead
uv run python scripts/launchdarkly/setup_native_routing.py --pin anthropic   # --dry-run to preview
```

`--pin <suffix>` clears the per-framework rules and points every node config's **fallthrough** at the
`*-<suffix>` variation, so every `orchestrator` value serves that one model. The per-framework
variations are left untouched, so re-running **without** `--pin` restores Experiment B.

Use **`--pin anthropic`** (Claude Haiku 4.5). It has to be the Anthropic variation: the LangGraph
runner only has `langchain-anthropic` installed (no LiteLLM), so it can't run GPT/Gemini — pinning to
`gpt`/`gemini`/`bedrock` would break the langgraph arm. In Experiment A the quality judge should read
roughly flat across arms (same model), so **cost and latency — framework overhead at a fixed model —
are the differentiators.**

After switching either way, **restart the experiment iteration** so the two shapes' data don't mix.

## Cost & metrics

LaunchDarkly's auto-generated AI metrics are token/duration only — **there is no built-in dollar-cost
metric**, and the `get-ai-config-metrics` REST endpoint reports cost only **per config (all variations
combined)**, never per-variation, and isn't reachable through the SDK. So for a per-orchestrator cost
ranking, the harness computes each run's **graph cost** (node tokens × the served model's catalog
price) and emits it as a custom metric, `ai-graph-cost-usd`:

```bash
uv run python scripts/launchdarkly/create_cost_metric.py      # one-time: create the metric
# run_experiment.py then emits it every run; results CSV gets a cost_usd column
uv run python scripts/launchdarkly/fetch_costs.py --hours 24   # read LD's own per-config cost (Insights)
```

Raw token counts are **not** a fair cost proxy across the different-model arms (per-token prices
differ), so use the dollar metric. **Metric randomization units are split**, and an experiment can
only include metrics matching its unit:

| metric | unit | use as |
|---|---|---|
| AI graph cost (USD) `ai-graph-cost-usd` | `user` | primary (cost bake-off) |
| Gap-quality judge | `user` | guardrail |
| Graph total tokens | `user` | secondary |
| Graph latency / duration | `request` | primary (separate latency experiment) |

So a **cost + quality** experiment randomizes by `user`; a **latency** experiment randomizes by
`request`. They can't be combined in one experiment.

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
