---
name: tb-science-task-authoring
description: Triage an empirical neuroimaging paper for conversion into a fair, sufficiently hard terminal-bench-science / Harbor benchmark, then author or harden the task. Use when deciding whether a paper has an obtainable measurement oracle and real agent headroom, choosing reproduction vs rigor genre, validating an un-cued off-critical-path failure axis, building a human-looking schema-robust verifier, or calibrating oracle, adversarial, and frontier-agent runs. Produces a benchmark verdict and task contract; genuinely capability-open families are handed to self-evolvable-question-design.
---

# Authoring hard tb-science (Harbor) tasks from papers

Hard-won playbook. **Core principle: difficulty comes from the science and the data, not from elaborate scoring.** A weighted multi-layer rubric with regex-scored claims is both *easy to defeat* and *obviously machine-generated*.

## Scope and boundary

This skill owns the benchmark branch of a bounded curation job:

- `STEP0`: execute the exact paper claim or benchmark-critical lever.
- `BENCHMARK_DRAFT`: author a frozen `BenchmarkQuestionSpec`.
- `CALIBRATE_BENCHMARK`: run and inspect oracle, adversarial, and frontier-agent trials.

It does not schedule jobs, claim topics, write a tracker, append lifecycle transitions,
release artifacts, run an existing Harbor evaluation on behalf of another stage, or turn a
benchmark into an evolving service. The controller owns state transitions and adjudication
owns release. If a paper also supports a capability-open family, preserve the shared
evidence artifact and hand that independent decision to
`self-evolvable-question-design`.

Worked examples ship alongside this skill (the `*-001` task directories at the repo root), a measured difficulty ladder:
- **`GRADIENT-001`** — un-cued *characterise the principal gradient* → both GPT-5.5 xhigh & Claude Opus 4.8 overclaim a single identity → **FAIL** (hard).
- *easy control (measured during dev, not shipped)* — clean reproduction of Richardson 2018's within-network result, pipeline fully pinned → both compute it and report honestly → **PASS**. This is the baseline that proves the difficulty below is the un-cued choice, not reproduction itself.
- **`SOCIALBRAIN-001`** — reproduce Richardson's headline anti-correlation, but it only holds under GSR (an un-cued, contested choice) → both run one default pipeline and give a flat verdict → **FAIL** (hard reproduction).
- **`DEVCONN-001`** — reproduce the developmental local-to-distributed connectivity result; children move ~2× more, so it's a head-motion confound (collapses under motion control) → agents compute it, none volunteer the motion check → **FAIL** (GPT-5.5 4/4, Claude 3/3; the *wrong-cause* axis).

## Paper intake — decide whether Step 0 is warranted

Do not equate a famous paper, a rising topic, or an available dataset with a benchmark
candidate. Start with a **primary empirical or benchmark paper**, not a review. Read
`contracts/curation/README.md` and consume the shared
`curation-contracts-v1.schema.json#/$defs/PaperEvidencePacket` artifact supplied by the
job. Do not recreate an incompatible local packet.

Advance only when the paper provides an exact claim/contrast, the scoring substrate is fixed
and obtainable, the method can be executed, and the candidate truth is a real measurement.
Use reviews only to locate a primary source. Record missing or credential-blocked inputs as
`insufficient_evidence`; do not silently substitute another dataset or headline.

At intake, return one provisional route:

- `advance_to_step0` — the measurement and method are testable.
- `needs_data` — the claim is testable but the required dataset is not currently obtainable.
- `archive` — no fair fixed oracle, no executable claim, or only a fabricated/open-corpus key.
- `assess_evolvable` — the paper suggests a real oracle, headroom, and repeatable frontier;
  pass the unchanged packet to `self-evolvable-question-design`. This may coexist with
  `advance_to_step0`.

## Step 0 — Validate the result reproduces BEFORE building anything

The single most important gate. **Never assume the paper's headline reproduces on data you can actually get.**

**Prerequisite — the ground-truth substrate rule (check this first, it disqualifies whole task ideas):** the task's ground truth must be a **reproducible measurement on a fixed, obtainable dataset** — NOT (a) something you fabricate, nor (b) an aggregation over an open, incomplete literature corpus. Two ideas died on exactly this:
- *Fabricated verification* (hand-build an analysis, inject a flaw, grade against your own description) — the "truth" is invented, and a competent solver who reads the code gets marked wrong.
- *Reverse inference via meta-analysis* (Neurosynth/ALE) — the "truth" is an aggregation over a corpus you can't fully obtain or control (you can't find all the papers); it drifts with the corpus and is dominated by artifacts (e.g. top "terms" for dACC were anatomical self-labels, not cognition). Not a stable oracle.
The shipped tasks pass this rule: the truth is a number reproduced on a fixed dataset (ds000228). If a candidate's answer key isn't a reproducible measurement on a fixed obtainable dataset, stop — pick a different paper.

- Empirically run the paper's method on the accessible cohort first (a throwaway script).
- Example failure: Margulies-2016 "G1 = DMN-apex" is **HCP-specific** and does NOT reproduce on `nilearn.fetch_development_fmri` (ds000228); the apex network even flips across band-pass/subsample choices. Only discovered by running it.

Three outcomes decide the genre:
| reproduces on open data? | do this |
|---|---|
| yes, robustly | **reproduction task** (paper → result) — cleanest |
| needs credentialed data (HCP/UKB) | get the data, or pick another paper |
| fragile / doesn't reproduce | use the **measured fragility** only if it supports a fair lever or rigor task; otherwise archive |

Step 0 must distinguish the paper's reported result from local evidence. Update evidence
field by field using `reported | verified | measured | planned | missing`, and preserve the
exact dataset, cohort, contrast, preprocessing, metric, input artifacts, command log, and
outputs used by the probe. A successful Step-0 kill is a valid output. A desk assessment,
fixture, or planned command is not Step 0.

## Step 0.5 — Test benchmark fit before authoring the full task

A real effect or real lever is necessary but not sufficient. Write an explicit
`agent_headroom_hypothesis` and apply the **critical-path test**:

> To complete exactly what the instruction asks, must a competent agent already make this
> correction or analytic choice?

If yes, the candidate is likely an easy control. Subject-grouped CV, an obvious site
covariate, TIV adjustment, or a lever named by the task ID/required outputs is usually
telegraphed. Prefer a scientifically necessary check that is **off the requested execution
path**, absent from the task name and output schema, and discoverable only by interrogating
the result.

Return one benchmark verdict before expensive calibration:

- `build_hard_candidate` — Step 0 passed and an off-critical-path un-cued failure axis is
  plausible.
- `build_easy_control` — scientifically valid and useful for calibration, but no credible
  frontier-agent gap is expected.
- `reframe` — the headline is unfair, but a different locally measured claim or fragility can
  support an honest task.
- `archive` — no fair oracle, no real lever, or no remaining agent headroom.
- `insufficient_evidence` — a named data or execution probe remains open.

Do not promote `build_hard_candidate` to “hard benchmark” until Step 5 calibration passes.

For `build_hard_candidate`, `build_easy_control`, or `reframe`, emit a draft
`curation-contracts-v1.schema.json#/$defs/BenchmarkQuestionSpec`. Store the failure axis
and hidden lever as private artifact references, not in a public instruction or summary.
Include the fixed substrate, locally measured target, oracle, verifier target,
critical-path result, Step-0 evidence, expected agent gap, and calibration plan.

This is a candidate contract, not evidence that a runnable task exists or that the benchmark
is hard. Keep `release_status=draft`. Those claims require the corresponding runnable
artifacts, Step 5 evidence, and independent adjudication.

## Step 1 — Pick the genre deliberately

| | reproduction (paper→result) | process / rigor |
|---|---|---|
| instruction | condensed methods section | condensed methods section |
| ground truth | the locally reproduced target derived from the paper | correct scientific *behaviour* |
| verifier | **one numeric match** (± tolerance) | reads the conclusion and *judges* |
| looks human | natively | needs care (judgement ≠ number) |
| precondition | result must reproduce locally | measured fragility/failure axis from Step 0 |

Reproduction is cleaner and more authentic — *prefer it*. But note (measured): a clean reproduction of a **robust** result is **not hard** — frontier agents just run the pipeline and report it honestly (measured: an easy fully-pinned control variant, both agents pass). To make a reproduction *hard* without leaving the genre, see the next section — you inject un-cued judgement by choosing a result that is **choice-dependent**, keeping the verifier mostly numeric + one honesty check. Fall back to the pure rigor genre only when the result won't reproduce at all, or you specifically want to test open-ended judgement.

## Step 2 — The difficulty ladder (what actually defeats a frontier agent)

Validated against GPT-5.5 xhigh and Claude Opus 4.8:
1. **Procedural rigor** (alignment, spatial/spin nulls, self-falsification) → **does NOT defeat them**. It's in their priors; ask and they do it. (GPT-5.5 passed a spin-null+self-falsify task at 0.99.)
2. **Condensed-methods underspecification** ("hidden info") → mostly absorbed by priors.
3. **Anti-prior ("the textbook is wrong here")** → only fair if the textbook is *robustly* wrong on the data. If it's merely fragile, a correct pipeline can reproduce the textbook → you'd punish a correct solution. Usually **not gateable**.
4. **Un-cued volunteered behaviour** → **this defeated both frontier models.** Without being told, do they spontaneously check robustness / volunteer skepticism / refuse to overclaim?
   - GPT-5.5: ran one pipeline, asserted one confident identity, checked nothing.
   - Claude: did a bootstrap *robustness ritual* but on the wrong axis (within-pipeline resampling, not across analytic choices) → false reassurance, still overclaimed.
   - **The cue is load-bearing: cued, they do it right; un-cued, they don't.** The frontier gap is metacognitive, not compute.

**Takeaway: to make it hard, don't add more rigor requirements — test what the agent won't do unprompted.**

The failure axis must also be **off the critical path and not telegraphed**. A standard
correction can have a dramatic Step-0 effect and still be easy if the requested analysis
forces the agent to decide it. Difficulty is an empirical property of the agent population,
not an intrinsic property of the paper.

Note the failure is symmetric: agents are confidently wrong in *either* direction. On `SOCIALBRAIN-001` both flatly concluded "doesn't reproduce" — a confident *refutation* that missed the result reproduces under a choice they never tried. Under- and over-claiming are the same un-cued-judgement gap.

**The un-cued failure axes — the design space.** Each axis = a check a careful scientist
volunteers and the agent, un-cued, does not. The three we've shipped are just the *named*
ones; the space is much larger. Grouped by **what the agent fails to question** — pick one
per task, and ground it in a real, measured pitfall (Step 0):

**A · the result's robustness** — does it hold across defensible analytic choices?
- **Over-claim an identity** — asserts one confident answer, checks nothing. (`GRADIENT-001` ✓ — each model asserts a *different* single gradient identity; the divergence is the fragility.)
- **Confident refutation** — a null hides a result that appears under one un-cued choice; the agent runs one default pipeline and flatly says "doesn't reproduce". (`SOCIALBRAIN-001` ✓ — the GSR lever.)
- **Point-estimate, no multiverse** — reports one number, never the spec-curve / vibration of effects (Steegen 2016; garden of forking paths). *candidate.*

**B · the cause** — is it the effect I think, or an artifact?
- **Wrong-cause confound** — reproduces an effect, never checks a confound. (`DEVCONN-001` ✓ — a developmental effect that is really head motion (Power 2012); a Claude run even volunteered a *different* caveat but still missed the true cause.) Same machinery, other levers: physiological noise (respiration/cardiac aliasing), site/scanner batch (ComBat), temporal band-pass. *candidates.*
- **Reverse inference** — infers a cognitive process from an activation without the base rate (Poldrack 2006). *candidate.*
- **Correlation → causation / direction** — treats connectivity or activation as directed influence or necessity. *candidate.*

**C · the statistical inference**
- **Circularity / double-dipping / leakage** — selects on the same data it tests, or a predictor with subject/site leakage inflating accuracy (Kriegeskorte 2009). *candidate (Lane D).*
- **Multiple comparisons / cluster inflation** — reports a blob uncorrected (Eklund 2016, ~60% false positives). *candidate.*
- **Significance ≠ effect size** — with large n everything is "significant"; reports p, not magnitude/CI. *candidate.*
- **Power / small-sample instability** — a headline from n≈15 reported as fact. *candidate.*
- **Aggregation fallacy** — a group-level correlation is asserted of individuals (Simpson's paradox). *candidate.*

**D · the data / sample**
- **Selection / regression to the mean** — top-responders selected, then "decline". *candidate.*
- **Over-generalization** — the result is dataset-specific and doesn't transfer (e.g. HCP-specific gradients — we hit exactly this; validate transfer before gating). *candidate.*

Rules across all of them: (1) each axis still needs its own **Step 0** — the pitfall must
produce a *real measured signal on your data* before you gate on it (no-fake-traps); (2) a
task already covering one axis is **not** made harder by piling on rigor — reach for a
*different* axis; (3) vary **axis × dataset × modality** across the suite (Suite-level design).

## Step 2.5 — Make a *reproduction* hard: the choice-dependence lever

This is how to get a task that is **authentic + human-looking (reproduction) AND hard**, instead of falling back to the rigor genre.

Pick a famous result whose reproduction **hinges on one defensible-but-contested analytic choice** — the classic neuroimaging levers: **global-signal regression (GSR)** (induces anti-correlations), **temporal band-pass**, **ROI/parcellation definition**, GLM/HRF or motion-scrubbing options. Then:
1. **Pin everything except that one lever** (e.g. pin the ROIs), and leave the lever to the analyst.
2. Keep the instruction **un-cued** — name the result to reproduce, never mention the lever, robustness, or sensitivity.
3. The honest answer must *discover and report the choice-dependence*; an agent that runs one default pipeline gets a flat yes/no and **fails**.

**Step 0 for the lever (mandatory — it's the no-fake-traps rule):** prove the lever actually flips the result before building. Worked example (`SOCIALBRAIN-001`): Richardson's ToM–pain anti-correlation is `r_s=−0.07` (n.s.) with a standard clean but `r_s=−0.34` (≈ the paper's −0.35) once GSR is added. Real, dramatic, and GSR is a genuine decade-long controversy — so the trap is fair: a mature reproduction *should* check it. Verifier then stays mostly numeric (connectivity computed) + one honesty check (does `findings.md` link the lever to the result — see Step 5 for the false-positive trap in writing that check).

## Step 3 — Never fake a trap

Every difficulty/trap must produce a **real measured signal on the data**. Validate each one before writing the verifier around it.
- Kept: alignment necessity (unaligned r≈0 vs aligned r≈0.68); apex fragility (apex flips across configs).
- Dropped as noise: template circularity (inflation 0.010); parcel-coverage (0/20 subjects ever incomplete).
- If a candidate trap isn't real, fold it in honestly as a *reported self-check*, or drop it — do not gate on it.

## Step 4 — Write a human-looking AND schema-robust verifier

Tells that scream "machine-generated" (avoid):
- weighted multi-layer rubric (`WEIGHTS = {...}`), `score.json`, named regex constants scoring prose;
- an instruction that **describes its own scoring rubric**;
- bespoke artifact contracts (e.g. a `method_route.json`/`claim_support.json`/`artifact_contract_scan.json` trio).

Human version (see `GRADIENT-001/tests/test_outputs.py`):
- a short reviewer-style `pytest` with **plain `assert`s** and a comment stating the ground truth;
- a natural deliverable (`findings.md` write-up + `run_metadata.json`), not a rigor-artifact trio;
- for reproduction tasks, literally `assert abs(result - expected) < tol`.

**Schema robustness is non-negotiable** (it bit us 3×). Agents emit varied output shapes — network labels `"Visual"` vs `"Vis"`; `aligned_signed` as a scalar vs a nested `{pairwise_pearson_mean: ...}` dict. A verifier that hard-codes one shape **fails correct solutions on format, not science**. Canonicalise labels; search any-depth for the number. Always inspect a real agent's captured output (`--artifact /app/output`) to find brittleness.

Honest limit: a rigor-genre verifier still *grades a judgement* (reads the conclusion), so it can't be as clean as a reproduction task's numeric match. That ceiling is intrinsic to the genre — don't pretend otherwise.

## Step 5 — Calibrate with oracle + adversarial + real agent

- **Oracle must pass** (reward 1.0) — the reference solution proves the task is solvable in-container.
- **Shortcuts must fail** — build adversarial outputs (skip the key step / use the wrong method) and confirm the gates bite.
- **Run ≥2 different frontier families** (e.g. GPT-5.5 xhigh *and* Claude Opus), k≥3 each for a firm claim. n=1-per-model is preliminary — agents are stochastic. Read *why* each failed: divergent failure modes are themselves evidence the trap is real, not a verifier quirk. (`GRADIENT-001`: GPT-5.5 checked nothing; Claude ran a bootstrap *robustness ritual on the wrong axis* — within-pipeline resampling, not across analytic choices — and still overclaimed. Both fail, differently, for the same un-cued reason.)
- **Distinguish "did the science wrong" from "formatted output wrong."** A 0.79 fail that's actually a label-string mismatch is NOT a hard task — it's a verifier bug. Inspect before concluding.
- **Re-score the real agent output and read its pass/fail by hand — a green/red light is not enough.** When the verifier grades a prose *insight*, a keyword check will false-pass a write-up that merely *names* the thing. The fix is always the same: **require the insight to be linked to the RESULT**, never a bare keyword, then re-tune the regex against the *actual* agent + adversarial texts until reference passes and every flat/naming answer fails.

  **The recurring false-positive class — a confound/lever word colliding with *pipeline vocabulary* (bit us twice).** The trap words you grade on (`gsr`, `global signal`, `motion`, `confound`, `regress`, `reduced`, `nuisance`) are the *same words agents use to describe their preprocessing*. So a pipeline description false-passes a naming check:
  - `SOCIALBRAIN-001`: check looked for "global signal" → GPT-5.5 passed by writing "**no global signal regression**" (describing its pipeline), never having tested GSR.
  - `DEVCONN-001`: check had a `(confound…)[0,45](motion)` branch and a `reduced`→`regressed`→`motion` chain → Claude passed by writing "fMRIPrep **reduced confounds regressed (motion**, aCompCor, …)" (a nuisance-regressor list), never having checked head motion. It had even volunteered a *different* skeptical caveat (global-amplitude), so it *looked* insightful — the green light was a lie.
  Guards that hold: (1) the trap word must co-occur with a **result token** (the age/group/developmental effect, "reproduce", "anti-correlation") or a **collapse token** ("only with", "no longer significant", "vanishes under control") — proximity to the trap word alone is not enough; (2) **never put pipeline vocabulary in your trigger set** — dropping a bare `reduc\w*` (which matched "reduced confounds") was the actual fix; (3) build the adversarial set *from the real runs*: a passing agent's own pipeline sentence is your hardest negative. A judgement check is only as good as its tuning against real outputs — and the output that looks like a pass is the one to read most carefully.

Record calibration in the draft `BenchmarkQuestionSpec` and return a
`StageResult`. Use `calibration_status=calibrated` only for an actually executed, fully
reviewed protocol. Set `release_status=adjudication_pending` at most; this skill cannot
release the task.

## Suite-level design — don't build a monoculture

A single hard task is not a benchmark. Across the suite, vary three things independently, or every task exercises the same weakness:
- **failure axis** (over-claim / confident-refutation / wrong-cause — see Step 2);
- **dataset** (all our first tasks sit on `nilearn.fetch_development_fmri`/ds000228 — convenient, but a shared quirk becomes a shared blind spot);
- **modality / method** (resting-state connectivity ≠ task-GLM activation ≠ structural/diffusion ≠ EEG).

When two candidate tasks share all three, the second adds little. Prefer the candidate that opens a *new* axis or a *new* data+modality even if it's more work to validate — e.g. a task-fMRI GLM multiverse (fitlins) breaks the connectivity monoculture, a motion/QC-FC task opens the wrong-cause axis.

## Task layout (Harbor)

```
TASK/
  instruction.md        # condensed methods voice; NO scoring-rubric section
  task.toml             # difficulty, dataset_id, cpus/mem, timeouts, allow_internet
  environment/Dockerfile# pinned deps (verify they actually install+run)
  solution/{solve.sh, compute.py}   # reference; writes the natural deliverable
  tests/{test.sh, test_outputs.py}  # test.sh -> uvx pytest -> reward.txt
```

## Engineering gotchas

- Runtime data download needs `allow_internet=true`; **osf.io throttles/timeouts** after repeated fresh pulls (nilearn's urllib has no socket read-timeout, so a throttled connection hangs *indefinitely* on one file, not just slow). During **development/agent runs**, mount the host cache to skip the download entirely:
  `--mounts-json '[{"type":"bind","source":"$HOME/nilearn_data","target":"/nilearn_data","read_only":true}]' --ae NILEARN_DATA=/nilearn_data` (validated: oracle reward=1, downloads=0). Keep it a **local run flag, never committed** — the shipped task must still fetch at runtime (`allow_internet=true`), and external runners/CI will still hit osf, so flag that reliability caveat in the proposal. The mount removes the ~30-min download but **not** the compute (e.g. GSR's per-subject whole-brain global-signal extraction ≈15 min is irreducible). Highest value on *agent* runs, where an osf hang otherwise burns tokens and wall-clock.
- `--artifact /app/output` drags multi-GB niftis into `/tmp` and can fill the session tmpfs (kills Bash). Only use it when inspecting outputs; clean up after.
- Pin Dockerfile deps to versions you've **actually run** (e.g. `brainspace==0.1.20` verified under `numpy==2.1.3`), not guessed.
- A choice-dependence task may need a heavier reference (e.g. GSR = whole-brain `NiftiMasker` per subject on top of the download) — budget the timeout (`SOCIALBRAIN-001` oracle ≈ 35 min over 155 subjects; `timeout_sec=5400`).
- Harbor agents: `-a oracle` (reference), `-a codex -m gpt-5.5 --ak reasoning_effort=xhigh`, `-a claude-code -m claude-opus-4-8`. The claude-code agent reads auth only from host env (`CLAUDE_CODE_OAUTH_TOKEN`/`ANTHROPIC_API_KEY`) — it does NOT inherit the local `~/.claude` login.

## One-line flow

Consume the shared `PaperEvidencePacket` → reject reviews/unobtainable oracles → **verify the exact claim on
obtainable data** → measure a real lever or fragility → apply the off-critical-path
`agent_headroom_hypothesis` → choose `build_hard_candidate`, `build_easy_control`, `reframe`,
`archive`, or `insufficient_evidence` → only then author the task → calibrate with oracle +
adversarial + ≥2 frontier families, k≥3 each → hand re-score why each run passed or failed →
recommend adjudication only for science failures, never format/auth/runtime failures. If the paper also exposes
an open oracle/ceiling/freshness frontier, send the unchanged packet to
`self-evolvable-question-design`; keep the two artifacts separate.

## Related memory
`project_tbscience_gradient_trap_experiments.md` (running Harbor oracle/agent on the GRADIENT task; the un-cued-vs-cued difficulty findings).
