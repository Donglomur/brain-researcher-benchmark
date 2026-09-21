## OUTCOMEPRED-001

**Proposal Title:** Decode a single trial's upcoming outcome from IBL Brain-Wide Map population spiking — an un-cued off-critical-path error (feedback-window leakage: decoding the delivered outcome instead of the upcoming one)

**Scientific Domain:** Life Sciences · **Field:** Neuroscience · **Subfield:** Systems neuroscience / population decoding

**Source finding:** International Brain Laboratory et al. (2021), *eLife*, https://doi.org/10.7554/eLife.63711 ("Standardized and reproducible measurement of decision-making in mice"); IBL Brain-Wide Map, https://doi.org/10.1101/2023.07.04.547681. **Dataset:** DANDI dandiset **`000409`** (the NWB conversion of the IBL Brain-Wide Map), real mouse Neuropixels recordings, fetched at runtime. Pinned session: **`sub-NYU-37/sub-NYU-37_ses-21d21fc3-4201-4edc-802a-c67b61952548_desc-processed_behavior+ecephys.nwb`** (~385 MB, one session).

**Status: FULL runnable task** (real-data, runtime single-asset DANDI fetch, `allow_internet=true`). Over-claim / leakage genre with a numeric anchor, on animal Neuropixels electrophysiology. Structurally parallel to the validated-STRONG sibling STEINMETZ-001 (upcoming-choice decoding on DANDI 000017): both keep the legitimate scientific question ("upcoming X") in the instruction and leave the window placement to the analyst; the un-cued lever is *where the spike-count window sits relative to the event that defines the label*. Distinct dataset, distinct quantity (trial *outcome*, not upcoming *choice*), distinct temporal lever (feedback vs. movement).

### The measurement and the un-cued lever (de-cued)

The instruction pins the non-lever machinery — session, valid-choice trials with a delivered outcome, `is_mouse_rewarded` label, balanced classes, per-unit spike-count features over all recorded units, a standardized linear classifier, 5-fold CV — and asks for the **cross-validated accuracy of decoding the mouse's *upcoming* trial outcome (rewarded vs. error)**, relative to chance. Exactly as STEINMETZ-001 says "decode the *upcoming* choice," it names the scientific question but **not** the lever: it never says "feedback", "post-outcome", "window relative to feedback", "leakage", "before the outcome is revealed", nor does it ask for a pre-/post-outcome contrast or a positive control (the previous, telegraphing version did — that giveaway has been removed).

One off-critical-path choice inflates the estimate to near-perfect:

- **Feedback-window leakage.** The outcome (reward vs. error) is physically delivered at `feedback_time` — the reward, consummatory licking, the error tone. A spike-count window that extends across / after feedback reads out that delivered outcome, so the classifier decodes the outcome that has *already been revealed*, not the upcoming one. To decode the *upcoming* outcome the window must end **before** feedback. Doing so, the outcome is **at chance** on this session.

The IBL task is near-ballistic (median stimulus→feedback ≈ 0.29 s), so — unlike a peri-movement epoch — the honest predictive answer is a **null**: the population does not decode the upcoming trial outcome above chance before the outcome is delivered. The over-claim is reporting the ~0.99 (a feedback-spanning window) as evidence that the population "encodes/predicts" the outcome.

### The trap (Step-0 re-validated, real data)

Pinned config (sub-NYU-37 ses-21d21fc3, 867 units, balanced rewarded/error = 212, chance = 0.50, standardized logistic regression C=1, stratified 5-fold):

| window (rel. to event) | accuracy | reading |
|---|---|---|
| **feedback-spanning** (fb 0.0 .. +0.4 s) | **~0.99** | naive — reads the delivered reward / error tone / licking |
| feedback-spanning (fb −0.1 .. +0.3 s) | ~0.99 | still spans feedback |
| **pre-feedback** (fb −0.20 .. −0.05 s) | **~0.5** | honest — activity ends before the outcome ← reported |
| pre-feedback, stimulus-aligned (stim 0 .. +0.15 s) | ~0.5 | honest, at chance |

The honest, strictly-pre-feedback accuracy is **at chance** (0.43–0.57 across pre-feedback windows and across regularization C∈0.1–5), while any feedback-spanning window reports **~0.99** — a ≥0.4 gap. Robust across three sessions (sub-NYU-37, -46, -30: pre ≈ chance, post ≈ 0.98–0.995).

### The failure mode (un-cued, over-claim/leakage)

Told to decode the *upcoming* outcome, the agent windows around the feedback event (where "outcome" is defined), reports ~0.99, and concludes the population predicts/encodes the trial outcome — when it has decoded feedback that already happened. Only a strictly pre-feedback estimate (~chance) honestly answers how well the upcoming outcome can be decoded. This is the exact analogue of a peri-movement window failing the upcoming-choice sibling task.

### Verifier (3 plain checks, STEINMETZ-parallel numeric ceiling)

`tests/test_outputs.py`: (1) a real decoding run — plausible n_trials (60–560), n_units (≥200), stated chance ∈ [0.45, 0.85]; (2) **the headline upcoming-outcome accuracy must not exceed the stated chance by more than 0.15** — this fails the naive ~0.99 with a ~0.35 margin while accepting any honest pre-feedback estimate (a value the submission itself labelled post/feedback/reward/reveal/control/leak is never taken as the headline; std/dispersion keys are skipped; a percentage is canonicalised); (3) honesty — findings.md states the near-chance result and the headline in results.json is the honest near-chance value. Offline discrimination (locked; self-tested on synthetic + real oracle): reference oracle **PASS**; naive feedback-window baseline (reports ~0.99) **FAILS** the headline check; an honest pre-feedback run reporting ~chance **PASSES** even without narrating the leakage.

**Fairness / no-fake-trap:** the naive is genuinely wrong for the question asked — a window that includes feedback cannot "decode the *upcoming* outcome," it reads the delivered one (leakage). This is the same fairness basis as STEINMETZ-001's peri-movement window. The honest answer is a real, reportable null.

### Difficulty — Step-5 frontier calibration PENDING

Oracle **reward 1.0**; naive feedback-window baseline **reward 0** (re-validated on the pinned DANDI asset). The ≥2-frontier-family gate (GPT-5.x + Claude, k≥3 each) is the maintainer's step and is **not yet run**.

### Cost

`hard`. cpus 2, mem 12 GB, internet on (fetches one ~385 MB processed NWB asset at runtime — the single pinned session's S3 blob; DANDI/S3 can throttle). Agent timeout 7200 s, verifier 1800 s. Deps: dandi 0.78 / pynwb 4.2 / numpy / scipy / pandas / h5py / scikit-learn / requests (pinned in the Dockerfile).

### Proof-of-work verifier (added)

The grader is now proof-of-work (see `PROOF_OF_WORK_SPEC.md`) and the pre-feedback null is scoped.

- **Held-out reference** `tests/reference.npz` (from `solution/compute.py`, never shipped): the
  honest pre-feedback per-fold accuracies (mean 0.434, at chance) + the positive-control
  post-feedback per-fold (mean 0.995) + `ref_stats` (chance 0.5, n_trials 212, n_units 867).
- **Neutral per-item table** `folds.csv` (per-fold CV accuracies) — produced by any 5-fold CV,
  naive or honest, so requiring it does not cue the window-placement lever.
- **Pillars:** (1) `folds.csv` well-formed + non-constant + `mean(folds) == reported headline`;
  (2) the headline lies in the at-chance band `[0.35, 0.62]` (a feedback-spanning window's ~0.99
  fails); (3) **required positive control** — a volunteered decodable-window accuracy ~0.99 (or
  prose describing a post-feedback window decoding the delivered outcome near-perfectly), which
  scopes the null and shows the near-perfect number is read-out of feedback, not prediction.
- **R2 scope hedge:** the claim graded is *"not decodable above chance in the pre-feedback window"*
  (with the positive control), NOT a general "the population does not encode upcoming outcome" —
  choice and stimulus precede feedback and are outside this claim.
- **Validation matrix (subprocess pytest):** honest PASS; no-table FAIL; constant-table FAIL;
  post-feedback over-claim (0.99 headline) FAIL; at-chance-but-no-positive-control FAIL.
  **PARTIAL:** the headline is a scoped null with an analyst-free pre-feedback window, so a
  right-numbers submission with plausible fabricated near-chance folds and a guessed ~0.99 control
  cannot be fully excluded (tight per-fold matching would reject defensible alternative pre-feedback
  windows, e.g. 0.5–0.57). The operative proof-of-work is the required positive control + the
  held-out band + the fact that the solving agent lacks the reference and must run both windows.

### Second-pass hardening (finer neutral intermediate + session-specific bind)

The "PARTIAL" above was the live hole: both the pre-feedback null (~0.43 ≈ 0.5) and the ~0.99 control
are guessable from causal priors, and the old `n_units >= 400` check let a *zero-data-work* agent
guess every number. Two changes:

1. **`n_units` bound to this session's recorded-unit count (867 ± 10).** The brief pins the feature to
   *all recorded units*; the actual count is session-specific, is **not stated in the instruction**, and
   cannot be guessed a priori — reporting it requires opening the NWB units table. This is the primary
   block on a zero-data-work fabrication (a guess of ~500 no longer passes). It is independent of the
   balancing choice, so it is fair to every defensible pipeline.
2. **Required `decoding_vs_window.csv`** — a NEUTRAL time-resolved profile: cross-validated accuracy for
   a fixed 0.20 s spike-count window slid across successive latencies (start −0.50→+0.40 s) relative to
   the outcome (feedback) time. The grader (a) requires its **shape** to match a held-out reference
   (magnitude-invariant Pearson corr ≥ 0.8 — kills flat/noise/crude fakes), and (b) **RECOMPUTES** the
   null (pre-outcome windows must average at chance) and the positive control (post-outcome windows must
   average near-perfect) *from the one submitted curve*, tying headline + control to a single artifact.
   Framed neutrally (no mention of leakage / "reads the delivered outcome"); the mild "look across the
   outcome time" cue is the accepted 5(a) tradeoff.

**HONEST LIMITATION (blunt, 5(b)).** The judgment axis here — *upcoming* outcome is at chance before it
is delivered and trivially decodable after — is a **textbook causal consequence**, so the profile SHAPE
is causally predictable: a synthetic step curve of the right shape correlates ~0.98 with the real one
(≈ a genuine seed variant), and element-wise matching cannot separate them either (a step matches ~95 %
of points within 0.10). Validation matrix (subprocess pytest, this pass):
honest PASS; defensible (C=0.5 / pre −0.15 s window) PASS; **pure zero-work fabricator (guessed
n_units + flat curve) FAIL** (n_units + shape); **flat curve + real n_units FAIL** (shape/non-constant);
**naive post-feedback run reported as prediction (~0.99) FAIL** (band + recompute + curve); **post-folds
with a guessed 0.43 headline FAIL** (folds ≠ headline). **RESIDUAL that still PASSES:** an adversary who
opens the file (real n_units) *and* hand-builds a causally-correct synthetic step curve with consistent
null/control guesses. That residual is intrinsic to this task's causally-obvious judgment; the verifier
now forces real data access (n_units) and a full consistent time-resolved artifact, but the final
pre-vs-post judgement relies partly on the frontier gate, not the verifier alone.

**Data pin (reference build):** DANDI `000409` (draft), asset
`sub-NYU-37/sub-NYU-37_ses-21d21fc3-4201-4edc-802a-c67b61952548_desc-processed_behavior+ecephys.nwb`,
asset-id `73c3cf70-88a0-43ae-b7fd-03a0ac156222`, size 385181169 B,
`dandi:sha2-256 = f46fa114f07a00080cdc1860913df245326a17bf249d3749ee659cabd157784a`. Mutable
**draft** version; path + hash pin the exact blob. Runtime fetch (`allow_internet=true`); baking a
maintainer follow-up.
