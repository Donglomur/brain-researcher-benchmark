# Complete NEDS prediction export bridge

This component fills the export seam identified in `initial-evaluator-v1`: the
author's categorical predictions use class indices, while the evaluator requires
the original behavioral values. It converts a closed, explicitly labeled export
into the unchanged evaluator's prediction receipts for **all 74 pretraining and
10 held-out sessions, both declared methods, all five encoding masks and all four
decoding endpoints**. It does not run a model or recover a historical export.

The bridge is operator-side source, with scientific qualification **unknown**.
The native capture mechanism, protected runtime, authentic arrays and original
results remain unavailable. No task, comparator selection or readiness changes.

## Source semantics

At NEDS commit `61d2ef65556dbbc2b828d542f19bd4e7134c92f3`:

- [`loader/base.py`](https://github.com/yzhang511/NEDS/blob/61d2ef65556dbbc2b828d542f19bd4e7134c92f3/src/loader/base.py)
  maps choice `-1/+1` to indices `0/1` and block `0.2/0.5/0.8` to `0/1/2`.
- [`multi_modal/mm.py`](https://github.com/yzhang511/NEDS/blob/61d2ef65556dbbc2b828d542f19bd4e7134c92f3/src/multi_modal/mm.py)
  produces hard static-class predictions using argmax. They are not calibrated
  class probabilities, and this adapter does not fabricate probabilities.
- [`eval.py`](https://github.com/yzhang511/NEDS/blob/61d2ef65556dbbc2b828d542f19bd4e7134c92f3/src/eval.py)
  names the all-behavior and individual-behavior encoding output paths.
- [`eval_utils.py`](https://github.com/yzhang511/NEDS/blob/61d2ef65556dbbc2b828d542f19bd4e7134c92f3/src/utils/eval_utils.py)
  exponentiates spike log predictions before producing the saved `pred` array.
  The input here is that expected-count representation, never an inferred log
  rate or a rate in Hz. Continuous predictions retain source values without
  normalization or rescaling.

These are source observations, not evidence that the original checkpoint or its
full evaluation was executed. The author output files do not themselves supply
the ordered trial/unit provenance required here. An independently qualified
exporter must provide it; a filename or matching length cannot establish it.

## Export and frozen operator inputs

`assemble(bundle, export, expected_methods)` consumes the existing evaluator's
complete `neds-binned-panel-v1` operator bundle. There is no subset option, even
for generated controls. `expected_methods` is an independent ordered pair chosen
by the operator, not selected by the export. A method name is not proof of an
author model. The same ABI can represent a candidate, without attributing it to
the author.

The export has exactly these fields:

| Field | Required value |
|---|---|
| `schema` | `neds-native-prediction-export/v1` |
| `source_commit` | The pinned NEDS source commit above |
| `evidence_kind` | Exactly the operator bundle's existing evidence kind |
| `methods` | The exact operator-selected ordered pair |
| `records` | One record per method/session, exactly 168 records |

Every record carries the existing receipt's `eid`, `method`, ordered `trial_ids`,
ordered `unit_ids`, `fit_trial_ids`, `validation_trial_ids`, `pretrained_eids`,
`budget_contract`, and six `packet_sha256` values. Those declarations must match
the operator bundle and paired method. No defaults silently fill missing lineage.
The additional `native_outputs` object has exactly:

- `eval_spike`, `eval_spike_choice`, `eval_spike_block`, `eval_spike_wheel`, and
  `eval_spike_whisker`: each contains only `expected_counts_per_bin`, with shape
  `[all_test_trials, 100, all_ordered_units]`, finite and nonnegative.
- `eval_behavior`: `choice_class_index` and `block_class_index`, each one JSON
  integer per ordered test trial, plus `wheel` and `whisker`, each finite
  `[all_test_trials, 100]`. Booleans, float indices, raw labels and probabilities
  cannot masquerade as class indices.

Ground-truth arrays, extra modalities, missing masks, incomplete last-batch
outputs, reordered identities, duplicate records and stale packet commitments
are rejected. Numeric strings and booleans are rejected as predictions.
Expected-count field names declare units; numerical values alone cannot verify
that a producer actually used those units. Matching IDs similarly do not prove
that hidden predictions were generated in their declared order.

The output is detached from mutable input containers, ordered by the pinned
cohort roster and operator methods, and includes content digests. `receipts` is
the unchanged evaluator ABI. `evaluate_export` passes it to the existing scorer
without fitting. All nine endpoints remain separate. Decoding-only RRR/NDT2/POYO+
comparator incidence needs its own qualified source-panel interface; this full
NEDS/candidate bridge does not invent their missing encoding predictions.

## Use and verification

Requires the existing NumPy environment. The loader verifies the predecessor
evaluator and cohort hashes before importing them; relocation is allowed through
an explicit directory, but changing their content requires a reviewed successor.

```sh
python3 native_output_bridge.py /operator/bundle.json /operator/export.json \
  /operator/bridge.json --methods source_method candidate
python3 native_output_bridge.py /operator/bundle.json /operator/export.json \
  /operator/scored.json --methods source_method candidate --score
python3 -I -B test_native_output_bridge.py -v
```

The CLI reads JSON with duplicate-key and nonfinite-literal rejection, writes a
new output exclusively, and never loads pickle, NPY, checkpoints or network
resources. Tests use generated arrays only and reach the unchanged full-cohort
scorer; they do not execute native models or estimate scientific performance.
During construction, run those tests through the project's existing two-slot
test pool. The integration handoff specifies the new component CI command; this
private package has not itself enrolled a public CI job.

The full-source split, eligibility conflict, presplit scaling, validity masks,
camera lineage, animal/probe identity, source reference outputs and joint
superiority policy remain held. In particular, enforcing all trials here does
not make the author's possible final-batch execution equivalent. Hash binding
does not establish protected execution, historical reproducibility or success
against paper results.
