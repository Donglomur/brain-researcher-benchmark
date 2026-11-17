# Stroop55 paired participant inference

This evaluator component fills the paired-comparison and conditional-interval
gap in the existing Stroop task. It preserves all 55 people, three conditions,
the five participant folds, globally withheld session 3, and every declared
eligible case. It does not acquire or prepare authentic recordings, run a
candidate, fit a reference, or establish scientific qualification.

Native interpretation and creating or using tools, models and pipelines remain
separate first-class outcomes. This component reports their condition-specific
submitted predictions on the same cases without collapsing the access modes.
Comparability of training information and representations requires its own audit.

`paired_stroop.compare` calls the unchanged, SHA-256-pinned
[`stroop.evaluate`](../stroop55-evaluator/stroop.py) for each method against one
private manifest. All original coverage, class-support, fold, probability and
argmax checks apply independently to both complete submissions. Predictions
are joined by opaque case identity; participant metrics are joined by opaque
participant identity. Row ordering never defines a pair. No intersection-only
or available-case fallback is allowed.

The primary endpoint remains mean participant three-class balanced accuracy.
The secondary endpoints remain participant-mean Brier sum over three classes
(range 0–2) and participant-mean log loss with a true-class floor of `1e-15`.
Each person's contribution and each fold's mean are reported for both methods
and their paired difference. Every difference is **candidate minus comparator**:
positive accuracy differences and negative error differences favor the candidate.
The supplied comparator is not automatically a competent baseline.

The bootstrap samples 55 whole participants with replacement per draw. It uses
the same participant draw for both methods and all metrics, including directly
resampled per-person differences. It never resamples blocks, channels or folds
as independent participants. It emits 2.5th/97.5th percentiles with linear
interpolation at `(resamples - 1) * quantile` (type 7). The default is 10,000
resamples; the accepted range is 1,000–20,000. A required hexadecimal seed drives
the documented SHA-256 counter/rejection stream, avoiding dependence on a
library-specific pseudorandom implementation. The sorted opaque participant
order and full algorithm are fixed in source.

These intervals are **descriptive and conditional on fixed predictions, this
cohort, folds and the observed third-session schedule**. They exclude training,
refitting, model selection, prompt selection and unseen-schedule uncertainty.
Overlapping training folds do not become independent replications. There is no
superiority threshold, multiplicity-adjusted decision, p-value, causal tool-use
effect or cortical-specificity claim. The three reported metrics remain one
primary endpoint plus secondary descriptions. The published within-person
binary result is still not a reference score for this three-class joint holdout.

## Evaluator interface

From a trusted checkout, using owner-only inputs:

```sh
python3 -I -S -B paired_stroop.py \
  --manifest PRIVATE_MANIFEST.json --manifest-sha256 FROZEN_MANIFEST_SHA256 \
  --candidate FROZEN_CANDIDATE.json --candidate-sha256 CANDIDATE_SHA256 \
  --comparator FROZEN_COMPARATOR.json --comparator-sha256 COMPARATOR_SHA256 \
  --bootstrap-seed PROSPECTIVELY_CHOSEN_64_HEX_CHARACTERS --resamples 10000
```

Before evaluation, freeze the bootstrap policy/seed and comparison, the private
case census before candidate execution, and both output files before score
disclosure. SHA-256 arguments bind bytes but cannot prove this chronology.
The CLI requires external hashes for all three operands, uses the predecessor's
bounded strict JSON reader, and records their byte identities in the output.
The callable API accepts already loaded objects; custody and byte commitments
remain the caller's responsibility. The output contains evaluator-only opaque
participant identities and performance and belongs outside public source Git.
Source pinning assumes this extension itself was authenticated by its operator.

Authentic source identity and eligibility, physical units and marker timing,
canonical packet preparation, matched training information, protected fresh
state, competent references and nuisance controls remain separate unfinished
requirements. A programme score cannot establish direct or viewer interpretation.
The predecessor and canonical understanding contract remain preserved; integration
may later cite this addition without rewriting historical claims about that scorer.

## Provenance and controls

The scientific scope comes from the existing
[`understanding.v1.json`](../../understanding.v1.json) and the preserved
[`STROOP_CANDIDATE_V3.json`](../stroop55-evaluator/STROOP_CANDIDATE_V3.json),
whose primary metric and secondary paired-difference provisions explicitly
require this participant bootstrap. The fixed source family is
[Figshare 31839673 version 2](https://doi.org/10.6084/m9.figshare.31839673.v2)
and the [data paper](https://doi.org/10.1038/s41597-026-07800-4).
Previously inspected source evidence is reused; no new source acquisition or
authentic target access is needed for this arithmetic repair.

The standard-library generated controls use an invented complete 55-person
cohort. They check exact perfect/wrong limits, equal-method zero paired spread
despite variable person accuracy, the independent binomial resampling reference,
unequal block/class counts, reordered inputs, exact case coverage on both arms,
missing people/classes, invalid folds/probabilities, percentile interpolation,
policy bounds and independently frozen input bytes. These are software controls,
not observed biological data, reference qualification or model performance.
