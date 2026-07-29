---
name: self-evolvable-question-design
description: Evaluate whether a neuroimaging topic or empirical paper can anchor a genuinely self-evolvable, capability-open question family rather than a static current-agent benchmark or noise-floor-capped task. Use when triaging landscape topics or papers, designing an evolvable question set, testing oracle provenance and reliability headroom, defining freshness and ratcheting rules, or deciding whether to hand a capped paper-derived task to tb-science-task-authoring. Produces an evidence-state-aware verdict and an EvolvableQuestionFamily contract; it does not author Harbor tasks.
---

# self-evolvable question design

Decide whether a neuroimaging problem's difficulty **auto-regenerates for years** (worth
investing) or is a finite curriculum / noise-floor-capped (not). Grounded in a literature
pass over CASP, ImageNet, Kaggle, ARC-AGI, SWE-bench, MLPerf, Brain-Score, Algonauts.

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

When starting from a paper, create this shared packet before scoring C1–C10. Use the same
packet if the paper is also assessed by `tb-science-task-authoring`.

```yaml
PaperEvidencePacket:
  paper_id:                 # DOI/PMID/OpenAlex ID or stable citation
  paper_kind:               # primary_empirical | methods | benchmark | review
  claim_and_contrast:
  target_measurement:
  obtainable_dataset:
  executable_method:
  oracle_candidate:
  reliability_ceiling:
  current_baseline:
  candidate_hidden_lever:
  freshness_source:
  evidence_status: {}       # field -> reported | verified | measured | planned | missing
  evidence_refs: []
```

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

## The gate — C1–C10 (C2 is the one neuroimaging keeps failing)

- **C1 reality/execution-grounded automatic oracle** — decidable, minutes, pinned data. *Necessary, NOT sufficient* (ImageNet had a perfect oracle and still saturated).
- **C2 quantified headroom to a RAISABLE ceiling ABOVE the reliability floor.** Compute the
  noise/reliability ceiling on the *specific* target FIRST (test-retest / split-half /
  Brain-Score normalization). Require current-SOTA ≪ ceiling **and** the residual is
  capability-limited, not measurement-noise-limited, **and** a way to raise the ceiling.
  **BRUTAL AUTO-REJECT when the reliable signal is tiny or saturated:** BWAS trait effects
  r≈.01 (Marek 2022 Nature); connectome fingerprinting ~98% (Finn 2015). *This is the gate
  the v1 scoring skipped.*
- **C3 exogenous, time-forward, sequestered freshness** — name the world-process emitting new
  (problem, truth) pairs after the training cutoff + the sequestration (post-cutoff release /
  private split / novel measurement). "Human hand-authors more of the same" = sense (a), reject.
- **C4 capability-orthogonal gradient + a MANDATORY falsification test** — point to a natural
  harder continuum (up the cortical hierarchy, longer horizon, OOD stimulus/subject/scanner/
  species); then **test** that scale/compute does NOT close the gap. If scale closes it, the
  ceiling is soft (ARC-AGI-1 lesson) → downgrade.
- **C5 cheap, pre-committed re-targeting rule** — state in advance how difficulty ratchets at
  saturation; prefer AUTOMATABLE (hardness knob / held-out generator / exogenous stream).
- **C6 oracle independent of the solver** — no self-grading, no model-as-truth.
- **C7 leakage/shortcut audit inside scoring** — site/subject/family-blocked splits + a
  permutation null + a fresh re-test (ImageNet-v2 lesson), so a shortcut can't fake the ceiling.
- **C8 anti-memorization by construction** — private/post-cutoff/novel-measurement split; give
  the concrete contamination argument (public HCP/UKB/NSD/OpenNeuro get ingested).
- **C9 validated-simulator preference** — a forward model with a difficulty knob is the
  cleanest engine, but only past the sim-to-real gate.
- **C10 efficiency re-opening** — after an accuracy target ceilings, re-score on
  SAMPLE/COMPUTE/SCAN-TIME efficiency (same signal from 1/N the data). Permanently open,
  spend-free — the answer to "raising a neuroimaging noise ceiling is grant-gated."

## Procedure

0. If starting from a paper, fill `PaperEvidencePacket`. Require a primary empirical or
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

For `pass` or `conditional`, emit:

```yaml
EvolvableQuestionFamily:
  family_id:
  seed_instances:
  instance_generator:
  oracle:
  oracle_provenance:
  reliability_ceiling:
  current_baseline:
  capability_gap:
  hardness_knobs:
  freshness_and_sequestration:
  ratchet_rule:
  leakage_controls:
  efficiency_reopening:
  retirement_condition:
  next_probe:
```

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
