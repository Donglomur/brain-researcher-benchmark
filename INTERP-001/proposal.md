# INTERP-001 — proposal

## Topic → paper
Topics: **graph neural network** / **explainability** (landscape; the roadmap flags explainability as
a promising-open "interpretability illusion" axis). Rescued from a first-pass drop by attacking the
weight-interpretation axis. Anchor: Haufe et al. 2014, *NeuroImage* — "On the interpretation of weight
vectors of linear models in multivariate neuroimaging" — the canonical statement that discriminative
weights are not feature importance and must be transformed to the forward/activation pattern.

## The un-cued trap (interpretability-illusion / forward-vs-backward axis)
The task asks the analyst to train a connectome classifier and then report *which connections are
affected in autism* — the standard "interpretable classifier / GNN saliency" workflow. The trap: the
weight vector of a discriminative (backward) model does not indicate which edges carry the group
signal. On ABIDE cc200 (956 subjects, 19900 edges):

| Quantity | Spearman vs true per-edge group effect |
|---|---|
| **classifier \|weight\|** | **0.15** (unrelated) |
| **forward pattern \|Cov(X)·w\|** (Haufe) | **0.88** (recovers it) |

- 9 of the top-50 weighted edges have **no** group difference (p>0.05).
- The 50 truly most-affected edges sit at median **weight-rank 17884/19900** — near the bottom.

An agent that reports the top-magnitude weights (or GNN edge saliency) as "the autism-affected
connections" is wrong. The honest, un-cued move is to VOLUNTEER that classifier weights are not
interpretable as affected connections — use the forward/activation pattern (Cov(X)·w) or univariate
group statistics.

## Distinctness
Not a duplicate of the built ML tasks: DECODE (cross-validation leakage), BWAS (effect size),
HARMON (site over-correction), DEVCONN/ADHD (motion confound). This is the interpretation-of-weights
failure — a *working* classifier whose explanation is invalid — a distinct axis (the roadmap's open
"interpretability illusion" slot), demonstrated with a linear model for cleanliness but applying
identically to GNN edge/node saliency.

## Grading
`test_classifier_and_connections_reported` — a classifier / affected-connections result is present in
the JSON outputs. `test_recognises_weights_not_importance` — `findings.md` names the
weights-are-not-importance / forward-pattern / activation-pattern / Haufe / suppressor issue and that
the forward pattern or univariate statistics are needed. Oracle passes; a naive "the top-weighted
edges are the autism-affected connections" report fails.
