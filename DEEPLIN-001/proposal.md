# DEEPLIN-001 — proposal (rescued mislabeled-duplicate)

## Topic → paper
Topic: **convolutional neural network / deep learning** (landscape). Originally flagged DUP-of-DECODE
and held; on re-examination against the grid (axis × dataset × modality × lever), it is a **different,
empty cell** — model-complexity / illusory-deep-benefit — not the leakage axis. Anchor: He et al. 2020,
*NeuroImage* (deep nets ≈ kernel regression for FC prediction); Schulz et al. 2020, *Nat Commun*;
Heinsfeld et al. 2018 (deep learning on ABIDE).

## The un-cued trap (model-complexity axis — no built task covers it)
The task asks to build the "best-performing" autism classifier and judge whether the approach is
appropriate — without mentioning baselines. The trap: on connectome features, deep/nonlinear models do
NOT beat a linear one. Validated (ABIDE, 1035 subjects, 20 sites, **leave-one-site-out** CV):

| model | accuracy |
|---|---|
| linear logistic regression | **0.670** |
| RBF-SVM | 0.640 |
| MLP(100) | 0.619 |
| MLP(256,64) | 0.619 |

Linear is best; the deep MLP is worst under honest site-generalization (it overfits site). An agent that
trains a deep net and reports its accuracy over-states the case — the honest, un-cued move is to compare
to a linear baseline and note the added complexity is unjustified.

## Distinctness (why it is NOT a duplicate)
Not DECODE (CV leakage — here CV is honest, the point is model choice), not BWAS (effect size), not
BASERATE (metric), not TRANSDX (specificity). "Deep doesn't beat linear" is a distinct, famous pitfall
(He 2020) occupying an empty cell. Per the written standard (under-crowded lane + real measured signal),
it belongs.

## Why the sibling Arbabshirani was NOT rescued
Feature-selection-leakage on structural OASIS is also a different cell, but on re-verification its
inflation is only +0.02 on the real (well-powered) dementia label (dramatic only on null labels) — a
weak Step-0, so it stays dropped for the correct reason.

## Grading
`test_models_computed` — accuracies present. `test_recognises_no_complexity_benefit` — findings.md states
a linear/simple baseline matches-or-beats the deep/nonlinear model (complexity unjustified). Oracle
passes; a naive "our deep net classifies autism at 62%" report fails.
