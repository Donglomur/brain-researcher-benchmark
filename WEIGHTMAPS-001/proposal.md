## WEIGHTMAPS-001

**Proposal Title:** Characterise the autism-affected connections from an interpretable connectome classifier — an un-cued interpretation-of-weights illusion (the *forward-vs-backward / interpretability* failure axis)

**Scientific Domain:** Life Sciences · **Field:** Neuroscience · **Subfield:** Connectome machine learning / model interpretability

**Source paper:** the interpretable-connectome-classifier / GNN edge-saliency approach — Shen et al. (2017), *Nature Protocols*, https://doi.org/10.1038/nprot.2016.178 (connectome-based predictive modelling reads out the edges a model relies on); and graph-neural-network connectome models that report edge/node saliency as the affected connections. Interpretation-of-weights critique: Haufe et al. (2014), *NeuroImage*, https://doi.org/10.1016/j.neuroimage.2013.10.067 ("On the interpretation of weight vectors of linear models in multivariate neuroimaging"). Dataset: ABIDE cc200 (`nilearn.datasets.fetch_abide_pcp`, cpac, rois_cc200), shipped as a **packaged offline bundle** (`data/cc200_interp.npz`; no network).

**Status: FULL runnable task, built with the `tb-science-task-authoring` skill; the RIGOR genre (characterise X → the honest answer volunteers the readout is confounded), route-b offline (packaged .npz), modelled on TOPEDGES-001 / GRADIENT-001.** Failure axis **interpretability illusion / forward-vs-backward** (the roadmap's open "interpretability illusion" slot) — a *working* classifier whose explanation is invalid; a distinct axis from DECODE (CV leakage), BWAS (effect size), HARMON (site over-correction), DEVCONN/ADHD (motion), TOPEDGES (winner's curse). Demonstrated with a linear model for cleanliness, applying identically to GNN edge/node saliency.

### Why this exists

The "interpretable classifier / GNN saliency" workflow is a standard way to report which connections are altered in a condition. Characterised at face value it looks compelling — the classifier separates autism from controls above chance, and its top-magnitude readout gives a ranked list of "affected" edges. The un-cued judgement is that the weight vector of a discriminative (backward) model does **not** indicate which edges carry the group signal — a large weight can sit on a noise-cancelling ("suppressor") edge with no group difference, and a genuinely affected edge can get a near-zero weight. Exactly the shipped pattern: the agent trains a working classifier, reads it out correctly, and fails only if it does not *volunteer* the interpretation check the instruction never mentions.

### The reproduction and the trap (validated) — held privately

The validated numbers (n, nested-CV AUC, Spearman of the raw weights vs the true group effect, the Haufe forward-pattern recovery, the top-weighted-edge null count, and the median weight-rank of the truly-affected edges) and the oracle receipt are in the **private, git-ignored `calibration.md`** (rule 4). In brief: a nested-CV logistic-regression connectome classifier separates ASD from controls above chance, but its top-magnitude **weights** barely match the true per-edge group difference (many top-weighted edges have no group difference, and the truly most-affected edges rank near the **bottom** by weight), whereas the **Haufe forward/activation pattern** A = Cov(X)·w recovers them. So the top classifier weights (or GNN edge saliency) are **not** the autism-affected connections; the forward pattern or univariate group statistics are. The instruction is un-cued: it names the analysis and the method in full, but **never mentions the forward/activation pattern, Haufe, suppressor edges, backward-vs-forward models, or univariate group statistics**.

**Honesty note (no-fake-traps discipline).** The illusion is real and the corrective was measured, not assumed: the forward pattern is computed without ever forming the 19,900×19,900 covariance (A = Xᶜᵀ(Xᶜ w)/(n−1)), and its |A| ranking recovers the univariate group-difference ranking while the |weight| ranking does not (numbers in `calibration.md`). Demonstrated with a linear model for cleanliness; the weight-vs-forward-pattern problem applies identically to GNN edge/node saliency (a backward model in disguise).

### Verifier (2 plain checks)

`tests/test_outputs.py`: (1) `test_connections_computed` — validates the actual DATA: the reported top affected connections are real cc200 ROI-pairs in [0,199] with plausible edge-level values, a sane subject count, a plausible classifier AUC (if reported), and — where the recovery numbers are present — that the **forward pattern genuinely recovers** the affected edges while the raw **weights do not** (the hidden check points the right way; a reversed or fabricated one fails). (2) `test_recognises_weights_not_importance` — `findings.md` recognises that discriminative classifier weights (or GNN saliency) are **not** the affected connections and that the forward/activation pattern or univariate group statistics are needed — **not** a flat "the top edges are the affected connections," and **not** merely name-dropping the forward pattern / Haufe while affirming the top weights AS the affected edges. The recognition must LINK the weights-are-not-importance conclusion to the readout.

**Discrimination (validated locally):**

| solution | verdict |
|---|---|
| reference (nested-CV classifier, then reports the weights are unrelated to the group effect; forward pattern recovers it) | **PASS — reward 1.0** |
| genuine "top weights ≠ affected edges; used per-edge group t-tests / forward pattern instead" | **PASS** |
| flat "the top-weighted edges are the autism-affected connections" (no interpretation check) | **FAIL (recognition)** |
| "computed the Haufe activation pattern, and the top weights already are the affected edges" (name-drop, no coupled downgrade) | **FAIL** |
| fabricated (fake out-of-range ROI-pairs, or reversed hidden check: weights "recover" / forward "fails") | **FAIL (data)** |
| empty submission | **FAIL** |

### Difficulty — PENDING the frontier gate (harbor + GPT-5.5 / Claude, k≥3 each)

Oracle **reward 1.0** (offline, packaged .npz, run by maintainer). Frontier-agent runs **not yet measured** — to be run by the maintainer with harbor + credentials, recorded here in the shipped format:

| agent | runs | reward | what it did |
|---|---|---|---|
| **GPT-5.5 (codex, xhigh)** | _k≥3_ | _pending_ | _pending_ |
| **Claude Opus 4.8** | _k≥3_ | _pending_ | _pending_ |

**Expected failure mode (hypothesis, to be confirmed by the gate):** both families train a working classifier and report its top-magnitude weights (or GNN saliency) as the autism-affected connections, but — un-cued — do **not** volunteer that discriminative weights are not feature importance (a large weight can fall on a suppressor edge with no group difference) and that the forward/activation pattern (Cov(X)·w) or univariate group statistics are needed. This mirrors the measured behaviour on DEVCONN-001 (motion) and SOCIALBRAIN-001 (GSR), where both frontier families computed correctly yet failed to volunteer the single hidden check.

**Verifier-integrity note (the skill's inspect-real-outputs lesson).** The recognition check is negation-aware and downgrade-driven: it requires the honest CONCLUSION coupled to the weights (e.g. "the weights are unrelated / misleading," "the truly affected edges carry near-zero weight," "used per-edge group t-tests instead"), and rejects a name-drop-then-affirm dismissal ("computed the Haufe pattern, and the top weights already are the affected edges") without a fragile "genuine"-veto — which also lets the honest oracle pass when it notes the forward pattern DOES recover the affected edges (contrast). The data check additionally enforces the forward-vs-backward direction on the reported numbers, so a fabricated/reversed submission fails. Harden further against the real GPT/Claude texts at gate calibration.

### Cost

`hard`. cpus 2, mem 8 GB, **internet off** (packaged offline bundle `data/cc200_interp.npz` ≈ 75 MB: float32 subject×edge Fisher-z cc200 connectomes + diagnosis). Deps: numpy/scipy/scikit-learn (nested CV + logistic regression; forward pattern via numpy matmul without forming the P×P covariance). Oracle runtime ≈ 15 s (nested CV dominates).
