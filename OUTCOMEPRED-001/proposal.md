# OUTCOMEPRED-001: released-cluster feedback-window method control

This task retains an original public IBL recording and a paper-derived analysis
family while limiting its claim to a deterministic, retrospective within-session
window sensitivity. It is an **easy method control**, not a calibrated hard task.

## Scientific target and provenance

[IBL 2021](https://doi.org/10.7554/eLife.63711) establishes the behavioral paradigm.
[IBL Nature2025 Fig6 and decoding Methods](https://doi.org/10.1038/s41586-025-09235-0)
establish population feedback decoding as the paper relationship, not this task's
exact cohort/model/result. Their regional quality-selected, L1/class-weighted,
balanced-accuracy, nested/repeated-CV analysis differs from our all-released-cluster,
fixed C1 L2, single balanced subset and one five-fold split.

Source: [DANDI000409/0.260309.1324](https://doi.org/10.48324/dandi.000409/0.260309.1324),
NYU-37 session21d21fc3-4201-4edc-802a-c67b61952548, asset73c3cf70-88a0-43ae-b7fd-03a0ac156222.
The original385,181,169-byte processed NWB is pinned by DANDI's published SHA256
and immutable S3 object version. It is acquired at image build, then used offline.
CC-BY-4.0 attribution is recorded; no raw-voltage or extra-session acquisition.

Structural inspection found548 trials and867 released clusters:137 Kilosort-good,
730 MUA,61 with IBL quality score1. These are not867 independently isolated neurons.
The actual Boolean reward field agrees with released reward-volume metadata, but
neither is an independent physical delivery assay. The exact executed conversion
commit is unestablished; the NWB records NeuroConv0.9.4 and matches captured
contemporaneous converter semantics. No synthetic target label is introduced.

## Public choices, not a hidden null

The full source/selection/counting/scaling/logistic/output contract is public at
`environment/method_contract.json`, frozen before feature counting and model fits.
The 150-ms pre-feedback and400-ms post-feedback windows are compared descriptively;
19 additional200-ms windows characterize timing sensitivity. All21 share selected
trials, original unit IDs and five train-only-scaling folds. The target is the
measured signed OOF decisions and derived accuracies, not a required direction.

The old proposal's claims that a pre-feedback null was a causal necessity, that
post-feedback accuracy proves licking/reward origin, and that reported oracle
success established task difficulty have been withdrawn. A later feedback timestamp
is not an online prediction trigger; random within-session accuracy and fold SD
are not cross-animal evidence or an absence test. Unequal window widths and
unknown uninterrupted unit observation are explicit limits. Protocol epochs and
first/last spikes are not substituted for unit observation intervals.

## Verification design and evidence boundary

The eight public artifacts expose every original trial's selection status, the
complete integer count tensor, all signed OOF predictions and105 fold summaries.
A fresh source-only reference route must regenerate counts, selection, folds and
the public logistic objectives from the original NWB, without importing the oracle
or trusting submitted features. A separate independent implementation is a genuine
positive control. The grader canonicalizes labeled axes/row order and recomputes
summaries; it does not grade prose keywords, near-chance bands, curve shape,
performance direction or exact optimizer/software identity.

Wrong-output controls cover source/ID/label/fold substitution, wrong counts/window
edges, missing units, signed-score changes with unchanged accuracy, altered method,
and coherent but fabricated summaries. Source-free fixtures are only engineering
tests. Exact execution status is recorded in `REPAIR_STATUS.md` and external run
receipts; legacy answers are not evidence for the repaired revision. No Sol or
other frontier run has been performed for this revision, and no difficulty claim
is inferred from oracle success.
