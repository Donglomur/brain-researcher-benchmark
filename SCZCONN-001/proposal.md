## SCZCONN-001

**Proposal Title:** Is functional connectivity a schizophrenia biomarker? (UCLA CNP / ds000030) — an un-cued diagnostic-non-specificity failure (the *over-claim / robustness* axis on a NEW multi-disorder clinical cohort)

**Scientific Domain:** Life Sciences · **Field:** Neuroscience · **Subfield:** Psychiatric biomarkers / connectome classification / external validity

**Source paper:** the standard connectivity-biomarker practice — train a patient-vs-control classifier on resting-state functional connectivity and report its cross-validated accuracy as a disorder biomarker. Statistical critique (the un-cued axis, **kept out of the instruction**): Arbabshirani et al. (2017), *NeuroImage*, https://doi.org/10.1016/j.neuroimage.2016.02.079 ("Single subject prediction of brain disorders … promises and pitfalls" — a classifier that separates a patient group from controls is routinely reported as a biomarker for that disorder but is rarely tested for SPECIFICITY against other disorders). Data: UCLA Consortium for Neuropsychiatric Phenomics (Poldrack et al. 2016), OpenNeuro **ds000030**, reached via S3 + a lightweight dipy-affine + CompCor pipeline (provenance in `data/`). **The first task built on OpenNeuro multi-disorder clinical data** — proves the clinical growth reserve is unlockable without a data-use agreement.

**Status: FULL runnable task, built with the `tb-science-task-authoring` skill.** Rigor / characterise genre (like GRADIENT-001): the naive narrative is a general practice with only a *critique* paper behind the hidden check, so there is no headline number to "reproduce" — the task asks to characterise whether connectivity is a valid schizophrenia biomarker, and the honest answer volunteers the specificity failure. Failure axis **over-claim / robustness** on a genuinely **NEW diagnostic-non-specificity** cell (impossible on the single-disorder cached datasets — ABIDE=autism only, ADHD-200=ADHD only).

### Why this exists

Reporting "connectivity classifies schizophrenia at AUC ~0.8, therefore it is a schizophrenia biomarker" is a routine translational claim. The un-cued judgement is that the classifier **works but is not schizophrenia-specific**: the very same schizophrenia-vs-control classifier, applied to bipolar patients it was never trained on, still separates them from controls — so it marks the **psychosis spectrum / shared illness**, not schizophrenia per se. The `.npz` ships the control, schizophrenia, bipolar, and ADHD labels; the agent must, un-cued, notice the other groups and test specificity. It fails only if it does not *volunteer* that check.

### The face-value result (Step-0 validated) — a real schizophrenia classifier

UCLA CNP connectomes (Harvard-Oxford 48-ROI, 1128 edges), ~30 per group, L2 logistic regression: schizophrenia vs control **5-fold CV AUC = 0.82** (held-out ~0.78) — a real, above-chance classifier. A naive analysis stops here and reports connectivity as a schizophrenia biomarker.

### The trap (Step-0 validated) — the "schizophrenia biomarker" is not diagnosis-specific

Training SCHZ-vs-control, then applying that same classifier to other disorders against **held-out** controls (no control reuse):

| | AUC |
|---|---|
| Schizophrenia vs control (CV) | **0.82** (held-out **0.78**) — real |
| SCHZ classifier → **bipolar** vs control (held-out ctrls) | **0.62 ± 0.08** — still separates |
| SCHZ classifier → ADHD vs control | **0.49 ± 0.07** — chance |

The "schizophrenia biomarker" retains real power for **bipolar** (0.62), so it marks the **psychosis spectrum**, not schizophrenia specifically. ADHD at chance argues against a generic-patient / head-motion confound (ADHD patients move most). The honest, un-cued move is to VOLUNTEER the specificity failure. The instruction is un-cued: it asks to build the schizophrenia classifier and judge whether it is a valid schizophrenia biomarker, but **never mentions specificity, bipolar, ADHD, other disorders, cross-disorder transfer, or the psychosis spectrum**.

**Honest risks (for the difficulty gate).** Lightweight preprocessing (affine-only registration + CompCor, not fMRIPrep), so the connectomes are noisier than a standard derivative; the effect (0.82 / 0.62 / 0.49) reproduces but the exact AUCs would shift with better preprocessing (provenance + build scripts shipped in `data/`). The connectomes are **provided as data** (the full pipeline is ~80 min, beyond an oracle timeout). Bipolar transfer is moderate (0.62 ± 0.08); the ADHD-at-chance contrast is what makes it a specificity story rather than a generic confound.

### Verifier (2 plain checks)

`tests/test_outputs.py`: (1) `test_classification_computed` — a schizophrenia-classification result (AUC/accuracy) is present in `*.json`; (2) `test_recognises_nonspecificity` — `findings.md` recognises the classifier is **not schizophrenia-specific** — it also separates bipolar from controls, so it marks a shared / psychosis-spectrum / transdiagnostic signal (or over-states the schizophrenia claim) — **not** a flat "connectivity classifies schizophrenia at 0.82, a valid biomarker," and **not** a note-then-dismiss ("also detects bipolar, but that's comorbidity — still a workable schizophrenia marker").

**Discrimination (validated locally):**

| solution | verdict |
|---|---|
| reference (reports AUC 0.82, then volunteers bipolar transfer 0.62 vs ADHD 0.49 chance → psychosis-spectrum, not schizophrenia-specific) | **PASS** |
| genuine "SCHZ 0.82 but the same model separates bipolar 0.62 → not specific" | **PASS** |
| flat "connectivity classifies schizophrenia at 0.82, a valid biomarker" (no specificity) | **FAIL** |
| "also detects bipolar (comorbidity), still a workable schizophrenia marker" (note-then-dismiss, no coupled downgrade) | **FAIL** |

### Difficulty — PENDING the frontier gate (harbor + GPT-5.5 / Claude, k≥3 each)

Oracle **reward 1.0** (in-container, run by maintainer). Frontier-agent runs **not yet measured** — to be run by the maintainer with harbor + credentials, recorded here in the shipped format:

| agent | runs | reward | what it did |
|---|---|---|---|
| **GPT-5.5 (codex, xhigh)** | _k≥3_ | _pending_ | _pending_ |
| **Claude Opus 4.8** | _k≥3_ | _pending_ | _pending_ |

**Expected failure mode (hypothesis, to be confirmed by the gate):** both families train the classifier correctly, get a real above-chance schizophrenia-vs-control AUC (~0.8), and report connectivity as a schizophrenia biomarker, but — un-cued — do **not** notice the other diagnostic groups in the data and test specificity, so they never volunteer that the classifier also separates bipolar (marking the psychosis spectrum, not schizophrenia). This mirrors DEVCONN-001 (motion) and SOCIALBRAIN-001 (GSR): correct computation, hidden check not volunteered.

**Verifier-integrity note (the skill's inspect-real-outputs lesson).** The recognition check is negation-aware: the honest conclusion here is itself a negation ("not schizophrenia-specific", "wouldn't trust it as a schizophrenia test"), so those phrases live in the plain-match `absence` set, while the positive non-specific reading (a shared / psychosis-spectrum / transdiagnostic signal, or over-states) is the coupled downgrade. The raw "also detects bipolar" observation is NOT a downgrade on its own — a dismisser uses the same words then explains them away as comorbidity — so it fails WITHOUT a fragile "genuine"-veto, which also lets the honest oracle pass. Harden further against the real GPT/Claude texts at gate calibration.

### Cost

`hard`. cpus 2, mem 8 GB, internet on (per environment). The connectomes are **provided** in `data/cnp_connectomes.npz`, so the analysis itself needs no runtime download. Deps: scikit-learn + numpy (L2 logistic regression, stratified CV, held-out transfer). Timeouts generous (classification + 30-seed transfer over ~120 subjects).
