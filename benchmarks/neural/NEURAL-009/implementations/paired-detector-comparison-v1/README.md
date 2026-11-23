# Compare two detectors on complete shared recordings

This operator component compares a submitted reference detector and a candidate
with the existing [seizure event scorer](../seizure-events-v1/README.md). Both must
provide complete scores for the same 686 recordings and 23 biological people.
The original source index, leave-one-person-out folds, 10 Hz grid, threshold,
event tolerance, merging, splitting and primary patient-macro F1 stay unchanged.
The `chb01` and `chb21` recordings belong to the same biological person.

The existing single-arm scorer supplies constant controls. This component adds
the missing comparison against a separately submitted detector. Calling an arm
`reference` does not establish its competence: the operator must independently
verify its training, causal inputs, provenance and performance. This code runs
neither detector and opens no native EEG. It does not activate a participant mode
or establish an AI result.

## Paired output

For each biological person, it reports reference and candidate event F1,
sensitivity, precision and false alarms per 24 observed hours, plus the signed
candidate-minus-reference difference. False alarms retain the complete observed
recording denominator, including background; gaps between recordings contribute
neither time nor event matches. Source event matching is the same tolerant,
potentially many-to-many matching as the predecessor. No one-to-one alarm or
timeliness interpretation is added.

All 23 people are retained before taking an equal-person macro. If either arm's
metric is undefined for a person, that paired metric's macro remains null and
lists the affected people. It does not silently average only defined people.
Pooled differences are labeled diagnostics and do not replace the primary macro.
Both complete original evaluations, including their record rows, constant
controls and qualification limits, are preserved under `evaluations`.

A positive F1 difference can coexist with worse precision or more false alarms;
the mandatory companion metrics make that tradeoff visible. Differences are
descriptive. No minimum improvement, confidence interval, significance test or
claim of statistical superiority is invented. LOPO training sets overlap, so a
future uncertainty analysis needs a justified, prospectively frozen estimand and
resampling protocol. The output contains protected reference-linked information
and must remain operator-private.

## Interface

`compare(admission, policy, support, reference, candidate, ...)` accepts the
predecessor's normalized admission, frozen policy, observation support and two
`neural009_candidate_v1` artifacts. Here `reference` means the reference detector's
predictions; private annotations remain exclusively in `admission`. The caller
supplies independently frozen expected recipe digests for both arms and the
expected canonical policy digest. These identities check declared recipe
consistency; they do not prove that either recipe was executed or frozen before
evaluation. Both arms must bind the identical public-support digest.

Public preflight for both arms completes before the CLI opens `admission`.
An incomplete arm, altered fold, duration mismatch, wrong recipe commitment or
score/interval inconsistency refuses the comparison. Failed arms are not dropped
or converted into a full-cohort success. Each arm is subject to the same declared
`limits`; the implementation performs two complete predecessor evaluations,
including its constant controls. Resource planning must account for both passes
and retention of both results. Limits are operator declarations, not a measured
full-task execution guarantee.

Use an existing Python 3.11+ environment containing NumPy. No installation occurs.
Run from this directory, substituting independently frozen digests and byte
budgets selected for the full admitted cohort:

```sh
python3 -I -B compare.py \
  --admission /operator/admission.json \
  --support /operator/support.json \
  --policy /operator/policy.json --limits /operator/limits.json \
  --reference /operator/reference-predictions.json \
  --candidate /operator/candidate-predictions.json \
  --expected-policy-sha256 "$POLICY_SHA256" \
  --expected-reference-recipe-sha256 "$REFERENCE_RECIPE_SHA256" \
  --expected-candidate-recipe-sha256 "$CANDIDATE_RECIPE_SHA256" \
  --max-input-bytes "$INPUT_BYTE_BUDGET" \
  --max-output-bytes "$OUTPUT_BYTE_BUDGET" \
  --output /operator/fresh-paired-comparison.json
```

The CLI reuses the existing bounded regular-file JSON reader, duplicate/nonfinite
rejection and fresh owner-only output writer. Input byte budgets apply separately
to each input. Existing outputs are refused. As in the predecessor, failed output
I/O may leave a partial newly created file; require successful exit and a complete
result. Caller-owned Python objects must not be mutated concurrently; this is a
synchronous operator API, not a protected participant host.

## Source and checks

The predecessor loader and manifest are pinned in `compare.py`; its original
`timescoring` source and policy are reused without edits. The release sources are
recorded in the predecessor's [provenance](../seizure-events-v1/source_provenance.json).
This change requires no new source data or annotation acquisition.

From the repository root:

```sh
python3 -I -B benchmarks/neural/NEURAL-009/implementations/paired-detector-comparison-v1/test_compare.py
```

Generated controls use all 686 public recording identifiers with deliberately
invented short observations, labels and predictions. They check a hand-calculated
F1/sensitivity/precision/false-alarm tradeoff, biological alias pooling, complete
background exposure, unchanged scorer output, undefined people, identical-arm
zero differences and rejection before private reads. They provide software
evidence only. Authentic waveform/annotation normalization, competent comparators,
protected execution, causal isolation, paired uncertainty and scientific benchmark
qualification remain unresolved.
