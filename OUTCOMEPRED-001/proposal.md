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
