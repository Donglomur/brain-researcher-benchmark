## EEGLEAK-001

**Proposal Title:** Reproduce motor-imagery decoding from windowed EEG (CSP+LDA) — an un-cued windowing / cross-validation-leakage confound (the *leakage / CV-circularity* failure axis)

**Scientific Domain:** Life Sciences · **Field:** Neuroscience · **Subfield:** EEG decoding / brain–computer interfaces

**Source paper:** Ramoser, Müller-Gerking & Pfurtscheller (2000), *IEEE Trans. Rehabil. Eng.*, https://doi.org/10.1109/86.895946 ("Optimal spatial filtering of single trial EEG during imagined hand movement", CSP + linear classifier decodes left- vs right-hand imagery). Leakage/CV-circularity critique: Varoquaux (2017), *NeuroImage*; Lemm et al. (2011), *NeuroImage* ("Introduction to machine learning for brain imaging"); Abraham et al. (2014). Dataset: PhysioNet EEG Motor Movement/Imagery (eegbci, runs 4/8/12) via `mne.datasets.eegbci`. **Fills the explicitly-empty EEG cell of the leakage axis (DECODE is fMRI/Haxby).**

**Status: FULL runnable task, built with the `tb-science-task-authoring` skill; built the shipped way (reproduce the decoding headline → reveal the hidden confound), modelled on DEVCONN-001 / SOCIALBRAIN-001.** Differentiated SIBLING of DECODE: the leak here is induced by the analyst's *windowing* step (no ingrained run-blocking convention), so a solution that mimicked Haxby's leave-one-run-out does not mechanically pass.

### Why this exists

CSP+LDA decoding of motor imagery is a canonical BCI result; cutting each trial into overlapping windows to get more samples is common practice. Reproduced at face value it looks strong — high cross-validated accuracy. The un-cued judgement is that a **random k-fold over the windows leaks**: windows from the same trial are highly correlated and land in both train and test, so the classifier partly recognises the trial, not the class. Blocking the split by trial/run removes it and the accuracy drops to the true one-window-per-trial level. The agent is asked to reproduce the decoding accuracy and report whether it holds; it fails only if it does not *volunteer* the non-independence and the blocked-CV comparison the instruction never mentions. Failure axis **leakage / CV-circularity**, EEG modality — distinct from DECODE's fMRI temporal-block leakage.

### The reproduction (Step-0 validated) — the decoding accuracy holds at face value

eegbci runs 4/8/12, CSP+LDA, 9 subjects, 1.5 s windows (0.75 s step), random 5-fold over the windowed epochs: mean accuracy **0.77** — a strong, publishable-looking left-vs-right decoding result in the spirit of Ramoser (2000). A naive analysis stops here and reports ≈77% decodability.

### The trap (Step-0 validated) — a trial/run-blocked split drops it to the true level

| cross-validation scheme | accuracy |
|---|---|
| **random 5-fold over windows** | **0.77** |
| **trial/run-blocked** (no trial's windows split across train/test) | **0.60** |
| **true one-window-per-trial** (leave-one-run-out) | **0.60** |

The random k-fold is inflated by **+0.17** over the blocked scheme, and the blocked accuracy matches the true one-window-per-trial decodability — the honest number is ≈**0.60**, not ≈**0.77**. The inflation holds for **100%** of subjects. The honest answer volunteers this; a flat "≈77% decoding accuracy" over-states it. The instruction is un-cued: it names the CSP+LDA + windowing method in full, but **never mentions leakage, non-independence, same-trial windows, grouped/blocked cross-validation, or leave-one-run-out**.

**Honesty note (no-fake-traps discipline, from Step-0).** The blocked estimate is not a contrived deflation: it agrees with the independent true one-window-per-trial decodability (both ≈0.60), so 0.60 is the real signal and the +0.17 is the leak. Unlike DECODE (fMRI, where a run-blocking convention exists), EEG window-decoding has no such convention — random k-fold over windowed epochs is common practice — so the leak is easy to fall into and is the analyst's own un-cued choice.

### Verifier (2 plain checks)

`tests/test_outputs.py`: (1) `test_decoding_computed` — a decoding-accuracy result is present in `*.json`; (2) `test_recognises_window_leakage` — `findings.md` recognises that a random k-fold over windowed epochs leaks (windows from the same trial are non-independent, in both train and test → inflated), so the split must be blocked by trial/run and the honest accuracy is ≈0.60 — **not** a flat "≈77% accuracy," **not** merely naming the blocked fix, and **not** a dismissal ("we blocked the folds; accuracy held at 0.77"). The recognition must LINK the windowing/same-trial non-independence to the inflation.

**Discrimination (validated locally):**

| solution | verdict |
|---|---|
| reference (random 0.77 leaks; trial/run-blocked 0.60 matches the true level → honest ≈0.60) | **PASS** |
| genuine "same-trial windows in train and test inflate it; blocked CV drops to ~0.60" | **PASS** |
| flat "≈77% decoding accuracy" (no blocked check) | **FAIL** |
| "we blocked the folds by trial; accuracy held at 0.77, so windowing didn't inflate anything" (dismissal) | **FAIL** |
| "small sample / class imbalance may matter" (adjacent-but-wrong cause) | **FAIL** |

### Difficulty — PENDING the frontier gate (harbor + GPT-5.5 / Claude, k≥3 each)

Oracle passes both checks (validated end-to-end). Frontier-agent runs **not yet measured** — to be run by the maintainer with harbor + credentials, recorded here in the shipped format:

| agent | runs | reward | what it did |
|---|---|---|---|
| **GPT-5.5 (codex, xhigh)** | _k≥3_ | _pending_ | _pending_ |
| **Claude Opus 4.8** | _k≥3_ | _pending_ | _pending_ |

**Expected failure mode (hypothesis, to be confirmed by the gate):** both families window the trials, run a random k-fold, and report the ~0.77 accuracy as decodability, without volunteering — un-cued — that the windowed samples are non-independent so the split must be blocked by trial/run (true ≈0.60). This mirrors the measured behaviour on DEVCONN-001 and SOCIALBRAIN-001, where frontier families computed correctly yet failed to volunteer the single hidden check.

**Verifier-integrity note (the skill's inspect-real-outputs lesson).** The recognition check is negation-aware and downgrade-driven: a bare "blocked by trial/run" does **not** pass (dismissers name the fix while affirming 0.77); the coupled downgrades require the honest mechanism (same-trial near-copies in train and test; the number is inflated/fake; the blocked estimate drops to ~0.60) that a name-drop-then-affirm dismissal never asserts, and there is **no** fragile "genuine"-veto so the honest oracle passes. Harden further against the real GPT/Claude texts at gate calibration.

### Cost

`hard`. cpus 2, mem 8 GB, internet on (eegbci runs 4/8/12 for ~9 subjects via MNE/PhysioNet — small, cached after first run). Deps: mne + scikit-learn/numpy. Per-subject CSP+LDA over windowed epochs with two CV schemes; timeouts generous.
