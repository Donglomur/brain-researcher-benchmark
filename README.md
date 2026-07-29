# brain-researcher-benchmark

A small benchmark of **un-cued scientific judgement** for coding/agent systems, in
[Harbor / terminal-bench](https://github.com/harbor-framework/harbor) task format. Each task is a real neuroimaging analysis a capable agent can *run*
correctly — yet frontier agents still **fail** it, because the honest answer needs a
piece of scientific judgement nobody told them to apply.

## The finding that drives it

Frontier agents (GPT-5.5, Claude Opus) can fetch the data, run the pipeline, and get
the numbers right. Where they fall down is **judgement that isn't cued by the prompt**:
volunteering the robustness check, the confound control, or the lever that decides
whether a published claim actually holds. A task "works" when:

- a correct **reference solution solves it** — oracle reward **1.0** (the task is real and doable), **and**
- **≥2 frontier agent families fail it** (k≥3 runs each), for the *right* (judgement) reason, hand-re-scored.

So the value is the gap, not the compute. See `INTERN_GUIDE.md` for the full
definition-of-done and the failure-axis taxonomy.

> ⚠️ **This repo is public, including reference solutions and the failure axis of each
> task.** That is deliberate — it's meant as a methods showcase — but it also means these
> specific tasks are "burned" as a held-out test (future models may train on the answers).
> Treat them as **worked examples of the method**, and author fresh tasks (using the
> skill below) for any real evaluation.

## The three example tasks

| Task | Paper | Failure axis | The un-cued move | Oracle | Frontier agents |
|---|---|---|---|---|---|
| **GRADIENT-001** | Vos de Wael 2020 / Margulies 2016 (connectivity gradients) | **over-claim** | the headline "apex" isn't robustly reproducible → the honest answer is a rigor/characterise verdict, not a confirmation | 1.0 | GPT-5.5 FAIL 0.46 · Claude FAIL 0.37 |
| **SOCIALBRAIN-001** | Richardson 2018 Nat Commun (ToM–pain anticorrelation) | **confident-refutation** | the effect reproduces **only under global-signal regression** (−0.07 n.s. → −0.34); a flat "not found" is wrong | 1.0 | both FAIL (never try the GSR lever) |
| **DEVCONN-001** | Fair 2009 PLoS Comput Biol (local→distributed development) | **wrong-cause** | the developmental effect is real but **collapses under head-motion control** (kids move ~2×); the confound must be volunteered | 1.0 | GPT-5.5 4/4 FAIL · Claude 3/3 FAIL |

All three run on the same public dataset (OpenNeuro `ds000228`, via nilearn-pinned
derivatives) so the environments are cheap to build. Measured difficulty (hand re-scored,
with honesty notes on run counts and verifier hardening): **[`RESULTS.md`](RESULTS.md)**.

## Task layout (Harbor)

Every task is a self-contained directory:

```
TASK-NAME/
├── instruction.md        # what the agent sees — NEVER names the failure axis (un-cued)
├── task.toml             # id, difficulty, timeouts, resources, dataset, source paper
├── environment/Dockerfile
├── solution/             # reference (oracle): solve.sh + compute.py
└── tests/                # test.sh + test_outputs.py — the verifier
```

## How to run

Install the harness ([harbor-framework/harbor](https://github.com/harbor-framework/harbor)).

**Shortcut** — let the helper generate the right commands (auth + `~/nilearn_data`
cache mount + `k` baked in), from the repo root:

```bash
./tools/run_task.sh DEVCONN-001            # print oracle + GPT-5.5 + Claude commands
./tools/run_task.sh DEVCONN-001 oracle     # just one agent
./tools/run_task.sh DEVCONN-001 all --run  # actually run them
```

Or spell them out yourself (`-k` = attempts per trial, the k≥3 knob):

```bash
# reference solution — must score reward 1.0
harbor run -p GRADIENT-001 -a oracle -o jobs -k 1 -y

# frontier agents — expected to FAIL for the judgement reason (run k≥3, hand re-score)
harbor run -p GRADIENT-001 -a codex       -m gpt-5.5 --ak reasoning_effort=xhigh -o jobs -k 3 -y
harbor run -p GRADIENT-001 -a claude-code -m claude-opus-4-8                      -o jobs -k 3 -y
```

Notes:
- **Agent auth** (see [`CONTRIBUTING.md`](CONTRIBUTING.md) for details): `claude-code` reads
  `CLAUDE_CODE_OAUTH_TOKEN` from host env only (or run `python tools/patch_harbor_oauth.py`
  once); `codex` with a ChatGPT login needs `--ae CODEX_FORCE_AUTH_JSON=1`. A `0.0` that
  finishes in seconds is an auth/quota artifact, **not** a task FAIL.
- Tasks fetch data at runtime (`allow_internet = true`). For repeat local runs you can
  bind-mount a warm `$HOME/nilearn_data` to skip the download (see the skill); keep that
  a local flag, never committed — external runners still fetch.
- A "pass" for a frontier agent means it *volunteered the judgement*, not that a keyword
  matched. Read the run that **looks** like a pass most carefully (see the verifier
  false-positive lesson in the skill).

## Paper triage and authoring new tasks

Paper intake uses two separate skills:

- **`tb-science-task-authoring`** decides whether a paper can become a fair,
  sufficiently difficult frozen benchmark, then guides task authoring.
- **`self-evolvable-question-design`** independently decides whether the paper can
  anchor a capability-open family with an executable oracle, measured headroom,
  and a concrete freshness or ratchet mechanism.

They consume the same immutable `PaperEvidencePacket`, defined once under
[`contracts/curation/`](contracts/curation/), but produce separate artifacts. The same paper
may support a frozen benchmark, an evolvable family, both, or neither.

For a new coding agent:

```bash
git clone https://github.com/brain-researcher/brain-researcher-benchmark.git
cd brain-researcher-benchmark
mkdir -p ~/.claude/skills/tb-science-task-authoring
mkdir -p ~/.claude/skills/self-evolvable-question-design
cp .claude/skills/tb-science-task-authoring/SKILL.md ~/.claude/skills/tb-science-task-authoring/
cp .claude/skills/self-evolvable-question-design/SKILL.md ~/.claude/skills/self-evolvable-question-design/
```

Run a durable scheduler/controller outside the model session. For each leased job, fill
[`TOPIC_TRIAGE_CONTROLLER_PROMPT.md`](TOPIC_TRIAGE_CONTROLLER_PROMPT.md) with one immutable
`CurationJob` and start one clean worker session. The worker processes exactly that stage,
returns one `StageResult`, and stops.

The authority boundary is deliberate:

- the scheduler selects work, owns leases/retries, validates results, appends immutable
  `CurationTransition` records, and updates the tracker projection;
- the worker does scientific work for one supplied job, but does not select a topic, claim
  another job, write the tracker, append transitions, or declare a release;
- independent adjudication is the only path to `released`.

The benchmark skill owns `STEP0`, `BENCHMARK_DRAFT`, and `CALIBRATE_BENCHMARK`. The
evolvable skill owns `FAMILY_DRAFT` and `CALIBRATE_FAMILY`, applying the canonical C1-C10
and F0 rubric. Paper resolution or another desk-only pass is not Step 0. A planned command,
fixture, or schema-valid draft is not real scientific execution. Likewise, a task is not
calibrated until its oracle, adversarial, and target model runs actually execute and are
reviewed.

To contribute a task (fork → PR, and the definition of done a PR must meet), see
**[`CONTRIBUTING.md`](CONTRIBUTING.md)**.

## Repo map

| Path | What |
|---|---|
| `GRADIENT-001/` · `SOCIALBRAIN-001/` · `DEVCONN-001/` | the three example tasks (Harbor format) |
| `.claude/skills/tb-science-task-authoring/SKILL.md` | the authoring skill (the craft) |
| `.claude/skills/self-evolvable-question-design/SKILL.md` | the capability-open question-family gate |
| `TOPIC_TRIAGE_CONTROLLER_PROMPT.md` | bounded one-job scientific worker prompt |
| `contracts/curation/` | shared public contracts, lifecycle rules, and canonical C1-C10/F0 rubric |
| `RESULTS.md` | measured difficulty of the three tasks (hand re-scored, with honesty notes) |
| `CONTRIBUTING.md` | how to contribute a task (fork → PR) + the definition of done |
| `INTERN_GUIDE.md` | team process: daily contract, difficulty ratchet, environment, definition-of-done |
| `ASSIGNMENT_QUEUE.md` | candidate lanes / backlog for new tasks |
| `TASK_BOARD.md` | one-row-per-task summary (paper, axis, lever, Step-0 result, oracle, agent verdict) |
