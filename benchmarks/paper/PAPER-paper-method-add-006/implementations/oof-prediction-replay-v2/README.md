# Original rat spike-count prediction replay

This component scores supplied author and candidate out-of-fold predictions on
the original eight-rat, eight-session, PFC/CA1 task. It adds a no-fit prediction
replay path to the preserved `initial-evaluator-v1`; it does not rerun its
geometry/participation-ratio panel. No authentic source input, author prediction,
candidate performance or paper improvement has been established here.

Paper reproduction and paper improvement are separate first-class outcomes.
The retained numerical replay can support either assessment once the source
aggregation and native reference are qualified. Reproducing the two published
regional D2 values requires its own justified tolerance; improvement requires
an additional meaningful effect and uncertainty rule. Neither outcome is
established by the generated software controls. Paper+data and
paper+data+author-code participant conditions must keep separate exposure and
score records; this operator scorer does not create those participant packets.

`replay.py` requires Python 3.11+ and NumPy. Its adjacent generated controls also
use the existing scikit-learn installation for an independent KFold/deviance
reference. It installs and downloads nothing.

```text
python replay.py reference.json author-predictions.json candidate-predictions.json private-results.json
```

The output is an **operator-only evaluation artifact**: it contains unit IDs,
session identities, fold scores, row indices and prediction/content hashes.
Keep input arrays, manifests and output outside the public repository. The
scorer opens a new output file exclusively and never overwrites an existing
evaluation. This command is not a sandbox for candidate code or an attestation
that supplied predictions were generated without assessment-label access.

All three manifests use the retained v1 source-panel manifest schema, including
source revision `9674a6cb0c39926d70746024ce17de35f87df8f9`, DANDI version
`0.240511.0307`, and exactly 64 session rows. Each row contains `animal`,
`session_index`, `epoch_id`, `path`, `bytes`, and `sha256`. Animals must be
`KL8, ER1, JS34, JS14, JS17, JS21, JS15, ZT2`, each at processed session indices
0–7. The same animal/session must have the same epoch ID in all three manifests.
Paths resolve relative to the respective manifest. Bytes are verified before
loading any NPZ with `allow_pickle=False`. These checks bind declared artifacts;
they do not authenticate their claimed native source.

Reference NPZs contain:

| Field | Meaning |
| --- | --- |
| `latents` | Original aligned seven-column v1 array: x, y, recorded speed, vx, vy, correct, trajectory type. Position is in cm, speed/velocity in cm/s. |
| `counts` | Nonnegative integer spikes per 500-ms bin; rows align to `latents`, columns to units. |
| `bin_ids` | Unique nonempty strings, one per original bin in source order. |
| `unit_ids` | Unique nonempty strings, one per original unit in source order. |
| `locations` | Source unit locations; exact `CA1` and `PFC` enter these regions. |

The scorer derives its own masks: recorded speed strictly above 4 cm/s, then
unit mean count divided by 0.5 strictly above 0.1 Hz on those rows. It retains
both regions and all their eligible units. The 19-neuron random subset used by
the geometry analysis is irrelevant to this prediction endpoint and is not
imposed. The unit IDs are required to resolve identity ambiguity that v1's
region-only processed inputs cannot resolve. Authentic native preparation must
provide them; the scorer never invents them from positional indices.

Each prediction NPZ contains `predictions`, `bin_ids`, `unit_ids`, and
`fold_ids`. Predictions are finite, strictly positive **expected spikes per
500 ms**, with the retained bins/units in exact source order. Hz rates require
conversion by multiplication by 0.5 before submission; numeric values alone
cannot prove that this conversion was performed. IDs
must exactly match the reference after masking. Both prediction arms must
declare the ten contiguous unshuffled KFold partitions over retained source
rows; the first `n % 10` folds have one more row. These fields allow detecting
changed fold assignments, omissions and permutations. They cannot prove that
the model was trained on only the complementary fold.

Per unit and test fold, the scorer computes mean Poisson deviance and
`D2 = 1 - model_deviance / null_deviance`, using **that test fold's** mean
count as the null prediction. The output preserves all ten fold scores and
paired candidate-minus-author differences. Degenerate constant-target folds
retain zero null deviance and an explicit `undefined_zero_over_zero` or
`negative_infinity` status; they are not clipped, converted into successful
scores, silently excluded or replaced by a different null. This mathematical
representation is not a claim of bitwise parity with the author's unresolved
software environment. It also exposes a limitation of v1's `poisson_d2`, which
collapses every zero-null-deviance case to NaN. The predecessor is preserved.

No population score is emitted. The exact unit/fold/session/animal aggregation,
invalid-fold handling and treatment of selected/null-replaced units must still
be recovered from author outputs and software. The implementation therefore
does not rank candidates or compare a fabricated combined PFC/CA1 score to
the paper's 0.29/0.25 values. Per-fold scores, the complete paired panel, and
explicit invalid cases make that future reconciliation inspectable.

The source anchors are the pinned
[GLM script](https://github.com/awakhloo/population_geometry_optimal_coding/blob/9674a6cb0c39926d70746024ce17de35f87df8f9/code/fit-GLMs-rat.py),
[rat utilities](https://github.com/awakhloo/population_geometry_optimal_coding/blob/9674a6cb0c39926d70746024ce17de35f87df8f9/code/rat_utils.py),
the [paper](https://www.nature.com/articles/s41593-025-02183-y), and the
[retained task contract](../../improvement.v1.json). This component initially
uses the prior independently reviewed source reconstruction; no new paper
text, data release or author result is inferred from the software controls.

Remaining qualification requirements include authentic full-panel NWB mapping
and units, original row order, full 108-basis selection and per-unit alpha
selection exposure, source runtime behavior, original population aggregation,
author calibration in both regions, frozen candidate access/training evidence,
meaningful effect and rat-level paired uncertainty. No improvement-ready state
or current-SOTA claim follows from this scorer.
