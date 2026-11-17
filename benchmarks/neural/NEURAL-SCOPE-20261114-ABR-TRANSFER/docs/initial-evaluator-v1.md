# Initial ABR transfer evaluator

This package implements the registered threshold scoring calculations, complete
prediction ledger, descriptive animal bootstrap and threshold-rule audit. It is
an original standard-library Python implementation. It does not contain author
code, weights, native recordings or acquired annotations. It is construction
source, not an executable scientifically qualified benchmark.

The canonical task remains unchanged at SHA-256
`3ac11adf902d863075f6c38ee76365321a1fe44f23fde898e7f13c6b6a3c0f86`.
The task's source and scientific holds remain open. In particular, this package
has **no authentic scoring admission mode**: a prepared native reference can be
checked for structural completeness, but its aggregate score is withheld. A
future audited native adapter and authenticated annotation policy must precede
any new admission version. Calling an input generated does not establish its
provenance; generated mode is an engineering interface, not an authenticity test.

## What runs

From the repository root, without installing dependencies:

```sh
python3 benchmarks/neural/NEURAL-SCOPE-20261114-ABR-TRANSFER/implementations/initial-evaluator-v1/abr_evaluator.py \
  --reference generated-reference.json --predictions generated-predictions.json \
  --baseline generated-baseline.json --bootstrap-replicates 2000 --seed 0
python3 -m unittest discover -s benchmarks/neural/NEURAL-SCOPE-20261114-ABR-TRANSFER/implementations/initial-evaluator-v1/tests -v
```

The CLI writes JSON to stdout. It returns 1 for an incomplete submission, 2 for a
malformed reference or malformed JSON, and 0 for a completed engineering report
or a structurally complete but blocked native-reference audit. Always inspect
`status`: exit 0 is not benchmark admission. JSON duplicate keys and NaN/Infinity
constants are rejected. No loader performs network or candidate-program access.
Means use scaled summation to avoid overflowing an otherwise representable
average. Inputs beyond the floating-point range are rejected; unrepresentable
derived differences or widths withhold the aggregate with an explicit
`numeric_range_exceeded_no_aggregate_score` status and the complete case ledger.
No physiological clipping or complete-case fallback is applied.

Import `abr_evaluator.evaluate(reference, predictions, baseline=None,
bootstrap_replicates=2000, seed=0)` for the same behavior. The module also exposes
`animal_bootstrap` and `audit_threshold_rules`; the latter accepts calibrated
levels and probabilities and is a predictor-rule diagnostic only.

## Input and protected boundary

The reference is evaluator-only and has exactly these fields:

```json
{
  "task_id": "NEURAL-SCOPE-20261114-ABR-TRANSFER",
  "contract_sha256": "3ac11adf902d863075f6c38ee76365321a1fe44f23fde898e7f13c6b6a3c0f86",
  "target_release": "zenodo:15619100",
  "evidence_kind": "generated_engineering_control",
  "animal_roster": [{"animal_id": "opaque-a", "genetic_background": "C57BL/6N"}],
  "cases": [{
    "case_id": "opaque-case",
    "animal_id": "opaque-a",
    "stimulus": {"kind": "tone", "frequency_hz": 3000},
    "annotation": {"kind": "exact", "value_db": 35}
  }]
}
```

This minimal example is generated engineering input, not a smaller scientific
population. `unverified_prepared_reference` requires a 104-animal roster with
54 `C57BL/6NTacCdh23+` and 50 `C57BL/6N` entries and at least one explicit case
per animal, then withholds all aggregate scores. The case list must come from
the future frozen native census; this software cannot authenticate it or assume
104×9 records. It does not infer source animal identities from filenames or
collapse repeated ears/sessions. Every such case belongs to its verified animal
in the evaluator roster; its scientific eligibility remains a native gate.

Click is `{"kind":"click"}` and never a 100 Hz tone. Allowed target tones are
3000, 6000, 12000, 18000, 24000, 30000, 36000 and 42000 Hz. A source adapter must
resolve source frequency 100 into the explicit click category. The adapter and
complete native-frequency accounting are not supplied here.

The only annotations are exact singleton values, left-censored intervals
`{"kind":"left_censored","upper_db":15,"semantics_evidence":"..."}` and
right-censored intervals
`{"kind":"right_censored","lower_db":95,"semantics_evidence":"..."}`.
These are explicit mathematical input types, not a claim that either censoring
kind exists in the release. Their bounds and evidence must be authenticated
before native scoring. No sentinel or maximum-level convention is inferred.
Evidence strings do not unlock native scoring.

A prediction is an object in a list:

```json
{
  "case_id": "opaque-case",
  "threshold_db": 40,
  "censoring": "none",
  "abstain": false,
  "uncertainty": {"lower_db": 30, "upper_db": 50, "coverage": 0.95}
}
```

The threshold and interval endpoints must be finite numbers; booleans are not
numbers. Declared censoring is `none`, `left` or `right`. Interval endpoints are
ordered, and nominal coverage is strictly between zero and one. All fields are
required. Unknown fields, including annotation-bearing fields, invalidate the
prediction instead of being silently ignored. A finite threshold still scores
when `abstain` is true or predicted censoring is declared. Neither flag changes
the reference target interval.

This scorer must run in an evaluator process. Passing its reference to candidate
programs would leak labels and genotype. This package does not provide a secure
execution sandbox, path isolation, packet serialization, source selection or
candidate-safe waveform adapter.

## Metrics and uncertainty

For case i, error is distance from its point prediction p to the explicitly
provided target interval [L,U]: max(L−p, 0, p−U). Exact targets have L=U. Each
animal contributes the mean of all its case errors. The primary metric averages
those animal means equally. Every missing, duplicate, malformed or nonfinite
required prediction withholds the aggregate; unknown extra cases also fail the
submission. The ledger retains every expected case and the full denominator.
There is no complete-case fallback or post hoc penalty.

Within-5-dB and within-10-dB fractions, signed error (prediction minus target),
and interval coverage use exact annotations only, average within animal then
across eligible animals, and expose both eligible case and animal denominators.
Interval widths and abstention use all cases. Censored cases receive primary
interval-distance error and separate annotation-kind strata, but no purported
exact-truth coverage or signed error. Interval coverage is also separated by
the supplied nominal confidence level; coverage alone is not proof of
calibrated uncertainty. Background and stimulus reports use the same explicit
animal weighting and do not create additional benchmark tasks.

The percentile bootstrap draws the complete number of animals with replacement,
retaining duplicate draws. All nested case/frequency/ear/session contributions
remain together. An optional baseline must supply the identical complete case
set; paired differences are computed within animal before bootstrap. Negative
candidate-minus-baseline MAE favors the candidate. The interval uses seeded
Python `random.Random`, linear empirical quantiles and the explicit requested
number of replicates (default 2000, permitted 1–100000). This is a prospective
engineering choice for the registered bootstrap instruction; it is not a
published ABRA analysis. It describes fixed fits on one held laboratory, not
independent-laboratory population uncertainty or refitting variability.

Response-presence AUROC/Brier and peak diagnostics are absent intentionally:
their equality, annotation-coverage and physical-unit gates are unresolved.
This package does not generate fake response labels from thresholds to enable
those endpoints.

## Source-rule audit and provenance

The primary task metric is a new registered transfer endpoint. Published ABRA
mixed-lab waveform metrics are context, not reference scores for it.

| Requirement | Primary evidence | Implementation |
|---|---|---|
| Equal-animal threshold distance, censoring, abstention and full denominator | Canonical task `target_and_scoring` | `validate_reference`, `validate_predictions`, `_metrics`, `evaluate` |
| Complete104 animals,54/50 strata,click encoding and target frequencies | [Zenodo15619100 metadata](https://zenodo.org/api/records/15619100) and canonical task | Explicit roster/frequency checks; native census remains unauthenticated |
| Whole-animal paired descriptive interval | Canonical task `target_and_scoring.uncertainty` | `animal_bootstrap` and paired animal contributions |
| 244 samples/10ms, stack normalization, paper consecutive-positive rule | [ABRA paper](https://www.nature.com/articles/s41598-026-38045-1), [Europe PMC XML](https://www.ebi.ac.uk/europepmc/webservices/rest/PMC13018588/fullTextXML) | Only rule audit implemented; no native resampling assumed |
| Historical descending two-negative stop and strict probability>0.5 | [Pinned ABRA.py](https://raw.githubusercontent.com/ucsdmanorlab/abranalysis/0369a215b429002c115af2ac1f0922bb190d5c1f/ABRA.py), lines760–820 | Independently written behavioral reconstruction in `audit_threshold_rules` |
| Complete support releases and rights holds | [Zenodo17584961 metadata](https://zenodo.org/api/records/17584961), canonical task `acquisition_rights_and_feasibility` | Holds retained; no support data acquired or fitting performed |

Paper XML was read on 2026-11-17:114556 bytes, SHA-256
`967601e245b46899f9051086144b29a8ad3ddd8ee0ed340ac3e80b9bf3edc60a`.
It is not vendored. The pinned author source identity remains commit
`0369a215b429002c115af2ac1f0922bb190d5c1f`, ABRA.py SHA-256
`a33c8617426a11ee9e41d3b3c3fe9b3055cef9cac38dd4483f4a2ea03466cc7d`
from the immutable task, independently read at that commit for behavior.

The historical audit sorts levels descending, initializes the threshold to the
highest level, updates it at every strict positive and stops after two
consecutive negatives. The paper-rule reconstruction finds the lowest lower
member of two adjacent positive recorded levels. A no-pair result is `None`;
this is an explicit prospective boundary policy, not an author result or
censoring label. Both paths reject duplicate levels and unequal vector lengths.
All-negative, all-positive, insufficient-level, non-monotone and exact0.5
boundaries are tested independently. The audit is not a competent waveform
baseline and does not reproduce a training pipeline.

## Remaining work before admission

Authenticate all104 target identities and complete target/support records;
resolve overlap, ears/sessions, native labels and censoring; verify physical
units, timing and full waveform transforms; close code/weight rights and target
exposure; build and audit candidate-safe adapters and source-grouped splits;
freeze the four-stack calibration and byte-identical documentation packet;
verify context and native budgets; fit competent source-only comparators and
run protected authentic controls. Generated tests establish engineering
behavior only. No authentic baseline, model call, dataset/archive transfer,
package installation or native scientific run occurred in this implementation.
