# Figure 6d numerical components

This package computes the original paper's image-classification accuracy from
image-level predictions and retains the complete supplied ablation curve. It
also implements the exact like-to-like eligibility predicate from the paper.
It is **not an admitted evaluation route**: the original image memberships,
complete ablation conditions, strength-matching algorithm, original weights and
numerical author curve have not been recovered. No author inference, candidate
run or paper improvement is established.

Reproduction of the original curve and improvement beyond it are separate,
first-class outcomes. This component supports their numerical calculations but
qualifies neither outcome. A future reproduction comparison must retain paired
paper-plus-data and paper-plus-data-plus-author-code access conditions, scored
separately using the same original images and ablations. The functions operate
on one such access condition per call; they do not merge access conditions or
increase the registered task count.

The source is Ding et al., [Functional connectomics reveals general wiring rule
in mouse visual cortex](https://www.nature.com/articles/s41586-025-08840-3),
Figure 6d, Results paragraph 37 and Methods paragraph 144. The inspected public
PMC XML is identified in [source_recovery.json](source_recovery.json). The
historical biological association runtime remains a separate calibration task.

## What the functions do

- `like_to_like_eligible(weight, signal_correlation)` applies **signed**
  `weight > 0.01` and `signal_correlation > 0.2`. Neither an absolute weight nor
  a newly computed percentile is equivalent. It does not invent which image
  responses define correlation or which recurrent matrix entries are eligible.
- `score_curve(target_rows, expected_conditions, prediction_rows)` returns
  correct-image counts and image denominators separately for every condition.
  Image IDs align predictions with targets. Missing, extra and duplicated IDs
  or conditions fail. The operator supplies the expected condition roster;
  submissions cannot choose a favorable subset. Each count, fitted network and
  ablation realization must have both like-to-like and strength-matched random
  conditions. Fractions are in `[0, 1]`; multiply by 100 only for display.
- `paired_differences(...)` retains image-paired author-only and candidate-only
  correct counts per condition. It does not pool test images as independent
  trained networks, compute a confidence interval, collapse the curve, set a
  minimum effect or award an improvement pass.

All functions consume Python iterables; no data loading, training, inference,
network requests or dependency installation occurs on import. `target_rows`
and each set of predictions are `(image_id, integer_class)` pairs. Predictions
are `(Condition, rows)` pairs. `Condition` retains network ID, realization ID,
ablated connection count and mode. Those IDs must identify actual source runs
if scientific use is later admitted; their presence does not prove replication.

The random mode's name is **not evidence of strength matching**. Before scoring
a scientific comparison, an operator must recover and authenticate the actual
ablation intervention, source model, permitted observations and budget parity.
Count matching alone fails the paper's control requirement. Candidates may
change methods under an eventual admitted comparison contract; this component
does not force them to copy the author's architecture.

## Source recovery boundary

The paper fixes a 1,000-unit tanh RNN, 20 time steps, linear static-image input
and final-state linear readout, 10 training epochs, batch size 512, categorical
cross entropy and PyTorch Adam. It identifies MNIST and describes FashionMNIST
as a sensitivity check. The paper's approximately 10.5% eligible weights is a
reported observation, not a prescribed ablation fraction or test target.

The inspected Methods does not establish the original image file digests and
memberships, preprocessing, optimizer settings, random seeds, ablation counts
and realizations, strength-matching procedure, correlation stimulus support,
original checkpoints, per-condition author accuracy or across-run uncertainty.
This package fills none of these gaps by using default PyTorch settings, a new
MNIST split, a guessed grid, image-level pseudo-replication or biological GLMM
coefficients. See the recovery record for the exact scope of inspected sources.

The newly retrieved author tree at `bc9302a21443453b1f39819676f2388e91bd43a3`
contains 272 entries. Both advertised figure notebooks were authenticated to
their Git blob identities and their complete code/markdown cells inspected:
`like2like.ipynb` implements biological Figure 2–4 plots; `common_input.ipynb`
plots Figure 5c. Neither supplies Figure 6 RNN training or ablation code. The
publisher page links four supplements but no separate source-data link; their
table-legend PDF describes all 34 tables as biological neuron inventories,
pairwise comparisons, projection counts and GLMM trends. It identifies no RNN
accuracy table. The workbook itself, reporting summary and peer-review file
were not opened. These bounded observations do not establish global
unavailability of the missing Figure 6 artifacts.

## Software controls

`test_fig6.py` contains small generated controls for strict threshold boundaries,
signed weights, non-finite inputs, ID alignment, exact image/condition coverage,
label validity, unpooled networks and paired discordance hidden by equal marginal
accuracy. These are software checks and do not establish scientific performance.
Run through the shared lightweight pool under its operator instructions; test
execution and measured costs are recorded in the external handoff.

Canonical task, improvement contract, registered runtime, public catalogue and
historical evidence are unchanged. Integration should retain `source_unresolved`
unless the missing original experiment is independently recovered and admitted.
The canonical improvement-only wording predates the user's four-outcome
clarification; any canonical reproduction registration is an integration
proposal, not a silent reinterpretation of the historical runtime.
