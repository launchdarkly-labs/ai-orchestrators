# One Agent Graph, Every Variable Behind a Flag

A research-gap-analysis workflow (`intake → [approach-analyzer ∥ contradiction-detector] → gap-synthesizer`) whose topology, prompts, models, tools, and judge all live in **one LaunchDarkly agent graph**. An `orchestrator` routing flag selects the arm per request; a LaunchDarkly experiment ranks the arms; an LLM-judge quality score guards them. Three experiments, each isolating one layer of the agent stack:

| | varies | holds constant | the decision it answers |
|---|---|---|---|
| **A** | framework (node execution) | graph, walk, judge, **model** | **Migration**: "what would swapping frameworks cost?" — measures the framework tax (agent loop + adapter). Small tax ⇒ the choice is reversible |
| **B** | framework + its native model | graph, walk, judge | **Adoption**: "which stack do we build on?" — each vendor's happy path, whole-bundle |
| **C** | the **orchestrator** (who walks) | graph, judge, model-per-pair | **Architecture**: "who owns the traversal — our dispatcher, the framework's engine, or a managed runner?" |

The suite hangs on one intentional design decision: a shared ~100-line **dispatcher** (`orchestrators/dispatcher.py`) owns the walk in A/B — holding traversal byte-identical so framework execution paths compare cleanly — then serves as the **control arm** when C makes the walk itself the treatment. An orchestrator is really a *context manager*: what it carries between nodes is the lever C measures, and on this input-heavy workload it can swing the token bill more than the framework tax.

Sequel to [*Framework-Agnostic AI Swarms*](https://launchdarkly.com/docs/tutorials/ai-orchestrators).

## Setup

```bash
uv sync                # or: python -m venv .venv && source .venv/bin/activate && pip install -r requirements.txt
cp .env.example .env   # fill in keys; set LD_PROJECT_KEY to your project
```

Needs Python 3.11+, a LaunchDarkly account with AgentControl, and `ANTHROPIC_API_KEY`. For Experiment B/C native models also: `OPENAI_API_KEY`, `GOOGLE_API_KEY`, AWS credentials for Bedrock (e.g. `scripts/aws/` SSO). Prefix commands with `uv run` (or activate the venv and drop it).

## Run

1. **Create an LD project**, set `LD_PROJECT_KEY`.
2. **Bootstrap** node configs, graph, `orchestrator` flag, judge:
   `python scripts/launchdarkly/bootstrap.py config/graph_experiment_manifest.yaml`
3. **Metric + experiment**: `python scripts/launchdarkly/create_cost_metric.py`, then create the experiment in the UI (treatment = `orchestrator` flag, control = `langgraph`, Bayesian). Pick ONE randomization unit ([why](#cost--metrics)): **`user`** → primary = AI graph cost (USD), guardrail = gap-quality judge, secondary = tokens; or **`request`** → primary = graph latency. Start an iteration.
4. **Drive traffic** (each run feeds a topic's FULL paper set through the graph):
   - Randomized (default): `python scripts/run_experiment.py` — the flag splits arms; add topics for statistical power.
   - Matched head-to-head: `--all-frameworks` (four framework arms) or `--arms <arm ...>` (any arm list).
   - Smoke test: `python orchestrators/verify_run.py all` (frameworks) / `c` (orchestrators) / `<arm>`.
5. Read the per-variation winner in the LD UI (or the harness's per-arm means / results CSV).

## Experiment B — native models

`setup_native_routing.py` (run after bootstrap; idempotent) adds one variation per provider to every **node config** plus targeting rules on the `orchestrator` context attribute. Provider is derived from each variation's `modelConfigKey` (must exist in your LD model catalog). Fallthrough stays on base `claude-sonnet-4-5`. Default demo roster (edit `NATIVE_MODELS` in the script for flagships):

| arm | model | provider |
|---|---|---|
| langgraph | claude-haiku-4-5 | Anthropic (direct API) |
| openai-agents | gpt-5.4-mini | OpenAI |
| google-adk | gemini-3-flash-preview | Gemini (free tier OK) |
| strands | amazon nova-2-lite | Bedrock (geo prefix auto-added) |

```bash
python scripts/launchdarkly/setup_native_routing.py --dry-run   # preview
python scripts/launchdarkly/setup_native_routing.py             # variations + rules + judge attachment
```

**Cost** (~110–140k input + ~15–18k output tokens/run + ~$0.14 judge): demo set ≈ $0.20–0.27/run (≈$5–6 per 24-run matched sweep); flagships ≈ $0.65–1.15/run.

### Toggling A ↔ B

```bash
python scripts/launchdarkly/setup_native_routing.py                  # B: per-arm native models
python scripts/launchdarkly/setup_native_routing.py --pin anthropic  # A: ONE model on every arm
```

`--pin` clears the rules and points every node's fallthrough at the `*-anthropic` variation (must be Anthropic — the langgraph arms have only `langchain-anthropic`); re-run without `--pin` to restore B. **Restart the experiment iteration after any switch** so shapes' data don't mix.

## Experiment C — orchestrator bake-off

Every multi-agent app makes two silent decisions, usually inherited from a framework's
quickstart: **context strategy** (what each agent sees — a curated fresh input, or the
accumulating transcript) and **routing authority** (who picks the path — the drawn graph, or
the model at runtime). Context strategy is directly your token bill and compounds with graph
size; routing authority decides whether the drawn edges are a contract or a suggestion. This
experiment prices both: same drawn graph, same judge, but each framework's **native
orchestration engine** owns the walk. Every input still comes from LaunchDarkly.

**The arms as a 2×2** (★ = dispatcher control):

| | **structural routing** (drawn edges execute) | **model-decided routing** (edges are options) |
|---|---|---|
| **curated context** | ★ dispatcher (all four framework arms) · `strands-native` | *(empty — no framework ships this)* |
| **accumulating context** | `langgraph-native` · `google-adk-native` | `openai-agents-native` (linear chain) |

| arm | orchestrator | routing | context between nodes |
|---|---|---|---|
| dispatcher arms *(controls)* | shared dispatcher | structural, ALL-join | fresh: papers + predecessor outputs |
| `langgraph-native` | LangGraph `StateGraph` | structural, ALL-join | one accumulating message state (full transcripts) |
| `strands-native` | Strands `Graph` | structural, **ANY-trigger** | task + dependency-output digest (≈ dispatcher's) |
| `openai-agents-native` | Agents SDK **handoffs** | **model-decided**, sequential | can't traverse the diamond — runs a **linear chain** (see below) |
| `google-adk-native` | ADK workflow agents | structural, level barriers | one shared session (accumulates) |

**How to read it** — the same drawing means different things to different engines: ALL-join
(dispatcher, LangGraph `StateGraph`) vs ANY-trigger re-execution (Strands fires a node when
*any* predecessor completes) vs level barriers (ADK) vs model-decided handoffs (OpenAI). The
structural engines walk the diamond as drawn; a drawn graph is a *contract* only under
structural orchestration.

**The handoff exception (OpenAI).** Handoffs are sequential and model-decided, so they can't
express the diamond's parallel fan-out at all — the arm bailed at the entry node (and so did
LaunchDarkly's own managed handoff runner, so it's the paradigm, not the runner). Making
handoffs walk took three things, all config: (1) a **linear-chain graph**
(`research-gap-graph-linear`, same node configs), (2) handoff-aware prompts authored in the
OpenAI `*-gpt` node variations (not in code), and (3) a **message-carrying handoff** — the
transfer tool requires the agent's findings as its payload, fusing "do the work" and "hand
off" into one act. With all three, the arm walks the chain reliably and scores competitively
(~0.73 gap-quality). Which graph each arm reads is routed by a separate **`graph-key` flag**
(targets the `orchestrator` attribute: `openai-agents-native` → linear, everyone else →
diamond), evaluated per request during the same experiment.

Setup (all config, additive — run after `setup_native_routing.py`):

```bash
python scripts/launchdarkly/add_experiment_c_arms.py          # add the *-native arm values to the orchestrator flag
python scripts/launchdarkly/bootstrap_linear_graph.py         # the linear chain graph (reuses node configs)
python scripts/launchdarkly/bootstrap_openai_handoff_prompts.py  # handoff prompts into *-gpt variations + judge
python scripts/launchdarkly/bootstrap_graph_key_flag.py       # graph-key flag: routes openai-agents-native → linear
python orchestrators/verify_run.py c                          # smoke each walk (no experiment needed)
```

Then run it **as an experiment** (capture-or-don't-run): add the `*-native` arms as treatments
on the `orchestrator` experiment (control = `langgraph`, unit = `user`, primary = cost,
guardrail = judge), **start a fresh iteration**, and drive randomized traffic:

```bash
python scripts/run_experiment.py --runs-per-category 5   # flag-assigned; every run is an exposure
```

(`--arms`/`--all-frameworks` matched mode still exists for offline smoke-grade CSV reads, but
it bypasses the flag — zero exposures, invisible to the experiment.)

## Cheat sheet

**The layer cake** — everything is a harness around the layer below it; each experiment
varies exactly one layer:

| layer | job | in this repo | varied by |
|---|---|---|---|
| model API | generate | Claude / GPT / Gemini / Nova | **B** |
| framework | agent loop for ONE node: prompts, tool calls, retries | LangGraph, Strands, OpenAI Agents SDK, Google ADK | **A** |
| **orchestrator** | the walk: who runs, what they see, who routes | dispatcher · native engines · LD managed runner | **C** |
| measurement | randomize, judge, price, record | `run_experiment.py` + the LD experiment | — |

**Arm naming** — the `orchestrator` flag value decodes as *who walks*:

| value pattern | who walks the graph | example |
|---|---|---|
| plain (`langgraph`, `strands`, …) | **our dispatcher**; the framework only executes nodes | `google-adk` |
| `*-native` | **that framework's own engine** | `strands-native` (Strands `Graph`) |
| `langgraph-managed` | **LaunchDarkly's SDK runner** (`create_agent_graph().run()`) — zero orchestration code | — |

**One drawing, many compilers** — every arm reads the same LD graph per request; each
engine executes it with its own semantics:

| engine | multi-input node | parallel fan-out | drawn edges are | quirks |
|---|---|---|---|---|
| dispatcher | waits for ALL preds | yes (`asyncio.gather`) | contract | fails loudly on cycles |
| LangGraph `StateGraph` | ALL (list-edge join) | yes (supersteps) | contract | join must be explicit or it fires per edge |
| Strands `Graph` | fires on ANY pred | yes | contract, OR-interpreted | re-executes multi-input nodes |
| ADK workflow agents | level barrier | per level | contract + extra sync | reshaped into Sequential/Parallel levels |
| OpenAI handoffs | n/a — one agent at a time | **no** | **options** (model decides) | can't walk the diamond — runs the linear chain with a message-carrying handoff |

**Run modes** — capture-or-don't-run:

| mode | command | captured in the LD experiment? | allowed use |
|---|---|---|---|
| randomized | `run_experiment.py` (no overrides) | **yes** — flag assigns arms, every run is an exposure | the real experiments |
| matched | `--arms` / `--all-frameworks` | **no** — flag bypassed, CSV only | offline smoke-grade reads only |
| smoke | `verify_run.py <arm>` / `c` / `all` | no (metrics flow, no exposures) | route/walk validation |

**What lives where:**

| from LaunchDarkly (edit in UI, no deploy) | from code |
|---|---|
| topology (nodes + edges), per-node model, prompt, tools, judge attachment, routing (`orchestrator` flag → arm, `graph-key` flag → graph shape, targeting rules → per-node model), all metric trackers | the walk implementations (dispatcher + runners), tool *bodies* (`shared/tools`), the harness, the papers |

Metric units: cost / judge / tokens randomize by `user`; latency by `request` — one unit per
experiment, so cost+quality and latency are separate experiments (see [Cost & metrics](#cost--metrics)).

**Model modes** (same `setup_native_routing.py` toggle; the `-native` arms inherit their framework's model, so `strands-native` serves **Nova** like `strands`): **pairs** (default — each arm on its native model, so every dispatcher-vs-native pair holds the model constant) or **`--pin anthropic`** (one model on every arm, for cross-family comparability). Metric honesty: the OpenAI result reports graph-level tokens only (no per-node attribution); ADK reports no per-node duration — gaps stay unreported, not faked.

## Cost & metrics

LD's auto AI metrics are token/duration only (no dollar cost, and the REST cost endpoint isn't per-variation), so the harness computes each run's graph cost (node tokens × the served model's catalog price) and emits custom metric **`ai-graph-cost-usd`** — a fair cross-model primary where raw tokens aren't. Metric randomization units are split, and an experiment's metrics must match its unit:

| metric | unit |
|---|---|
| `ai-graph-cost-usd`, gap-quality judge, graph total tokens | `user` |
| graph latency / duration | `request` |

So cost + quality live in a `user`-randomized experiment; latency needs a separate `request`-randomized one.

## Papers (the query set)

Topic files in `data/` are auto-discovered (one file = one topic). Shipped: six complete niche literatures, 49–99 papers each (length generalization, model collapse, reward hacking, process reward models, sycophancy, activation steering). **The dataset IS the topic** — gap analysis needs a topic's *full* literature; a capped sample yields artifact "gaps". Pick narrow `ti:"..."` queries whose complete literature is run-sized (~10–100 papers):

```bash
python scripts/download_papers.py --query 'ti:"your niche topic"'
```

Agents analyze abstracts; the `fetch_paper` tool pulls full text on demand.
