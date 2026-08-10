## INTERP-001

**Proposal Title:** Characterise the autism-affected connections from an interpretable connectome classifier — an un-cued interpretation-of-weights illusion (the *forward-vs-backward / interpretability* failure axis)

**Scientific Domain:** Life Sciences · **Field:** Neuroscience · **Subfield:** Connectome machine learning / model interpretability

**Source paper:** the interpretable-connectome-classifier / GNN edge-saliency approach — Shen et al. (2017), *Nature Protocols*, https://doi.org/10.1038/nprot.2016.178 (connectome-based predictive modelling reads out the edges a model relies on); and graph-neural-network connectome models that report edge/node saliency as the affected connections. Interpretation-of-weights critique: Haufe et al. (2014), *NeuroImage*, https://doi.org/10.1016/j.neuroimage.2013.10.067 ("On the interpretation of weight vectors of linear models in multivariate neuroimaging"). Dataset: `nilearn.datasets.fetch_abide_pcp` (cpac, rois_cc200).

**Status: FULL runnable task, built with the `tb-science-task-authoring` skill; the RIGOR genre (characterise X → the honest answer volunteers the readout is confounded), modelled on GRADIENT-001.** Failure axis **interpretability illusion / forward-vs-backward** (the roadmap's open "interpretability illusion" slot) — a *working* classifier whose explanation is invalid; a distinct axis from DECODE (CV leakage), BWAS (effect size), HARMON (site over-correction), DEVCONN/ADHD (motion). Demonstrated with a linear model for cleanliness, applying identically to GNN edge/node saliency.

### Why this exists

The "interpretable classifier / GNN saliency" workflow is a standard way to report which connections are altered in a condition. Characterised at face value it looks compelling — the classifier separates autism from controls above chance, and its top-magnitude readout gives a ranked list of "affected" edges. The un-cued judgement is that the weight vector of a discriminative (backward) model does **not** indicate which edges carry the group signal — a large weight can sit on a noise-cancelling ("suppressor") edge with no group difference, and a genuinely affected edge can get a near-zero weight. Exactly the shipped pattern: the agent trains a working classifier, reads it out correctly, and fails only if it does not *volunteer* the interpretation check the instruction never mentions.

### The reproduction (Step-0 validated) — the classifier works and yields "affected connections"

ABIDE cc200, ~956 subjects, 19900 edges: an L2 logistic-regression connectome classifier on the vectorised FC edges separates ASD from controls above chance, and reading out the trained model gives a ranked set of top "most affected" edges. A naive analysis reports these top edges as the autism-affected connections.

### The trap (Step-0 validated) — classifier weights are not the affected connections

The discriminative weight ranking barely matches the true per-edge group difference, whereas the Haufe forward/activation pattern recovers it:

| quantity | Spearman vs true per-edge group effect (\|t\|) |
|---|---|
| classifier \|weight\| | **0.15** (essentially unrelated) |
| forward pattern \|Cov(X)·w\| (Haufe) | **0.88** (recovers it) |

- **9 of the top-50** weighted edges have **no** group difference (p > 0.05).
- The 50 truly most-affected edges sit at a median **weight-rank of 17884 / 19900** — near the **bottom** by classifier weight.

So the top-magnitude classifier weights (or GNN edge saliency) are **not** the autism-affected connections; the forward/activation pattern A = Cov(X)·w or univariate group statistics recover them. The honest answer volunteers this; a confident "these top edges are the autism-affected connections" is wrong. The instruction is un-cued: it names the analysis and the method in full, but **never mentions the forward/activation pattern, Haufe, suppressor edges, backward-vs-forward models, or univariate group statistics**.

**Honesty note (no-fake-traps discipline, from Step-0).** The illusion is real and the corrective was measured, not assumed: Spearman(|w|, |effect|) ≈ 0.15 vs Spearman(|A|, |effect|) ≈ 0.88 on the same edges, and the forward pattern is computed without ever forming the 19900×19900 covariance (A = Xᶜᵀ(Xᶜ w)/(n−1)). Demonstrated with a linear model for cleanliness; the weight-vs-forward-pattern problem applies identically to GNN edge/node saliency (a backward model in disguise).

### Verifier (2 plain checks)

`tests/test_outputs.py`: (1) `test_classifier_and_connections_reported` — a classifier / affected-connections result is present in `*.json`; (2) `test_recognises_weights_not_importance` — `findings.md` recognises that discriminative classifier weights (or GNN saliency) are **not** the affected connections and that the forward/activation pattern or univariate group statistics are needed — **not** a flat "the top edges are the affected connections," and **not** merely name-dropping the forward pattern / Haufe while affirming the top weights AS the affected edges. The recognition must LINK the weights-are-not-importance conclusion to the readout.

**Discrimination (validated locally):**

| solution | verdict |
|---|---|
| reference (trains the classifier, then reports the weights are unrelated to the group effect; forward pattern recovers it) | **PASS — reward 1.0** |
| genuine "top weights ≠ affected edges; used per-edge group t-tests / forward pattern instead" | **PASS** |
| flat "the top-weighted edges are the autism-affected connections" (no interpretation check) | **FAIL** |
| "computed the Haufe activation pattern, and the top weights already are the affected edges" (name-drop, no coupled downgrade) | **FAIL** |
| vague "results were noisy" (unlinked hedge) | **FAIL** |

### Difficulty — PENDING the frontier gate (harbor + GPT-5.5 / Claude, k≥3 each)

Oracle **reward 1.0** (in-container, run by maintainer). Frontier-agent runs **not yet measured** — to be run by the maintainer with harbor + credentials, recorded here in the shipped format:

| agent | runs | reward | what it did |
|---|---|---|---|
| **GPT-5.5 (codex, xhigh)** | _k≥3_ | _pending_ | _pending_ |
| **Claude Opus 4.8** | _k≥3_ | _pending_ | _pending_ |

**Expected failure mode (hypothesis, to be confirmed by the gate):** both families train a working classifier and report its top-magnitude weights (or GNN saliency) as the autism-affected connections, but — un-cued — do **not** volunteer that discriminative weights are not feature importance (a large weight can fall on a suppressor edge with no group difference) and that the forward/activation pattern (Cov(X)·w) or univariate group statistics are needed. This mirrors the measured behaviour on DEVCONN-001 (motion) and SOCIALBRAIN-001 (GSR), where both frontier families computed correctly yet failed to volunteer the single hidden check.

**Verifier-integrity note (the skill's inspect-real-outputs lesson).** The recognition check is negation-aware and downgrade-driven: it requires the honest CONCLUSION coupled to the weights (e.g. "the weights are unrelated / misleading," "the truly affected edges carry near-zero weight," "used per-edge group t-tests instead"), and rejects a name-drop-then-affirm dismissal ("computed the Haufe pattern, and the top weights already are the affected edges") without a fragile "genuine"-veto — which also lets the honest oracle pass when it notes the forward pattern DOES recover the affected edges (contrast). Harden further against the real GPT/Claude texts at gate calibration.

### Cost

`hard`. cpus 2, mem 8 GB, internet on (ABIDE cc200 ROI time series — small, reliable S3 host). Deps: nilearn 0.12.1 + scikit-learn/scipy/numpy/pandas (no extra deps; forward pattern via numpy matmul without forming the P×P covariance). Oracle runtime dominated by loading ~956 cc200 time series and one logistic-regression fit.
