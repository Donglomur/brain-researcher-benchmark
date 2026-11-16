# tb-science task authoring — team operating guide

Operational wrapper for a small team (currently 2 authors) turning papers into
terminal-bench-science / Harbor tasks. **The *how-to-author-one-task* playbook is
the `tb-science-task-authoring` skill** — read it first (`/tb-science-task-authoring`,
or `~/.claude/skills/tb-science-task-authoring/SKILL.md`). This file is the *process
around* it: the daily contract, the difficulty ratchet, the environment, and how the
board + queue keep two people from colliding.

Three shipped tasks are your copy-templates:
- `examples/original-three/GRADIENT-001/` — rigor genre, **over-claim** failure axis (un-cued "characterise").
- `examples/original-three/SOCIALBRAIN-001/` — reproduction genre, **confident-refutation** axis (un-cued GSR lever).
- `examples/original-three/DEVCONN-001/` — reproduction genre, **wrong-cause** axis (un-cued head-motion confound).

---

## The daily contract (read this before setting anyone's KPI)

**One paper *enters the pipeline* per person per day — NOT one finished hard task per day.**

This distinction is load-bearing. From our own build history:
- **Step-0 routinely kills a paper.** Margulies-2016's gradient does not reproduce on
  open data; a proposed band-pass lever may not flip anything. Discovering that in a day
  and dropping the paper **is a successful day**, not a failed one.
- **"Hard enough" is a ratchet, not a day.** The difficulty verdict needs ≥2 frontier
  agent families, k≥3 each, ~20–40 min per run, usually several iterations. GRADIENT and
  SOCIALBRAIN each took multiple days to go from "agent passes" to "both fail".

A KPI of "one graduated hard task per day" forces fake traps — which is the one thing the
skill forbids (Step 3: never fake a trap). Measure *pipeline throughput*, not daily graduations.

---

## Lifecycle (these are the board columns)

| stage | done when | typical time |
|---|---|---|
| **1. assigned** | picked a paper from the queue in an un-crowded lane | — |
| **2. step-0** | ran the paper's method on obtainable data; result reproduces (or the lever provably flips it). **If not → drop the paper, back to stage 1.** | 0.5–1 day |
| **3. v0 + oracle** | full task built (skill's layout); `harbor -a oracle` = reward 1.0; adversarial shortcuts fail | 1–2 days |
| **4. difficulty gate** | ran ≥2 frontier families (GPT-5.5 xhigh + Claude Opus), k≥3 each; read *why* each passed/failed | 1+ day |
| **5. ratchet** | if any agent PASSES: do NOT add rigor — switch failure axis or find a real choice-dependence lever, back to stage 3 | open |
| **6. review → merge** | meets Definition of Done below; PR opened | — |

## Definition of Done (a "graduated" hard task)

- [ ] `harbor -a oracle` = **reward 1.0** (reference solvable in-container)
- [ ] reference solution passes; **adversarial shortcuts fail** (skip the key step / wrong method)
- [ ] **≥2 frontier families, k≥3 each, all FAIL** — and they fail for the *un-cued judgement*
      reason, **not** a verifier format bug (hand re-score the captured output; see skill Step 5)
- [ ] verifier is **human-looking** — plain `assert` pytest, no `WEIGHTS`/`score.json`/rubric-in-instruction
- [ ] every trap produced a **real measured signal** on the data (skill Step 3) — nothing faked
- [ ] `proposal.md` records: Step-0 validation, the trap/lever, the measured agent verdicts, the discrimination table
- [ ] task sits in an **under-crowded lane** (see anti-monoculture)

---

## The difficulty ratchet (stage 5 — the hard part)

When a frontier agent **passes**, resist the instinct to pile on more rigor requirements —
procedural rigor is in their priors and won't defeat them (skill Step 2). Instead:

1. **Switch the failure axis** (skill Step 2): over-claim → confident-refutation → wrong-cause.
   A task already probing one axis is not made harder by more of the same.
2. **Find a real choice-dependence lever** (skill Step 2.5): GSR / band-pass / atlas / HRF /
   motion-scrubbing — a result that only holds under one un-cued, contested choice. **Validate
   the lever flips the result before gating on it.**
3. **Keep the instruction un-cued** — name the result, never mention robustness/sensitivity/the lever.

Stop when Definition of Done is met. Don't over-tune the verifier to the specific agent runs
you happened to see — a judgement check is only as good as its calibration against *real* outputs.

---

## Environment (you run the difficulty gate yourselves)

```bash
conda activate brain_researcher            # nilearn/brainspace/scipy etc.
# Harbor runner:
harbor run -p <TASKDIR> -a oracle                 -o <jobs> -n 1 -y      # reference (must be 1.0)
harbor run -p <TASKDIR> -a codex -m gpt-5.5 --ak reasoning_effort=xhigh -o <jobs> -n 1 -y
harbor run -p <TASKDIR> -a claude-code -m claude-opus-4-8               -o <jobs> -n 1 -y
```

- **GPT-5.5 auth**: `~/.codex/auth.json` (no key needed).
- **Claude auth**: the claude-code agent reads **host env only** — `export CLAUDE_CODE_OAUTH_TOKEN=…`
  (it does NOT inherit your `~/.claude` login). Never print the token.
- **osf.io hangs** (nilearn has no socket read-timeout → a throttled download hangs forever): during
  dev/agent runs mount the host cache to skip it —
  `--mounts-json '[{"type":"bind","source":"/home/<you>/nilearn_data","target":"/nilearn_data","read_only":true}]' --ae NILEARN_DATA=/nilearn_data`
  (**local flag only, never commit it** — the shipped task must still fetch at runtime).
- **`--artifact /app/output`** to inspect an agent's files — but it drags multi-GB niftis into
  `/tmp` and can fill tmpfs; use only when inspecting, clean up after.
- Work in a **dedicated git worktree off `origin/master`**, not the shared main checkout
  (its HEAD floats under concurrent sessions). One branch per task.

---

## Anti-monoculture (how two people don't build the same task twice)

A benchmark of five ds000228 + resting-connectivity tasks tests one weakness five times.
Before assigning, check the board: **spread across `failure axis × dataset × modality`** (skill's
"Suite-level design"). The queue (`ASSIGNMENT_QUEUE.md`) is pre-split into data/modality **lanes** —
the two authors should be working **different lanes** on any given day.

---

## Guardrails

- **Step-0 killing a paper is success.** Log it on the board and move on; never fake a reproduction.
- **Never fake a trap.** Real measured signal or it doesn't gate (fold it in as a reported self-check instead).
- **Don't confuse "did the science wrong" with "formatted output wrong."** Inspect the artifact before
  concluding a task is hard — a format-mismatch fail is a verifier bug, not difficulty.
- **Hand re-score every agent pass/fail** — a green/red light is not enough (skill Step 5, the GSR false-positive).
- Commit style for this repo: **omit the Claude `Co-Authored-By` trailer**.
