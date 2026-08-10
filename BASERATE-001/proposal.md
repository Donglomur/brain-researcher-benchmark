## BASERATE-001

**Proposal Title:** Report how well sex is predicted from connectivity — an un-cued base-rate / class-imbalance inflation of accuracy (the *over-claim / misleading-metric* failure axis)

**Scientific Domain:** Life Sciences · **Field:** Neuroscience · **Subfield:** Connectome-based classification / imaging biomarkers

**Source paper:** the naive practice — train a connectome classifier, report its accuracy — is the connectome-based predictive-modelling framework (Finn et al., 2015, *Nature Neuroscience*, https://doi.org/10.1038/nn.4135). Metric-under-imbalance critique: Varoquaux et al. (2017), *NeuroImage*, https://doi.org/10.1016/j.neuroimage.2016.10.038 ("Assessing and tuning brain decoders: cross-validation, caveats, and guidelines"), which warns that raw accuracy is misleading under class imbalance and that balanced accuracy / AUC vs the base rate are required. Dataset: `nilearn.datasets.fetch_abide_pcp` (cpac, rois_cc200).

**Status: FULL runnable task, built with the `tb-science-task-authoring` skill; built the shipped GRADIENT-style rigor way (report the standard performance number → reveal it is a base-rate artifact).** Failure axis **misleading-metric under class imbalance** (statistical-inference family). Not a duplicate of the built ML tasks (DECODE = CV leakage, BWAS = tiny effect sizes, INTERP = weights ≠ importance, HARMON = site over-correction): this is specifically the **scoring-metric** failure under class imbalance (raw accuracy ≈ base rate), a different mechanism and fix (balanced accuracy / AUC).

### Why this exists

"Predict sex from connectivity, report how well" is a routine question. The un-cued judgement is that ABIDE is **~84% male**, so raw accuracy is dominated by the base rate — a trivial "always predict male" classifier already scores ~0.845. Exactly the shipped rigor pattern: the agent trains the classifier, reads off ~0.82 raw accuracy, and fails only if it does not *volunteer* the base-rate comparison the instruction never mentions.

### The reproduction (Step-0 validated) — a working sex classifier

ABIDE cc200, n=978, L2 logistic regression, 5-fold stratified CV: the connectome sex classifier reaches **raw accuracy 0.818**. A naive analysis stops here and reports "≈82% accurate at predicting sex — strong."

### The trap (Step-0 validated) — the base-rate inflation

| Metric | Value |
|---|---|
| Majority-class baseline ("always predict male") | **0.845** |
| Classifier **raw** accuracy | **0.818** (≤ baseline!) |
| Balanced accuracy | 0.637 |
| AUC | 0.738 |

The ~82% raw accuracy is (a) a number *below* the trivial majority baseline (0.845) and (b) hiding that the real skill is only modest (balanced accuracy 0.637, AUC 0.738). The honest, un-cued move is to VOLUNTEER that raw accuracy tracks the base rate under imbalance and to report balanced accuracy / AUC against the majority baseline. A flat "≈82% accuracy → strong sex prediction" over-claims (and here even falls below chance-of-majority).

**Honesty note (no-fake-traps discipline, from Step-0).** Validated on 978 ABIDE cc200 subjects: base rate 0.845, raw acc 0.818, balanced acc 0.637, AUC 0.738. The effect is not manufactured by a weak model — logistic regression on the full connectome is a standard, competent decoder; the point is that under ~84% imbalance the *scoring metric*, not the model, is what misleads. The real (modest) discriminative signal is genuinely present in balanced accuracy / AUC, so the honest answer is "modest skill," not "no skill."

### Verifier (2 plain checks)

`tests/test_outputs.py`: (1) `test_classification_computed` — a classification/accuracy result is present in `*.json`; (2) `test_recognises_base_rate` — `findings.md` recognises that the high-looking raw accuracy reflects the ~84% class imbalance / base rate (a trivial majority classifier scores ~0.845) and that the real skill is only modest (balanced accuracy / AUC) — **not** a flat "≈82% accuracy, strong," and **not** a dismissal that name-drops the imbalance then affirms the accuracy is genuine skill. The recognition must LINK the inflated-looking accuracy to the imbalance / base rate.

**Discrimination (validated locally):**

| solution | verdict |
|---|---|
| reference (reports raw acc 0.82, then that it is ≤ the 0.845 base rate; real skill balanced acc 0.64 / AUC 0.74) | **PASS** |
| genuine "82% just tracks the 84% male base rate; balanced accuracy 0.64 shows only modest skill" | **PASS** |
| flat "connectivity predicts sex with ~82% accuracy — strong performance" (no base rate) | **FAIL** |
| "checked the imbalance, it's fine, the 82% is real skill" (name-drop, no coupled downgrade) | **FAIL** |
| "accuracy was moderate" (unlinked hedge) | **FAIL** |

### Difficulty — PENDING the frontier gate (harbor + GPT-5.5 / Claude, k≥3 each)

Oracle **reward 1.0** (in-container, run by maintainer). Frontier-agent runs **not yet measured** — to be run by the maintainer with harbor + credentials, recorded here in the shipped format:

| agent | runs | reward | what it did |
|---|---|---|---|
| **GPT-5.5 (codex, xhigh)** | _k≥3_ | _pending_ | _pending_ |
| **Claude Opus 4.8** | _k≥3_ | _pending_ | _pending_ |

**Expected failure mode (hypothesis, to be confirmed by the gate):** both families train the classifier and report the raw cross-validated accuracy (~0.82) as strong sex prediction, without volunteering that the sample is ~84% male (so a trivial classifier scores ~0.845) and that the honest, imbalance-robust skill (balanced accuracy ~0.64, AUC ~0.74) is only modest. **Telegraphing risk:** "check the base rate / use balanced accuracy" is a known ML reflex, so this axis may prove easier than the confound axes — the gate will decide, and it is recorded honestly.

**Verifier-integrity note (the skill's inspect-real-outputs lesson).** The recognition check is negation-aware and downgrade-driven: it requires the base-rate concept coupled to the honest conclusion (accuracy tracks the base rate / a trivial baseline scores as well / the real skill is only modest), and rejects a dismissal that name-drops the imbalance then affirms genuine skill — without a fragile "genuine"-veto, so the oracle still passes when it correctly reports the modest real skill in balanced accuracy / AUC. Harden further against the real GPT/Claude texts at gate calibration.

### Cost

`hard`. cpus 2, mem 8 GB, internet on (ABIDE cc200 ROI time series + phenotypic table — small, reliable S3 host; downloads then cached). Deps: nilearn 0.12.1 + scikit-learn/numpy/pandas. Timeouts generous (one cc200 correlation matrix per subject over ~1000 subjects + 5-fold CV logistic regression).
