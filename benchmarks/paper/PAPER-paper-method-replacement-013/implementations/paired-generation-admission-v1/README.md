# Complete paired generation admission

The existing Neuroformer generation scorer admits one prediction packet and
then calls a private truth loader. A caller comparing several runs can therefore
open targets before validating later runs, and the single-run API does not bind
its returned truth to a separately frozen complete ordered window roster.

`generation_roster.assess(packets, study, truth_loader, runtime_factory)` supplies
that missing operator composition. It admits every reference and candidate run
before any target-loader or numerical-runtime callback, checks the full declared
window support and source neuron population, freezes all predictions, validates
the same private targets within each pair, and then calls the two unchanged
original metric helpers through the existing `run_metrics.grade_generation`.
No candidate-supplied truth is used. Mutation of the caller's predictions or
study after admission cannot change the frozen predictions or paired identities.

This is an additive source component for the **protected, source-amended 10 ms
condition only**. It does not activate the runtime or narrow the registered paper
task. The source inventory's original neural-ablation cell IDs identify cohort
and method labels; they do not authenticate an original ablation recipe.

## Operator inputs

The study is a JSON-compatible dictionary with exactly these keys:

- `schema`: `neuroformer_generation_roster_v1`.
- `study_identity`: a canonical relative path, positive byte extent and SHA-256
  descriptor for the externally frozen study. This component records this
  descriptor; it does not read or scientifically authenticate its contents.
- `runs`: the complete ordered selected run roster. Each row contains `run_id`,
  `case_id`, `condition`, `arm`, `role`, `seed`, `source_run` and `support`.
- `pairs`: complete one-to-one `{pair_id, source_reference, candidate}` run-ID
  mappings. No selected run can be dropped or silently reused in another pair.
- `limits`: positive aggregate `max_runs`, `max_support_rows`, `max_windows`,
  `max_prediction_events` and `max_truth_events` capacities. These are admission
  bounds, not measured memory limits or permission to run a scientific study.

`condition` must be `protected_support_source_amended_10ms`. `arm` is
`paper_data` or `paper_data_author_code`; `role` is `source_reference` or
`candidate`. A pair must retain exactly the same cell, condition, arm, seed and
full ordered train/selection/evaluation support. Different methods can have
different `source_run` descriptors. Those descriptors must point to operator
records establishing the actual methods, resources and provenance; their shape
and hash equality alone are not proof of a competent reference or any run.

The support format and context separation are the existing native composition
format: complete lists of `{id, recording, end_tick, recording_ticks}`. Source
float32 interval encoding is retained, and collisions are refused. Each run
retains one recording because the original diagnostic ABI uses Trial 0 without
a recording column. Lateral IDs must be in `0..2021`, medial IDs in `0..1904`.
The component does not infer that these are independent animals or physical
spikes; the original calcium-derived rounded-rate token interpretation remains.

Each prediction packet is `{run_id, prediction}` in the exact declared order.
`prediction` carries the original aligned `ID`, `dt`, `Trial` and `Interval`
lists or tuples. Extra legacy generator `true` and `time` fields are never read.
Empty prediction streams are permitted; an empty stream does not allow omitted
evaluation windows. Original nonnegative offset validation is retained without
inventing a Figure 6 event-to-window conversion.

`truth_loader(run)` is a trusted evaluator callback called only after the whole
prediction roster is frozen. It returns the exact ordered tuple of
`{interval, trial, ids}` windows used by the existing native metric API, including
empty windows. IDs are tuples. Independent file-to-dataset truth issuance and
actual source/run authentication remain external obligations. The component
does not turn an arbitrary callback into a scientifically independent source.

`runtime_factory()` is called after every truth packet and paired-truth equality
check. It returns the existing metric leaves `pd`, `np` and
`precision_recall_fscore_support` from an independently qualified environment.
No numerical dependency is imported by this module itself. These callbacks are
operator interfaces, not an adversarial process or filesystem boundary.

## Interpretation and historical boundary

The output retains both original branches, `compute_scores` and
`compute_scores_scikit`, separately for every run. The first visits true-present
windows and retains the source's FP==0/FN==0 shortcut. The second visits
predicted-present windows and uses weighted binary scores. Neither is selected
as the paper's Figure 6 endpoint. Empty branch dictionaries remain empty; their
paired effect fields are null, not fabricated zeros. Candidate-minus-reference
precision/recall/F1 are descriptive effects only. There is no aggregate across
recordings, seeds, arms or branches, no significance test and no SOTA claim.

The scikit comparison additionally requires **equal exact predicted-present
`(Interval, Trial)` window sets**, derived from the already frozen prediction
events. Equal counts alone do not establish equality. When the sets differ, both
original diagnostic dictionaries are retained unchanged, but all three scikit
`candidate_minus_reference` values are null. Predictions remain admitted and the
true-present branch's existing numerical behavior is unchanged. Omitting a
window can change a raw source diagnostic; that change is not reported as a
same-support scikit effect.

Each comparison adds `effective_window_support.compute_scores_scikit` with
`equal`, `source_reference_count`, `candidate_count`, and `reason` set to
`same_predicted_present_windows` or `different_predicted_present_windows`.
This metadata concerns prediction support only and contains no private target
values. Equal empty sets still have empty source dictionaries and null effects;
support equality does not make an undefined metric defined. The report remains
`neuroformer_generation_roster_report_v1`: existing keys and raw diagnostics are
preserved, with additive comparison metadata and corrected undefined deltas.
Consumers should tolerate additional report fields and existing nullable effects.

The new report always retains `paper_win: null`,
`selected_paper_figure6_metric: null`, and false scientific/source/isolation
qualification fields. Complete support means **the declared selected roster**,
not recovery of the paper's unresolved complete original experiment family.
No private target event values are returned.

Historical generation is deliberately refused. In the pinned release,
`neuroformer_inference.py` calls `generate_spikes` on `finetune_dataset` and
`decode_modality` on `test_dataset`. The existing behavior composition's
historical selection=evaluation rule must not be imposed on this different
neural support. Historical split/run/metric mapping must be resolved separately;
this component neither repairs nor reproduces that original path.

## Source and controls

The component authenticates the existing `native-behavior-truth-v1` loader,
which authenticates the complete predecessor source bundle in private module
namespaces. It recovers the exact original analysis body from the existing
code index and calls the unchanged metric producer. Source identities are in
`SOURCE.json`. No predecessor file is changed or copied into this component.

The generated controls use the actual pinned source functions with explicitly
named small DataFrame, NumPy and weighted-binary metric doubles. They establish
admission/order/support/immutability behavior and preserve the source branch
quirks; they do not establish pandas/NumPy/scikit-learn numerical parity. No
authentic observations, weights, fits or model calls were used. Controls cover
equal-count/different-window sets, difficult-window omission with unchanged raw
diagnostics, equal sets with reordered and repeated events, both/one empty
prediction streams, and the retained admission and target-access barriers.

Run the focused public tests from this component's directory through the shared
two-slot generated-test pool, with child command:

```sh
python3 -I -S -B test_generation_roster.py -v
```

For private construction checks only, `NEUROFORMER_TEST_IMPLEMENTATIONS` can
identify the read-only published task's sibling implementations. The production
code has no such environment override. Public CI enrollment is an integration
action; adding these files alone does not claim CI discovery or qualification.

Primary source links: [original interval metric helpers](https://github.com/a-antoniades/Neuroformer/blob/36ed94084628c253098d448048c980d3dea0050d/neuroformer/analysis.py),
[original inference support](https://github.com/a-antoniades/Neuroformer/blob/36ed94084628c253098d448048c980d3dea0050d/neuroformer_inference.py).
The pinned local bodies were inspected; no fresh remote acquisition is claimed.
