## SEXCLASS-001

**Proposal Title:** Report how well sex is predicted from connectivity — an un-cued base-rate / class-imbalance inflation of accuracy (the *over-claim / misleading-metric* failure axis)

**Scientific Domain:** Life Sciences · **Field:** Neuroscience · **Subfield:** Connectome-based classification / imaging biomarkers

**Source paper:** the naive practice — train a connectome classifier, report its accuracy — is the connectome-based predictive-modelling framework (Finn et al., 2015, *Nature Neuroscience*, https://doi.org/10.1038/nn.4135). Metric-under-imbalance critique: Varoquaux et al. (2017), *NeuroImage*, https://doi.org/10.1016/j.neuroimage.2016.10.038 ("Assessing and tuning brain decoders: cross-validation, caveats, and guidelines"), which warns that raw accuracy is misleading under class imbalance and that balanced accuracy / AUC vs the base rate are required. Dataset: ABIDE cc200 connectomes (`nilearn.datasets.fetch_abide_pcp`, cpac, rois_cc200), packaged offline as `data/cc200_baserate.npz`.

**Status: FULL runnable task, built with the `tb-science-task-authoring` skill; built the shipped rigor way (report the standard performance number → reveal it is a base-rate artifact), route-b offline (packaged bundle, `allow_internet=false`).** Failure axis **misleading-metric under class imbalance** (statistical-inference family). Not a duplicate of the built ML tasks (DECODE = CV leakage, BWAS = tiny effect sizes, INTERP = weights ≠ importance, HARMON = site over-correction): this is specifically the **scoring-metric** failure under class imbalance (raw accuracy ≈ base rate), a different mechanism and fix (balanced accuracy / AUC).

**Method repair applied (maintainer #14):** feature standardisation is done **inside** the cross-validation pipeline (sklearn `Pipeline`, fit on train folds only — no leakage), and the reference reports class-balanced baselines (balanced accuracy, AUC, and the majority-class base rate).

### Why this exists

"Predict sex from connectivity, report how well" is a routine question. The un-cued judgement is that ABIDE is heavily male, so raw accuracy is dominated by the base rate — a trivial "always predict male" classifier already scores about the same. Exactly the shipped rigor pattern: the agent trains the classifier, reads off the raw accuracy, and fails only if it does not *volunteer* the base-rate comparison the instruction never mentions.

### The reproduction and the trap (validated) — held privately

The validated numbers (n, base rate, raw accuracy, balanced accuracy, AUC, per-class recall) and the oracle receipt are in the **private, git-ignored `calibration.md`** (rule 4). In brief: a competent cross-validated connectome sex classifier reaches a high-looking raw accuracy that is essentially the majority base rate — it does **not** beat a trivial "always predict male" baseline — while the honest, imbalance-robust metrics (balanced accuracy / AUC) reveal only modest real skill. The signal is genuinely present (modest), so the honest answer is "modest skill," not "no skill" and not "strong." The instruction is un-cued (never mentions base rate / class imbalance / balanced accuracy).

### Verifier (2 plain checks)

`tests/test_outputs.py`: (1) `test_classification_computed` — validates the **actual per-subject data**: real out-of-fold predictions (`predictions.csv`) over a genuine ~85% class imbalance, with metrics **recomputed from the predictions** that are consistent with what is reported and that exhibit the base-rate paradox (raw accuracy does not beat the majority baseline; real skill only modest). Empty and fabricated (fake 50/50 labels, or a real base rate but over-claimed near-perfect skill) submissions fail. (2) `test_recognises_base_rate` — `findings.md` recognises that the high-looking raw accuracy reflects the class imbalance / base rate (a trivial majority classifier scores as well or better) and that the real skill is only modest (balanced accuracy / AUC) — **not** a flat "≈84% accuracy, strong," and **not** a dismissal that name-drops the imbalance then affirms the accuracy is genuine skill. The recognition must LINK the inflated-looking accuracy to the imbalance / base rate.

**Discrimination (validated locally, offline):**

| solution | verdict |
|---|---|
| reference (reports the raw accuracy, then that it is ≤ the base rate; real skill only modest in balanced accuracy / AUC) | **PASS** |
| genuine "the raw accuracy just tracks the male base rate; balanced accuracy shows only modest skill" | **PASS** |
| flat "connectivity predicts sex with ~84% accuracy — strong performance" (no base rate) | **FAIL** (recognition) |
| "checked the imbalance, it's fine, the accuracy is real skill" (name-drop, no coupled downgrade) | **FAIL** (recognition) |
| "accuracy was moderate" (unlinked hedge) | **FAIL** (recognition) |
| fabricated (fake 50/50 labels, or over-claimed near-perfect metrics) | **FAIL** (data) |

### Difficulty — PENDING the frontier gate (harbor + GPT-5.5 / Claude, k≥3 each)

Oracle **reward 1.0** (offline, in-container). Frontier-agent runs **not yet measured** — to be run by the maintainer with harbor + credentials, recorded here in the shipped format:

| agent | runs | reward | what it did |
|---|---|---|---|
| **GPT-5.5 (codex, xhigh)** | _k≥3_ | _pending_ | _pending_ |
| **Claude Opus 4.8** | _k≥3_ | _pending_ | _pending_ |

**Expected failure mode (hypothesis, to be confirmed by the gate):** both families train the classifier and report the raw cross-validated accuracy as strong sex prediction, without volunteering that the sample is heavily male (so a trivial classifier scores as well) and that the honest, imbalance-robust skill (balanced accuracy / AUC) is only modest. **Telegraphing risk:** "check the base rate / use balanced accuracy" is a known ML reflex, so this axis may prove easier than the confound axes — the gate will decide, and it is recorded honestly.

**Verifier-integrity note (the skill's inspect-real-outputs lesson).** The recognition check is negation-aware and downgrade-driven: it requires the base-rate concept coupled to the honest conclusion (accuracy tracks the base rate / a trivial baseline scores as well / the real skill is only modest), and rejects a dismissal that name-drops the imbalance then affirms genuine skill — without a fragile "genuine"-veto, so the oracle still passes when it correctly reports the modest real skill in balanced accuracy / AUC. The data check recomputes the metrics from the real per-subject predictions, so fabricated labels/values fail. Harden further against the real GPT/Claude texts at gate calibration.

### Cost

`hard`. cpus 2, mem 8 GB, **internet off** (packaged cc200 bundle `data/cc200_baserate.npz` — no download, no network). Deps: scikit-learn/numpy. Timeouts generous (5-fold CV logistic regression over ~1000 subjects × 19,900 edges).
