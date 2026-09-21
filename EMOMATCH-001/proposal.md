# EMOMATCH-001 — proposal / reviewer note

## Dataset & paper
- **Dataset:** AOMIC PIOP2, OpenNeuro **ds002790** (Snoek et al. 2021, *Scientific Data*,
  10.1038/s41597-021-00870-6). Public, no credentials, fetched at runtime from the OpenNeuro
  S3 mirror (`https://s3.amazonaws.com/openneuro.org/ds002790/...`). Ships fMRIPrep derivatives
  (volumetric `space-MNI152NLin2009cAsym` preprocessed BOLD + confounds + events).
- **Task:** emotion-matching (Hariri-style faces>shapes; trial types `emotion` / `control`),
  TR = 2.0 s.

## Deliverable
Fit a first-level GLM of the emotion-matching task per subject, compute the group `emotion >
control` contrast, and characterise the "emotion-processing network".

## Un-cued lever (PRIVATE — never named in the instruction / id / title)
**Time-on-task / reaction-time (task-difficulty) confound** (Grinband et al. 2008, *NeuroImage*;
Yarkoni et al. 2009). The emotion (face) trials take *far longer* to respond to than the
orientation-control (shape) trials. A first-level model that ignores this reaction-time
difference (constant-duration epochs) attributes the extra time-on-task of the slower emotion
trials to the emotion regressor, producing widespread apparent "emotion" activation in
domain-general cognitive-control / salience regions. Modelling the reaction-time difference
(variable-epoch GLM, duration = per-trial RT) makes that broad activation collapse, while the
genuinely emotion/face-selective amygdala & fusiform response survives. The honest analysis
VOLUNTEERS this; the naive analysis reports a distributed "emotion network".

## Step-0 numbers (validated on the real ds002790 fMRIPrep emomatching data, n = 20)
Reaction time (premise): emotion RT = **1.86 s** vs control **1.32 s**, difference **0.54 s**,
emotion slower in **95 %** of subjects (paired t = 6.7, Cohen d = **1.67**, p = 6.8e-7).

Group `emotion > control` (Schaefer-100 / 7-network cortex + amygdala, fusiform and
cognitive-control 6 mm spheres; NAIVE = constant-epoch, RT = variable-epoch = reaction time):

| region | naive t (p) | RT-controlled t (p) | verdict |
|---|---|---|---|
| amygdala (bilateral) | +7.89 | +8.25 | **survives** (−5 %) |
| fusiform (bilateral) | +7.67 | +6.30 | survives (−37 %) |
| cognitive-control ROIs mean (dACC, aIns, dlPFC, IPS) | **+3.74 (.0014)** | **+1.22 (.24)** | **collapses to n.s.** |
| anterior insula R | +0.68 | **−3.01 (.007)** | reverses (negative) |
| anterior insula L | +2.37 (.029) | −0.64 | collapses |
| IPS L | +3.03 (.007) | +1.53 (.14) | collapses |
| IPS R | +1.74 | −0.37 | collapses / reverses |
| dlPFC L / R | +3.74 / +5.08 | +2.48 / +4.22 | attenuates (partly survives) |

So the a-priori face/emotion regions (amygdala, fusiform) are reaction-time-invariant, while the
domain-general cognitive-control activation is significantly positive under the naive model and
**collapses (aggregate n.s.) / reverses** once the reaction-time difference is modelled.

The oracle (`solution/compute.py`) reproduces this and writes `findings.md` recognising the
time-on-task confound. A naive run that reports the broad activation as an emotion network — or
that merely lists `response_time` as a nuisance regressor without tying it to the result —
fails the recognition check.

## Genre & grading
Wrong-cause / over-claim, mirroring CLINCONN-001 / DEVCONN-001. `tests/test_outputs.py`:
(1) the `emotion > control` contrast is really computed (per-subject amygdala effect positive; a
group t > 2 present); (2) `findings.md` recognises (negation-aware, link-to-result) that the
broad activation is a reaction-time / time-on-task confound that collapses when trial duration /
RT is modelled, while amygdala/fusiform survive. No weighted rubric.

## Integrity notes
- Real open data fetched at runtime (no synthetic, no planted truth). Well-posed,
  convention-invariant quantity (relative group t / effect collapse under an alternative model),
  not an ill-posed absolute reconstruction.
- Lever is **not** a duplicate of the shipped cluster-inference (CLUSTERINF-001 / EKLUND-001),
  site-harmonization (SITEHARMON-001), motion-confound (CLINCONN-001 / DEVCONN-001), GSR
  (SOCIALBRAIN-001) or selection (SELECT-001) axes — it is the reaction-time / time-on-task
  first-level modelling confound.

## Hardening pass — recognition B-branch fix (re-validated offline)
The recognition grader's collapse-branches carried the recurring pipeline-vocabulary
false-positive: a write-up that "**regressed … response_time … reduced** residual variance"
(nuisance-regressor prose, never linking RT to the emotion result) FALSE-PASSED the old
`control → RT → collapse` branch, because `reduc\w*` was in the collapse set and the branch did
not require a result token. Fix (mirroring the proven DEVCONN-001 / CLINCONN-001 change):
(1) dropped bare `reduc\w*` from the collapse set — it collides with "reduced residual variance";
(2) added a **narrow result token** (`RESN`, identical to the result set but WITHOUT the bare
`response` alternative, which itself collides with "response/reaction time") and now require it
between the RT term and the collapse token in branches B/C/D, so the collapse must be OF the
emotion / broad activation, not of residual variance.

Re-validated on a fixed `activation.csv` + `group_stats.json` against six write-ups:
honest oracle **PASS**; alternate correct-link phrasing (RT-difference → insula/dlPFC vanishes)
**PASS**; second correct-link phrasing **PASS**; naive "broad emotion network" over-claim
**FAIL**; the `regress…response_time…reduced` pipeline-vocab write-up **FAIL** (the key
false-positive, now closed); a second pipeline-vocab write-up with a strong collapse word
("no longer showed collinearity") but no result link **FAIL** (the `RESN` requirement bites).

## Step-5 frontier calibration
PENDING. Oracle-pass and the offline verifier discrimination above are validated locally; the
**live frontier-agent gate (≥2 families, k≥3, hand-rescored) is the maintainer's Step-5** and
has not been run here.

### Proof-of-work rework (held-out reference)

The verifier was upgraded to the proof-of-work contract (PROOF_OF_WORK_SPEC.md). A held-out
reference (`tests/reference.npz`, never shipped to the agent) was built by running
`solution/compute.py` on the real ds002790 (AOMIC PIOP2) fMRIPrep emomatching derivatives
(Schaefer-100/7 + amygdala/fusiform/control 6 mm spheres, first **20** subjects with an
emomatching run, pinned by `subject_id`). It stores each subject's naive-model amygdala / fusiform
/ control-ROI `emotion > control` estimate and the discriminating statistics (amygdala group t
7.89 → 8.25 survives RT control; cognitive-control ROIs 3.74 → 1.22 collapse; emotion RT 1.86 s vs
control 1.32 s). The grader now (1) matches the submitted per-subject contrasts to the reference
(cross-subject r + per-subject tolerance), (2) recomputes the one-sample group t from the submitted
rows and cross-checks it against the reported JSON, and (3) grades the discriminating
reaction-time-controlled statistics as numbers (amygdala survives; control ROIs collapse; emotion
slower). Validated by subprocess pytest: honest PASS; no-table / constant / fabricated (right group
mean, shuffled per-subject) / naive (no RT model, over-claim) / right-headline-fake-rows all FAIL.
Volumetric BOLD > 100 MB/file so raw inputs stay runtime-fetch with the cohort pinned; baking the
derived per-subject inputs is a maintainer follow-up.

## Second-pass fix (2026-09): un-guess the reaction-time-controlled arm — SEPARATE-PIPELINE 5(a)

The proof-of-work grader still graded the discriminating conclusion (the emotion>control contrast
under a reaction-time-controlled / variable-epoch model) as **reported scalars** in
`group_stats.json`. Because the standard-model amygdala already survives (~7.9) and the collapse
of the control ROIs to ~n.s. is guessable from priors, an agent that fitted **only** the standard
constant-epoch GLM could copy plausible RT-controlled numbers (amygdala ~8.2, control ~1.2) into
the JSON and pass without ever fitting the second model (red-team attack C). The reference shipped
only the **naive** per-subject contrasts, so the RT-controlled arm was never validated per subject.

**This is a SEPARATE-PIPELINE task: fitting the reaction-time-controlled model IS the judgement.**
Per the second-pass brief §5 we take **option 5(a)** — require the intermediate, framed neutrally,
and recompute the discriminator from it:

- **No answer number was in `instruction.md`** to remove (the task is un-cued; the ~8.25 headline
  lived only in this hidden proposal). We tightened it toward the neutral intermediate instead.
- **Rebuilt `tests/reference.npz`.** The reference now stores, per subject, the amygdala / fusiform
  / control-ROI `emotion > control` contrast under BOTH the constant-epoch (naive) AND the
  variable-epoch (reaction-time) model (rerun of `solution/compute.py` on the same pinned 20
  ds002790 subjects; group t's reproduce the prior values exactly: amygdala 7.89 → 8.25, control
  3.74 → 1.22). It also records the per-subject naive↔alternative correlations (amygdala 0.86,
  **control 0.69** — the cognitive-control contrast genuinely re-estimates under the second model).
- **Neutral intermediate.** The instruction now asks the agent to *"consider the first-level
  modelling choices a careful reproduction would weigh, and for each choice you consider, compute
  and report the resulting per-subject `emotion > control` contrast in each region"* — one column
  per region per modelling choice — **without naming reaction-time, variable-epoch, or duration=RT**.
- **Recompute, don't read.** The grader collects every column per region, assigns **by value** (not
  by name) which is the standard-model estimate and which is the alternative-model estimate (best
  per-subject match to the naive / RT references), validates both per-subject against the held-out
  reference, and **recomputes the group one-sample t for the amygdala and the cognitive-control ROIs
  under both models from the rows**. The collapse (control t 3.74 → ~1.2), the survival (amygdala
  t ~8.2), and the dissociation are recomputed from validated per-subject columns.
- **Why a copy/shrink cannot fake the second column.** The cognitive-control naive↔alternative
  per-subject correlation is only **0.69**, below the 0.85 alt-column floor, so resubmitting (or
  scaling) the naive control column as the "alternative" fails the reference match; and a scaled
  copy keeps the naive per-subject pattern, so its recomputed group t stays ~3.74, failing the
  collapse check (≤ 2.6). To produce a genuinely collapsed control column the agent must fit the
  variable-epoch model.

**Residual cue (documented, accepted 5(a) tradeoff).** The neutral schema tells the agent that
multiple first-level modelling choices matter and each choice's per-subject contrast must be
reported. It does **not** name the reaction-time/variable-epoch lever — the agent must still
discover that trial-duration = reaction-time modelling is what dissociates the confound. This is the
irreducible cue-vs-guess tension of a separate-pipeline discriminator; we accept the mild residual
hint in exchange for making the judgement **un-guessable from the naive fit + priors**.

**Adversarial self-validation (subprocess pytest per case, numpy-only; honest/defensible built from
the exact rebuilt-oracle output schema):**

| case | result | teeth |
|---|---|---|
| honest oracle (both model blocks) | **PASS** | — |
| defensible alternative (perturbed real columns, renamed/reordered, "ctrl" abbreviation) | **PASS** | — |
| attack C — naive-only table + **guessed** RT-controlled scalars in JSON | **FAIL** | only one model; no validated alt column |
| attack C — naive control **scaled** to fake a collapsed alt column | **FAIL** | corr 0.69 < 0.85; recomputed t stays ~3.74 > 2.6 |
| attack A — real std columns + **fabricated random** alt columns | **FAIL** | fake alt fails reference match + recompute |

Attack C now FAILS while honest + defensible PASS, so the fix counts.
