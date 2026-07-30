---
name: self-evolvable-question-design
description: Evaluate whether a neuroimaging topic or empirical paper can anchor a genuinely self-evolvable, capability-open question family rather than a static current-agent benchmark or noise-floor-capped task. Use when triaging landscape topics or papers, designing an evolvable question set, testing oracle provenance and reliability headroom, defining freshness and ratcheting rules, or deciding whether to hand a capped paper-derived task to tb-science-task-authoring. Produces an evidence-state-aware verdict and an EvolvableQuestionFamily contract; it does not author Harbor tasks.
---

# self-evolvable question design

Decide whether a neuroimaging problem's difficulty **auto-regenerates for years** (worth
investing) or is a finite curriculum / noise-floor-capped (not). Grounded in a literature
pass over CASP, ImageNet, Kaggle, ARC-AGI, SWE-bench, MLPerf, Brain-Score, Algonauts.

This skill owns `FAMILY_DRAFT` and `CALIBRATE_FAMILY` jobs. It authors or calibrates an
`EvolvableQuestionFamily`; it does not schedule work, claim topics, write a tracker, append
transitions, author Harbor tasks, or release a family. The controller owns state changes and
adjudication owns release.

> **The one correction that matters:** the *verb* of a task (predict / discover / design /
> intervene / adjudicate — the old A1–A6 archetypes) does **not** predict self-evolvability.
> Two problems of the same archetype land on opposite sides: naturalistic encoding in
> association cortex is open; FC→trait BWAS prediction is capped at r≈.01. Score by the
> structural axes below and the archetype washes out. Do **not** sort by archetype.

## Unit of judgment: the question family, not the paper

A paper is an **evidence anchor**, not itself an evolvable question set. It may identify a
target, dataset, measurement oracle, baseline, or difficulty axis. The investable unit is a
question family that can generate new scored instances and raise its frontier without
rewriting the answer key by hand.

When starting from a paper, read `contracts/curation/README.md` and consume the shared
`curation-contracts-v1.schema.json#/$defs/PaperEvidencePacket` artifact supplied by the
job. Use the unchanged artifact if the paper is also assessed by
`tb-science-task-authoring`; do not recreate an incompatible local packet.

Do not convert `reported` evidence into `verified` or `measured` evidence. A review can seed paper
discovery but cannot pass the paper gate itself. Missing ceiling, baseline, oracle, or
freshness evidence means **insufficient evidence** unless it is converted into a concrete
`planned` probe with inputs, cost, and a decision threshold. Planned evidence can support
`conditional`, never `pass`.

## Two senses of "self-evolvable" — only (b) is worth investing in

- **(a) instance-unbounded, ceiling-fixed** — infinite items scored against a fixed
  human-authored key. Dies on contact once a model clears it. *This is A1 un-cued rigor
  critique* (to auto-score "did the agent volunteer the right check" you must know the flaw
  in advance to inject it → bounded to yesterday's check repertoire). Useful as a
  **current-agent benchmark**, not a research line.
- **(b) ceiling-unbounded / capability-open** — the difficulty *frontier* recedes for years;
  each rung needs genuinely NEW capability. CASP, Brain-Score. **This is the target.**

## Score by ORACLE PROVENANCE (primary axis), best → worst

1. **Reality-grounded held-out MEASUREMENT** (encoding/decoding fidelity, atrophy-forward) — best.
2. **EXECUTION / computed objective** (a metric that runs).
3. **VALIDATED SIMULATOR** with known truth — only after a **sim-to-real** validation gate (C9); unvalidated = scientifically hollow.
4. **Real PERTURBATION outcome** (lesion/stimulation) — highest ceiling, priciest oracle.
5. **Human ANSWER-KEY** (A1) — capped by construction.
6. **MODEL-AS-TRUTH / in-silico** (optimize a stimulus to drive a model unit) — **disqualified, circular** (measures agreement with *that model*, not the brain; C6).

## The gate — C1–C10 and F0

Read and apply every definition in
`contracts/curation/evolvable-rubric-v1.md`. That file is the single source of truth.
Do not replace C3 with generic parameterized generation, C4 with generic contamination
resistance, or C5 with an uncommitted freshness idea. C2 measurement, the C4 falsification
test, and the F0 freshness probe must actually run before a `pass`.

## Procedure

0. If starting from a paper, consume the shared `PaperEvidencePacket`. Require a primary empirical or
   benchmark paper, an exact target/contrast, an obtainable scoring substrate, and an
   executable method. Otherwise return `insufficient_evidence` or use the paper only to find
   a better primary source.
1. Pick an **oracle type** (not an archetype). Confirm C1 with a concrete scoring path.
2. **Compute the noise/reliability ceiling on the specific target** and the current-SOTA gap
   (C2). If the signal is near the floor → reject now, no matter how clean the oracle.
3. Run the **C4 falsification test** (does scale close the residual?) — cheapest deliverable.
4. Run an **F0 freshness probe**: generate one genuinely new instance and score it without
   changing a human answer key. If this requires authoring yesterday's known flaw again, the
   family is capped sense (a).
5. Check C3/C5/C6/C7/C8. Prefer C9-simulator or C10-efficiency to re-open frontiers without spend.
6. Define the family contract below, then **tier and report**. Note what was dropped and why.
   In `FAMILY_DRAFT`, planned probes can support only `conditional`. In
   `CALIBRATE_FAMILY`, preserve actual commands, inputs, outputs, versions, and lineage.

## Required output: verdict plus an evolvable family contract

Return one verdict:

- `pass` — C1 is executable, C2 is measured, the frontier is open, and
  freshness/ratcheting are concrete.
- `conditional` — the candidate is plausible, but a named cheap probe such as C2, C4, or F0
  must run before investment.
- `reject` — the target is floor-limited, saturated, circular, solver-dependent, or capped by
  a human answer key.
- `insufficient_evidence` — the paper or available artifacts do not identify a testable
  target, scoring substrate, or required measurements.

For `pass` or `conditional`, emit
`curation-contracts-v1.schema.json#/$defs/EvolvableQuestionFamily` plus the bounded
`StageResult`. Keep `release_status=draft` in `FAMILY_DRAFT` and
`release_status=adjudication_pending` at most in `CALIBRATE_FAMILY`. This skill cannot
release the family.

Do not return a long static list of paper-comprehension questions as the family. Every
hardness knob must change capability demand, not merely wording or item count. State what
would falsify evolvability and trigger retirement.

If the same paper also supports a current-agent benchmark, mark `benchmark_handoff:
recommended` and pass the unchanged `PaperEvidencePacket` to
`tb-science-task-authoring`. Keep the frozen benchmark snapshot and the evolving family as
separate artifacts with separate IDs, splits, and claims. `both` is valid; forced duplication
is not.

## Tiers

- **Tier 1 — DO NOW:** reality-grounded oracle + demonstrated headroom over a RAISABLE ceiling
  in a capability-orthogonal regime + freshness from free exogenous dataset growth.
  Canonical: **naturalistic neural ENCODING in association cortex** (Algonauts 2025 winner
  captures only ~half the explainable variance; NSD 7T), **n-way identification decoding**
  (retrieval oracle, N/distractor hardness knob), **efficiency-frontier** (same target, 1/N
  data), **cross-dataset/OOD encoding transfer**.
- **Tier 2 — open but caveated:** A5 lesion/stimulation (highest ceiling, pricey oracle),
  A6 atrophy-spread (time-forward), validated-simulator inverse problem (C9-gated), A4 denoising
  reframed to QC-FC/ICC/efficiency (not the trait objective), SC→FC adjudication (cheap probe,
  soft ceiling — run first to test the scoring machinery).
- **Tier 3 — capped, but a good CURRENT-AGENT benchmark (sense a):** A1 un-cued rigor critique
  (the tb-science line), A3 find-the-confound / minimal-edge. Refreshed by *human* injection,
  not auto-regenerating. → hand to **tb-science-task-authoring** (authentic doer tasks:
  reproduce the paper's procedure, don't self-inject).
- **Tier 4 — DISQUALIFIED:** BWAS trait/behavior prediction from FC (r≈.01, Marek 2022),
  fingerprinting at current accuracy (~98%, Finn 2015), in-silico model-as-truth oracles,
  static theory-adjudication with indistinguishable predictions. Capped by REALITY; no oracle saves them.

## Canonical worked example (replaces the old head-motion one)

```
Problem:      Naturalistic neural ENCODING in association cortex (Tier 1)
Oracle prov.: reality-grounded held-out measurement (best)
Oracle:       noise-ceiling-normalized explained variance on held-out OOD naturalistic stimuli;
              subject- & stimulus-blocked splits + permutation null baked in (C7); minutes once features cached.
C2 headroom:  Algonauts 2025 winner ~half the explainable variance on average; near-ceiling in early
              sensory/auditory/language, LARGE headroom in higher-order association cortex; noise ceiling
              raisable (more repeats/subjects/field).
C4 test:      fit model-size × data scaling curves — does the association-cortex residual close with scale
              (soft → downgrade) or plateau far below ceiling (capability-orthogonal → invest)?  <-- first deliverable
C3/C8 fresh:  new movies/subjects/consortium waves (CNeuroMod/Algonauts), withheld novel films (post-cutoff).
C10:          re-score the same target from 1/N scan-minutes to keep it open at saturation.
Data:         Algonauts 2025 (CNeuroMod movie fMRI) primary; NSD (7T, 8 subj) high-SNR cross-check. Pinned/public.
```

## Anti-patterns

- **Sorting by archetype/verb** — it doesn't predict the outcome (open encoding vs capped BWAS are both "prediction").
- **Treating a paper as the evolvable unit** — papers provide anchors; generators, oracles,
  freshness, and ratchets make a family evolvable.
- **Generating many static questions** — instance count can be infinite while the capability
  ceiling remains fixed.
- **Scoring missing evidence optimistically** — `reported` and `planned` probes are not measured
  headroom or freshness.
- **Clean oracle over a floor-limited signal** — BWAS r≈.01: a perfect oracle certifies nothing.
- **Human answer-key as the ceiling** (A1) — capped by the author's repertoire.
- **Model-as-truth / in-silico discovery** — circular; only valid closed with a real measurement.
- **Unvalidated simulator** — tests recovery inside the sim, not science.
- **Skipping the noise-ceiling computation** — the single biggest v1 error; compute C2 FIRST.
