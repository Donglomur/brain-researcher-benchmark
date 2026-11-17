# Original example contribution process

Preserved from the upstream-oriented contribution guide. Its task criteria and
authentication notes are historical guidance for the three original examples.
Use [the fork workflow](../../docs/DEVELOPMENT.md) for current branch and PR targets.
Commands below assume the repository root.

# Contributing a task

This repo holds worked examples + the authoring skill. New tasks are welcome by
**fork → branch → PR**.

## Flow

1. The following is the original upstream workflow for `brain-researcher/brain-researcher-benchmark`. For this fork, use [the current development workflow](../../docs/DEVELOPMENT.md).
2. **Install the skill** and read the process guide:
   ```bash
   mkdir -p ~/.claude/skills/tb-science-task-authoring
   cp .claude/skills/tb-science-task-authoring/SKILL.md ~/.claude/skills/tb-science-task-authoring/
   ```
   Read the archived [team guide](upstream-history/INTERN_GUIDE.md)
   and [assignment queue](upstream-history/ASSIGNMENT_QUEUE.md). In Claude Code, invoke `/tb-science-task-authoring`.
3. **Branch** per task: `git checkout -b task/<SHORTNAME>-001`.
4. **Author** the task with the skill — copy a shipped `examples/original-three/*-001/` dir as the template.
5. **Open a PR** into `master`. One task per PR. Fold any new lesson into the skill by a
   separate PR.

## Definition of done (a PR is reviewable only if)

- **Oracle solves it:** `harbor run -p <TASK> -a oracle …` → reward **1.0**, in-container.
- **≥2 frontier families fail it** (k≥3 each), **hand re-scored** — the failure is the
  *un-cued judgement* gap, not a format/computation bug. Record the runs in the task's
  `proposal.md` (see the [historical results](upstream-history/RESULTS.md) for the expected shape and honesty notes).
- **`instruction.md` never names the failure axis** — the whole point is that the judgement
  is un-cued. No mention of the specific confound / lever / robustness check.
- **The verifier requires the insight *linked to the result*,** not a keyword match — a check
  that passes an agent which merely *names* the confound is broken (see the verifier
  false-positive lessons in the skill and [historical results](upstream-history/RESULTS.md)).
- **Environment is self-contained and public:** `FROM ubuntu:24.04` (or similar public base)
  with **pinned** dependencies; data fetched from a public source (e.g. OpenNeuro) at runtime.
- **One new axis or data/modality preferred** over a 4th task on the same axis+dataset —
  keep the suite from becoming a monoculture (see the taxonomy in the skill).

## What a task PR contains

```
<TASK-NAME>/
├── instruction.md      # un-cued
├── task.toml           # id, difficulty, timeouts, resources, dataset, source paper
├── environment/Dockerfile
├── solution/           # oracle: solve.sh + compute.py
├── tests/              # test.sh + test_outputs.py (verifier)
└── proposal.md         # Step-0 result, the trap, measured agent verdicts (k, reward, what each did)
```

## Scope / honesty

- **Don't fake a reproduction.** If Step-0 shows the paper's result (or its lever) doesn't
  reproduce on obtainable data, that's a **logged success** — record it `dropped` with the
  reason and move on. Never manufacture a trap.
- Frontier-agent access (Harbor, GPT-5.5 `~/.codex/auth.json`, Claude
  `CLAUDE_CODE_OAUTH_TOKEN`) is the contributor's own; never commit credentials or tokens.

## Running the Claude agent (auth gotcha)

Harbor's `claude-code` agent reads `CLAUDE_CODE_OAUTH_TOKEN` from the host env only — it
does **not** inherit your interactive `~/.claude` login. Without an export, a run dies in
~30 s with `NonZeroAgentExitCodeError` / "Not logged in" — a **0.0 that is an auth failure,
not a task FAIL** (always check `exception_stats` in `result.json` before scoring a 0.0).

Two fixes: either `export CLAUDE_CODE_OAUTH_TOKEN=…`, or run once:

```bash
python examples/original-three/scripts/patch_harbor_oauth.py
```

which idempotently patches Harbor's agent to fall back to your logged-in session token
(`~/.claude/.credentials.json`). An exported env var still wins; re-run after
`uv tool upgrade harbor`.

## Running the GPT-5.5 agent (auth gotcha)

Harbor's `codex` agent defaults to **`OPENAI_API_KEY`** auth. If you log in with a
ChatGPT account (`~/.codex/auth.json` has `auth_mode=chatgpt` and an **empty**
`OPENAI_API_KEY`), the default path ships an empty key and the run dies in ~40 s with
`401 Unauthorized: Incorrect API key ''` — again a **0.0 that is an auth failure, not a
task FAIL**. Two fixes:

- **ChatGPT login:** force Harbor to upload your `auth.json` —
  `--ae CODEX_FORCE_AUTH_JSON=1` (or `export CODEX_FORCE_AUTH_JSON=1`).
- **API key:** `export OPENAI_API_KEY=sk-…` (harbor's default path uses it; no flag needed).

Separately, a codex run that exits non-zero in seconds with *"You've hit your usage limit …
try again at HH:MM"* is a **quota** exhaustion, not a task FAIL — wait for the reset or use
an account/key with quota.

**Golden rule:** a `0.0` that finishes in seconds with a non-empty `exception_stats` is an
infra artifact (auth / quota / build), never a task result. Only score runs with
`exception_stats: {}` and a realistic duration (~15–20 min for these tasks).
