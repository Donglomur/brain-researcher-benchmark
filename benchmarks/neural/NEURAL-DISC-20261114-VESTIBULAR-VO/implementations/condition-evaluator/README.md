# Vestibular complete-support evaluator

This source package calculates the prospective held-repeat velocity estimand in
the [registered task](../../task.json). It compares a complete prediction artifact
with one **externally selected, training-only motion/phase prior**, and can compare
fixed-program and case-investigation artifacts on exactly the same normalized
reference. It does not fit a decoder or read the original MATLAB deposit.

The implementation is construction source. Authentic recording identities, clocks,
units, masks, split eligibility, input provenance and prior competence remain
unverified. No biological data, trained model, protected answers or original-author
code is included. The tests use generated numbers and establish software behavior
only. A valid submission is not a scientifically qualified benchmark result.

## What is calculated

For each complete held repeat, the evaluator computes MSE on its predetermined
valid core samples. It then takes the **equal-repeat mean within each recording
group**, followed by the **equal-group mean within each animal-condition cell**.
The primary report is the full animal-by-condition vector. It includes unavailable
cells and their frozen reasons, and has no cross-animal headline average.

The paired prior improvement is `prior MSE − candidate MSE`, using the same groups,
repeats and masks. Positive values mean lower prediction error than the selected
prior. The evaluator never chooses the best prior using held targets. The task's
phrase “strongest admissible prior” still requires an independently established
training-only selection protocol; supplying a claimed provenance string does not
verify that protocol.

Per-repeat secondary diagnostics include R², Pearson correlation, signed mean
error, prediction-versus-target calibration slope/intercept, and sign agreement.
Constant targets retain their MSE; undefined R²/correlation is reported as `null`
with a reason. Sample-weighted cell MSE is explicitly secondary, with its sample
weights disclosed. For example, repeat errors `[1, 9]` in one group and `[4]` in
another give primary MSE **4.5**; repeat lengths `[1, 3, 2]` give secondary pooled
MSE **6**. The tests check these independently specified results.

Single-neuron groups are reported in a separate diagnostic vector. They cannot
enter the simultaneous-pair primary. Session, recording, pair and shared-neuron
relationships remain visible; 35 pair relationships are not 35 independent animals
and are not necessarily 35 recording groups. No population confidence interval,
permutation significance or numeric scientific pass threshold is invented.

## Inputs and use

Python 3.11 or later and its standard library are sufficient. See
[SCHEMA.md](SCHEMA.md) for the normalized input contracts. The assessor must produce
and independently review the complete normalized reference before freezing its
SHA-256. Participant artifacts contain predictions and public identity/alignment
fields, never reference targets or a participant-selected mask.

From the repository root:

```sh
PKG=benchmarks/neural/NEURAL-DISC-20261114-VESTIBULAR-VO/implementations/condition-evaluator
python3 -I -S -B "$PKG/evaluate.py" \
  --reference /assessor/reference.json \
  --reference-sha256 "$REFERENCE_SHA256" \
  --submission /submissions/fixed-predictions.json \
  --max-reference-bytes "$REFERENCE_BYTE_LIMIT" \
  --max-submission-bytes "$SUBMISSION_BYTE_LIMIT"
```

The paths and environment values above are operator-supplied placeholders, not
available data or an authorized execution selection. Limits are explicit because
the authentic complete normalized payload size is not established. Exceeding a
limit refuses the input; the evaluator never truncates cases to fit a budget.
The reference hash must come from a trusted assessor record, independently of the
participant and input file. It authenticates the selected file bytes, not the
biology or provenance asserted inside them.

Add `--investigation /submissions/investigation-predictions.json` for a matched
comparison. The first artifact must claim mode `fixed_program`, the second
`case_investigation`. Both must match the same evaluation, evidence and access
condition, full case roster and native sample clocks. The comparison reports
`fixed MSE − investigation MSE` for each primary cell. Those mode labels do not
establish how the artifacts were produced or whether actual tools and information
were matched.

The CLI prints one JSON result and exits 0 for structurally valid submissions or
comparisons, otherwise 2. Any missing, extra, malformed or nonfinite prediction
refuses the entire primary result. No failed case or group is silently removed
from the denominator. Duplicate JSON keys and non-JSON numeric constants are
refused. Integer clocks are preserved without a floating-point round trip.

The full diagnostic output is **assessor-only**. A study must separately freeze
what feedback participants may receive and how often scoring may be requested;
this module is not a query-budget or protected-workspace controller. It executes
no candidate code and supplies no model/API runner.

## Generated controls

```sh
python3 -I -S -B "$PKG/test_evaluate.py" -v
```

The fixture deliberately uses generated animal/recording identities and the full
3-animal, 49-neuron, 35-pair census shape. It is not an authentic biological roster
or a sample of the dataset. Checks cover independent weighting calculations,
constant targets, scale/sign diagnostics, same-evidence mode comparison, complete
coverage, masks, exact large-integer clocks, pseudopopulation refusal, singleton
separation, nonfinite values, malformed JSON, and reference-byte authentication.

## Scientific work still required

- Reconcile the full real recording, repeat, condition and neuron/pair census,
  including unavailable cells and any additional conditions. The Figure 2D
  41-neuron subset is not a replacement for the 49-neuron task census.
- Verify authentic temporal alignment, physical units/sign, label-independent
  quality masks, train/held-repeat buffers, train-only fitting and calibration.
- Qualify a competent neural decoder and the admissible phase/stimulus prior;
  freeze prior choice before held outcomes. A replayed waveform can make a
  phase-only prior strong without demonstrating neural understanding.
- Perform the required paired-channel shift, whole-repeat reassignment and
  nuisance controls on the real complete support. Their prediction artifacts can
  use the same evaluator with explicit mode labels, but this package neither
  manufactures those controls nor verifies their neural transformation. Reassigning
  identical replayed waveforms can be powerless; no significance is inferred here.
- Independently verify authentic reference outcomes and execution parity. The
  secondary calibrated leave-one-animal-out experiment needs its own verified
  split and calibration records; the present module does not construct them.
- Review the source deposit's CC BY-NC 4.0 terms for any intended distribution or
  hosted assessment. Data and original source remain external.

These requirements retain the task's scientific holds. No additional benchmark,
paper reproduction, model result or readiness promotion follows from this source.
