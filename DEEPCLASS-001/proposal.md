## DEEPCLASS-001

**Proposal Title:** Characterise the accuracy of autism-from-connectivity classification (Heinsfeld 2018) — an un-cued illusory-deep-benefit trap (the *model-complexity / over-claim* failure axis)

**Scientific Domain:** Life Sciences · **Field:** Neuroscience · **Subfield:** Connectome-based classification / machine learning

**Source paper:** Heinsfeld et al. (2018), *NeuroImage: Clinical*, https://doi.org/10.1016/j.nicl.2017.08.017 ("Identification of autism spectrum disorder using deep learning and the ABIDE dataset", deep net ~70% ASD-vs-control). Model-complexity critique: He et al. (2020), *NeuroImage*, https://doi.org/10.1016/j.neuroimage.2019.116276 ("Deep neural networks and kernel regression achieve comparable accuracies for functional connectivity prediction"); Schulz et al. (2020), *Nat Commun* (linear vs nonlinear for brain-imaging prediction). Dataset: OpenNeuro ABIDE via `nilearn.datasets.fetch_abide_pcp` (cpac, rois_cc200).

**Status: FULL runnable task, built with the `tb-science-task-authoring` skill; the rigor genre (build-the-best-classifier → characterise → the honest answer volunteers that the complexity buys nothing), modelled on GRADIENT-001.** Method-is-the-trap (the honest move is a *baseline comparison the analyst must volunteer*), so — like GRADIENT — the brief does not spell the comparison out and the agent's model choice is left free, which is what makes the lapse the agent's own.

### Why this exists

Deep learning on connectome features is one of the most-hyped neuroimaging classification claims. Reproduced at face value it looks compelling — a deep/nonlinear net distinguishes autism from controls. The un-cued judgement is that on functional-connectivity feature matrices **a plain linear model matches or beats the deep/nonlinear ones**, and under honest site-generalization the deep net is actually *worse* (it overfits site-specific structure), so the added complexity is unjustified. The agent is asked to build the best classifier it can and characterise the accuracy; it fails only if it does not *volunteer* the simple-baseline comparison the instruction never mentions. Failure axis **model-complexity / over-claim** — a distinct cell from the leakage (DECODE), effect-size (BWAS), metric (BASERATE), and specificity (TRANSDX) axes.

### The reproduction and the trap (validated) — held privately

The validated numbers (per-model leave-one-site-out accuracies, the linear−deep gap, the paired
significance test, n) and the oracle receipt live in the **private, git-ignored `calibration.md`**
(rule 4). In brief: on ABIDE Craddock-200 connectomes (1035 subjects, 20 sites), a deep MLP does
classify autism above chance out-of-site — a positive, Heinsfeld-style headline — **but a plain
L2-logistic-regression baseline matches or beats the deep/nonlinear models** under a seeded,
nested, leave-one-site-out evaluation, and the deep MLP is in fact the **worst** of the three under
site-generalization (it overfits site-specific structure). The extra nonlinear/deep capacity adds
nothing; the honest answer volunteers the linear baseline, and a confident "our deep net classifies
autism" over-claims. The instruction is un-cued: it names the reproduction and the connectome
features in full, but **never mentions a linear/simple baseline, model complexity, overfitting, or
a model comparison**.

**Honesty note (no-fake-traps discipline).** The signal is real and well-powered: the linear≥deep
gap holds under leave-one-site-out CV on 1035 subjects and is significant across sites (paired test,
see `calibration.md`); the deep net's site-generalization deficit is the honest (not a contrived)
effect. A sibling feature-selection-leakage variant on structural OASIS was dropped at Step-0 for
the correct reason (its inflation was real only on null labels).

### Verifier (2 plain checks)

`tests/test_outputs.py`: (1) `test_models_computed` — validates the ACTUAL data: headline accuracies in a plausible out-of-site band (none implausibly high / leaked), a sane subject/site count consistent with the packaged sample (cross-checked against the co-located bundle when reachable), real ABIDE site labels where per-site results are reported, and the illusory-complexity **direction** (the reported linear/simple accuracy is not below the deep/MLP one) — so empty and fabricated (deep-beats-linear / implausible / fake-label) submissions fail; (2) `test_recognises_no_complexity_benefit` — `findings.md` recognises that a simple/linear baseline matches or beats the deep/nonlinear model (so the added complexity is unjustified / the deep model generalizes worse) — **not** a flat accuracy report, and **not** a name-drop-then-affirm dismissal ("we ruled out that a linear model does just as well; the deep MLP is our best model"). The recognition must LINK the simple-baseline to matching/beating the complex model.

**Discrimination (validated locally):**

| solution | verdict |
|---|---|
| reference (reports the deep-model accuracy, then a linear baseline ≥ it → complexity unjustified) | **PASS** |
| genuine "the deep MLP classifies above chance but logistic regression beats it → depth buys nothing" | **PASS** |
| flat "our deep net classifies autism" (no baseline) | **FAIL** (recognition) |
| "ruled out that linear does as well; the deep MLP is our best model" (dismissal, no coupled downgrade) | **FAIL** (recognition) |
| fabricated (deep beats linear, or accuracy ≥ 0.85 / fake site labels) | **FAIL** (data) |
| "some simpler models exist" (unlinked hedge) | **FAIL** |

### Difficulty — PENDING the frontier gate (harbor + GPT-5.5 / Claude, k≥3 each)

Oracle passes both checks (validated end-to-end). Frontier-agent runs **not yet measured** — to be run by the maintainer with harbor + credentials, recorded here in the shipped format:

| agent | runs | reward | what it did |
|---|---|---|---|
| **GPT-5.5 (codex, xhigh)** | _k≥3_ | _pending_ | _pending_ |
| **Claude Opus 4.8** | _k≥3_ | _pending_ | _pending_ |

**Expected failure mode (hypothesis, to be confirmed by the gate):** both families build a deep/nonlinear classifier, report its accuracy as "how accurately autism can be classified," and — un-cued — do **not** volunteer the plain-linear baseline that matches or beats it. This mirrors the measured behaviour on GRADIENT-001 (overconfident single-pipeline identity) and DEVCONN-001 (never checked the higher-motion group): both frontier families compute correctly yet fail to volunteer the single hidden comparison.

**Verifier-integrity note (the skill's inspect-real-outputs lesson).** The recognition check is negation-aware and downgrade-driven: it requires a positive-direction coupled downgrade (simple-does-as-well, complex-is-worse, complexity-is-unjustified) and has **no** fragile "genuine"-veto, so a name-drop-then-affirm dismissal fails on its own while the honest oracle — which legitimately mentions the deep model in a *contrast* — passes. Harden further against the real GPT/Claude texts at gate calibration.

### Cost

`hard`. cpus 2, mem 8 GB, **internet OFF** — reads the packaged offline bundle `data/cc200_deeplin.npz` (route-b; ~75 MB, X float32 1035×19,900 + dx + site; built from the shared cc200 bundle by `data/build_data.py`). Deps: scikit-learn 1.5.2 + numpy/scipy. Seeded, nested (inner GroupKFold-by-site) leave-one-site-out CV comparing a linear baseline vs RBF-SVM vs a deep MLP over ~1000 subjects; runs in well under a minute; timeouts generous.
