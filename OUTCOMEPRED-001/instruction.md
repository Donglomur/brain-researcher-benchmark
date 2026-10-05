# Feedback-aligned population decoding: a within-session method control

Estimate how decoding of the released rewarded/unrewarded flag changes across
specified feedback-relative spike-count windows in one IBL mouse recording.
This is a retrospective method/sensitivity case, not online prediction, a
pre-feedback absence claim, or reproduction of a published decoding score.
Preserve the measured outcome even if it contradicts an expected pre/post pattern.

## Original public substrate and paper relationship

The processed NWB is already available offline at
`/app/data/outcomepred/session.nwb`. Its source manifest is in the same directory.
Do not download anything at runtime. Use all released cluster rows, not a
quality-selected subset or a guessed number of neurons.

- DANDI `000409/0.260309.1324`, asset `73c3cf70-88a0-43ae-b7fd-03a0ac156222`;
  [versioned dataset](https://doi.org/10.48324/dandi.000409/0.260309.1324).
- Subject NYU-37, session `21d21fc3-4201-4edc-802a-c67b61952548`.
- Original processed behavior/spike-sorting derivative, not raw voltages.
  SHA-256 `f46fa114f07a00080cdc1860913df245326a17bf249d3749ee659cabd157784a`.
- CC-BY-4.0; attribute International Brain Laboratory et al. and the dataset.

[IBL 2021](https://doi.org/10.7554/eLife.63711) describes the behavioral task.
[IBL 2025 Figure 6 and decoding Methods](https://doi.org/10.1038/s41586-025-09235-0)
provide the paper-derived population-decoding context. Their regional,
quality-selected, post-feedback 200-ms analysis uses L1, class weighting,
balanced accuracy, nested regularization selection, repeated CV and nulls.
Our all-cluster single-session L2 fixed-C analysis is an adaptation, not that
finding. There is no assumed paper answer to recover.

## Public numerical contract

Read `/app/method_contract.json`: it is the complete public specification,
including all required field names, source semantics, numerical tolerances and
output schemas. The following summarizes it; no hidden estimator choice is needed.

1. Verify the source. Preserve original trial/unit IDs and their separate positional
   row indices. Require true Boolean `is_mouse_rewarded`; it is the released
   feedback-derived flag, not an independent physical water-delivery measurement.
   Keep every released cluster and every stored duplicate spike occurrence.
2. Eligible trials have finite stimulus onset and feedback, and choice exactly
   `clockwise` or `counter_clockwise`. Form ascending eligible source-row arrays
   for labels1 (rewarded) and0. With one `RandomState(0)`, draw k from label1
   **then** k from label0 without replacement, where k is the smaller count;
   perform both draws even if a whole class is selected. Sort the combined rows.
   Require k>=5 for the fixed five-fold analysis; do not add further exclusions.
3. Use a separate `StratifiedKFold(5, shuffle=True, random_state=0)` on this ordered
   sample. Reuse these exact folds for every window. Trial folds describe one
   recording; they are not independent animals.
4. Count each cluster's spikes in half-open intervals `[feedback+start,feedback+end)`:
   `headline_pre` [-200,-50) ms; `control_post` [0,400) ms; and 19 `curve_<start>`
   windows starting at -500,-450,...,+400 ms, each 200 ms wide. Curve IDs use
   seconds with three decimals, e.g. `curve_-0.500`, `curve_0.000`.
   Form endpoints independently as unrounded float64 feedback plus integer-ms/1000.
   Count occurrences, not rates; do not silently sort, deduplicate or round spikes.
5. For each of the 105 analysis/fold fits, standardize training counts only using
   population variance and the numerical-constant rule in the contract. Fit
   `sum(logaddexp(0,z)-y*z)+dot(w,w)/2`, with `z=Xscaled@w+b` and unpenalized b.
   No feature selection, weights, tuning or rank gate. C=1 L2 permits more units
   than training trials. The supplied sklearn solver is one implementation;
   any equivalent finite solution with mean-objective gradient infinity<=1e-9
   is acceptable. Preserve actual warnings and raw termination information.
6. Score>0 predicts rewarded1; score<=0 predicts0. Report ordinary fold accuracy,
   unweighted mean of five folds, separately pooled OOF accuracy, and population
   fold SD. Summaries must recompute from your submitted labels. Fold SD is not a CI.

No accuracy band, expected pre/post gap, profile-correlation threshold,
above-chance result, successful comparator or particular prose phrase is required.
Signed decisions are compared within public 1e-5 absolute +1e-6 relative tolerance;
summaries within absolute1e-6. Source times allow absolute1e-9 seconds; original
unrounded times still define counts. Integer identity/count values are exact.
Equivalent row/column ordering, consistently labeled NPZ axes, integral scientific
notation and honest alternative numerical implementations are accepted.

## Eight required outputs

Write to `${OUTPUT_DIR}` (default `/app/output`); detailed columns/nested fields
are specified under `outputs` in `/app/method_contract.json`.

| Artifact | Required evidence |
| --- | --- |
| `source_trials.csv` | Every original trial, times/choice/label, eligibility, selection reason and selected fold |
| `spike_counts.npz` | Primitive integer counts for all21 windows × selected trials × all units, with original identity axes; no pickle |
| `trial_predictions.csv` | Complete source-keyed OOF labels and signed decisions for every window/trial |
| `folds.csv` | All105 fits' train/test class supports, correct counts and accuracy |
| `decoding_vs_window.csv` | All19 fixed-width windows' mean-fold accuracy, pooled accuracy and fold SD |
| `results.json` | Source/selected counts, named headline/post summaries and all21 analysis summaries |
| `run_metadata.json` | Exact public source/method objects and byte hashes, source QC/support,105 fit diagnostics, truthful software versions |
| `findings.md` | Short interpretation of the actual results and their limits; no keyword matching |

`source_trials.csv` accounts for excluded and eligible-but-unsampled rows as well
as selected ones. Missing original times/unselected folds are empty cells.
`run_metadata.json` includes the entire parsed method contract under `method`;
its `source` is that contract's exact source object. Hash the method and source
manifest bytes, not reformatted JSON. `support_by_analysis` is a list of21 objects
with an `analysis` key and the seven named support counts. `fits` is a list of105
analysis/fold objects. Honest library versions/statuses may differ; exact source
and method identities may not. Harmless top-level descriptions are allowed.

## Interpretation and coverage limits

The released clusters are mostly MUA; no additional QC/re-sorting is requested.
The file lacks unit observation intervals and invalid-time annotations. Count
stored spikes, but explicitly mark continuous observation support as unknown;
zero counts and spike extrema do not prove uninterrupted observation. Report
window overlap with trial/stimulus/registered-choice/task-epoch times as described
in the contract, without turning those diagnostics into post hoc exclusions.

Feedback alignment uses a later observed timestamp: it is retrospective, not a
deployable prediction trigger. Pre-feedback does not generally mean pre-choice
or pre-movement. High post-feedback decoding cannot identify its sensory, motor
or reward cause; chance-like accuracy cannot establish absence. The 150/400-ms
headline/comparator widths differ, whereas the19-point curve has fixed200-ms
width. Random folds and balanced subsampling do not establish chronological,
new-session, new-mouse or natural-prevalence performance. No null/equivalence or
causal test is supplied here.

If source integrity/schema or numerical prerequisites fail, exit nonzero and
write parseable `results.json`, `run_metadata.json` and `findings.md` with
`status: failed_precondition` and a nonempty reason. Do not fabricate a complete
result, refetch, alter the cohort or overwrite an existing evidence destination.
