## MOTORIMG-001

**Proposal Title:** Reproduce motor-imagery decoding from windowed EEG (CSP+LDA) — an un-cued windowing / cross-validation-leakage confound (the *leakage / CV-circularity* failure axis)

**Scientific Domain:** Life Sciences · **Field:** Neuroscience · **Subfield:** EEG decoding / brain–computer interfaces

**Source paper:** Ramoser, Müller-Gerking & Pfurtscheller (2000), *IEEE Trans. Rehabil. Eng.*, https://doi.org/10.1109/86.895946 ("Optimal spatial filtering of single trial EEG during imagined hand movement", CSP + linear classifier decodes left- vs right-hand imagery). Leakage/CV-circularity critique: Varoquaux (2017), *NeuroImage*; Lemm et al. (2011), *NeuroImage* ("Introduction to machine learning for brain imaging"); Abraham et al. (2014). Dataset: PhysioNet EEG Motor Movement/Imagery (eegbci, runs 4/8/12) via `mne.datasets.eegbci`. **Fills the explicitly-empty EEG cell of the leakage axis (DECODE is fMRI/Haxby).**

**Status: FULL runnable task, built with the `tb-science-task-authoring` skill; built the shipped way (reproduce the decoding headline → reveal the hidden confound), modelled on DEVCONN-001 / SOCIALBRAIN-001 / TOPEDGES-001.** Differentiated SIBLING of DECODE: the leak here is induced by the analyst's *windowing* step (no ingrained run-blocking convention), so a solution that mimicked Haxby's leave-one-run-out does not mechanically pass.

### Why this exists

CSP+LDA decoding of motor imagery is a canonical BCI result; cutting each trial into overlapping windows to get more samples is common practice. Reproduced at face value it looks strong — high cross-validated accuracy. The un-cued judgement is that a **random k-fold over the windows leaks**: windows from the same trial are near-copies (within-trial autocorrelation), so they land in both train and test and the classifier partly recognises the trial, not the class. Grouping the split by trial/run (leave-one-run/trial-out) removes it and the accuracy drops to the true one-window-per-trial level. The agent is asked to reproduce the decoding accuracy and report whether it holds; it fails only if it does not *volunteer* the non-independence and the grouped-CV comparison the instruction never mentions. Failure axis **leakage / CV-circularity**, EEG modality — distinct from DECODE's fMRI temporal-block leakage.

### The reproduction and the trap (validated) — held privately

The validated numbers (per-scheme accuracies, the inflation, the grouped-CV split proof) and the oracle receipt are in the **private, git-ignored `calibration.md`** (rule 4). In brief: a random k-fold over the windowed epochs gives a strong, publishable-looking left-vs-right accuracy, but grouping the split on the **real run/trial provenance** (leave-one-run-out over the three recordings, or group-k-fold by trial) drops it substantially, to a level that matches the independent true one-window-per-trial decodability. The gap is the leak, and it holds for every subject. The instruction is un-cued: it names the CSP+LDA + windowing method in full, but **never mentions leakage, non-independence, same-trial windows, grouped/blocked cross-validation, or leave-one-run-out**.

**Honesty note (no-fake-traps discipline).** The blocked estimate is not a contrived deflation: it agrees with the independent true one-window-per-trial decodability, so the lower number is the real signal and the gap is the leak. Unlike DECODE (fMRI, where a run-blocking convention exists), EEG window-decoding has no such convention — random k-fold over windowed epochs is common practice — so the leak is easy to fall into and is the analyst's own un-cued choice.

**Validity repair (#24).** The reference no longer invents pseudo-runs from an index. The packaged bundle carries the **real eegbci run id (4/8/12) and a unique trial id per trial** (built from the run/event structure by `data/build_epochs.py`); windows inherit their trial's run/trial id and the CV is **grouped** on them so no trial's windows span train and test. The oracle emits a **grouped-CV proof** — the number of trials whose windows land in more than one fold, per scheme — and the verifier confirms it (grouped schemes → 0; the random scheme → many).

### Verifier (2 plain checks)

`tests/test_outputs.py`: (1) `test_decoding_computed` — validates the ACTUAL data: a real decoding accuracy in a plausible above-chance range, a sane subject count, the per-subject table if present, and — where a grouping proof or a blocked estimate is present — that the grouping is genuinely enforced (grouped scheme splits 0 trials, the random scheme splits >0) and the blocked accuracy sits below the random one; empty/fabricated fails. (2) `test_recognises_window_leakage` — `findings.md` recognises that a random k-fold over windowed epochs leaks (same-trial windows are non-independent, in both train and test → inflated), so the split must be grouped by trial/run and the honest accuracy is the lower one — **not** a flat high-accuracy report, **not** merely naming the blocked fix, and **not** a dismissal ("we blocked the folds; accuracy held"). The recognition must LINK the windowing/same-trial non-independence to the inflation.

**Discrimination (validated locally):**

| solution | verdict |
|---|---|
| reference (random leaks; run/trial-blocked matches the true level → honest lower number) | **PASS** |
| genuine "same-trial windows in train and test inflate it; blocked CV drops to the true level" | **PASS** |
| flat "high decoding accuracy, decodability holds" (no grouped check) | **FAIL** |
| "we blocked the folds by trial; accuracy held, so windowing didn't inflate anything" (dismissal) | **FAIL** |
| "small sample / class imbalance may matter" (adjacent-but-wrong cause) | **FAIL** |
| empty | **FAIL** |
| fabricated (blocked ≥ random / grouping proof that does not group) | **FAIL** |

### Difficulty — PENDING the frontier gate (harbor + GPT-5.5 / Claude, k≥3 each)

Oracle passes both checks (validated end-to-end, offline). Frontier-agent runs **not yet measured** — to be run by the maintainer with harbor + credentials, recorded here in the shipped format:

| agent | runs | reward | what it did |
|---|---|---|---|
| **GPT-5.5 (codex, xhigh)** | _k≥3_ | _pending_ | _pending_ |
| **Claude Opus 4.8** | _k≥3_ | _pending_ | _pending_ |

**Expected failure mode (hypothesis, to be confirmed by the gate):** both families window the trials, run a random k-fold, and report the high accuracy as decodability, without volunteering — un-cued — that the windowed samples are non-independent so the split must be grouped by trial/run (the honest, lower level). This mirrors the measured behaviour on DEVCONN-001 and SOCIALBRAIN-001, where frontier families computed correctly yet failed to volunteer the single hidden check.

**Verifier-integrity note (the skill's inspect-real-outputs lesson).** The recognition check is negation-aware and downgrade-driven: a bare "blocked by trial/run" does **not** pass (dismissers name the fix while affirming the high number); the coupled downgrades require the honest mechanism (same-trial near-copies in train and test; the number is inflated/fake; the grouped estimate drops to the true level) that a name-drop-then-affirm dismissal never asserts, and there is **no** fragile "genuine"-veto so the honest oracle passes. Verified locally on genuine / dismissal / adjacent-cause / flat prose. Harden further against the real GPT/Claude texts at gate calibration.

### Cost

`hard`. cpus 2, mem 8 GB, **internet off** (route-b: the needed left/right-fist epochs for eegbci runs 4/8/12, ~9 subjects, are packaged offline in `data/eegbci_epochs.npz` with real run/trial provenance). Deps: mne + scikit-learn/numpy/scipy. Per-subject CSP+LDA over windowed epochs with the random and two grouped CV schemes; timeouts generous.
