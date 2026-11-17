# Matched energy/context reference

This implements the registered laser-EEG task's missing **ten-example energy/context
ridge comparator**, plus the support/calibration median and target-person calibration
median controls. It consumes the existing complete query-packet format and emits the
existing full-assay scorer's comparator format. No preceding implementation or task
definition is changed.

This is a benchmark-authored reference implementation. Generated controls do not
establish authentic data preparation, reference competence, EEG-specific information,
participant delivery, a model result, or scientific qualification. The source paper
does not report this regression as its prediction baseline.

## Fixed fit and permitted evidence

Every call fits on exactly the packet's eight training supports and two chronological
person calibration examples. It predicts the current query only. No query rating is
accepted, no target loader is used, no additional source bank is accessible through
the API, and no fitted state persists between calls. The packet producer remains
responsible for chronological calibration, held-experiment selection and alias purging.

The features are fixed before outcomes are evaluated:

- Actual delivered energy in Joules is continuous. Missing energy uses the mean of
  observed energy among the ten labeled examples, with a separate missing indicator.
  If all ten energies are missing, the energy feature is zero for all cases: no energy
  slope is identifiable. A recorded calibration category is never substituted for it.
- Stimulated side, documented calibration category, device, reference and rating
  protocol are categorical. Each has a full one-hot vocabulary fitted only on the ten
  labeled examples, an explicit missing indicator and an explicit unseen indicator.
  Query-only categories do not expand the vocabulary. Their unseen column is constant
  zero in training, so its ridge coefficient is zero; this exposes the limitation of
  an unsupported category instead of assigning a fabricated effect.
- Each resulting feature is centered and scaled by its ten-example population
  standard deviation (`ddof=0`). Constant columns use scale one. This includes the
  indicator columns. The query never changes means, scales, imputation or vocabulary.

Let `Z` be that standardized ten-row matrix and `y` the unrounded ten recorded
intensities. The fixed objective is

```text
sum_i (y_i - intercept - Z_i @ beta)^2 + 1 * sum_j beta_j^2
```

The intercept is the ten-label mean and is unpenalized. The implementation solves
the ten-by-ten positive definite dual system with a standard-library Cholesky solver;
there is no tuning, feature selection, cross-query pooling or adaptive fallback.
Finite-arithmetic failures refuse the reference. Predicted values are deterministically
projected onto `[0,10]`, with both unbounded prediction and projection indicator in the
owner-private audit. Targets are never clipped or rounded. This projection cannot
increase absolute error against any target within the registered response domain.

The two median controls use exactly the same ten labels or the last two calibration
labels, respectively. These controls are distinct from the mean-centered ridge fit.
They preserve zero and decimal labels and do not supply uncertainty intervals.

EEG arrays, masks, channel labels, coordinates, signal grid and documentation are not
features. The consumer validates exact packet/case fields and the contextual operands,
but does not repeat neural payload validation or preprocessing. Complete byte hashes
bind it to the owner's separately admitted packet producer. A pin supplied by an
untrusted caller is not evidence of authentic input or permitted-information access.

## Executable interface

Python 3.11 standard library only. Load `reference.py` using
`importlib.util.spec_from_file_location` as with the adjacent packet/scorer modules.
Import has no filesystem/network or numerical execution side effects.

```python
result = reference.predict_packet(
    exact_complete_query_bytes,
    expected_packet_sha256=owner_packet_sha256,
    protocol_sha256=owner_protocol_sha256,
    representation_sha256=owner_representation_sha256,
)
# result["prediction"] is {"query_id": opaque_query_id, "median": value}
# result["audit"] is owner-private: fitted context statistics and scope diagnostics.
```

For complete assay output, derive the expected query-ID/body-hash map from the complete
owner packet-preparation receipt and stream every query packet:

```python
comparator, controls, receipt = reference.build_comparator(
    owner_query_packet_stream,  # yields (opaque_query_id, immutable_packet_bytes)
    packet_sha256_by_id=owner_complete_query_manifest,
    protocol_sha256=owner_protocol_sha256,
    representation_sha256=owner_representation_sha256,
    selection_receipt_sha256=owner_selection_audit_sha256,
)
# comparator is accepted by full-assay-scorer/scorer.py.
# controls contains two ordinary lep-predictions-v1 envelopes.
```

The builder refuses missing, extra, duplicate, changed or mismatched packets. It
requires nine distinct folds, at least 678 queries, and identical training-support
contents within each fold. It never writes a partially valid comparator or silently
skips a bad case. The 678 lower bound is necessary, not sufficient: the **retained
full-assay scorer** separately authenticates the supplied target ledger's complete
678-person/nine-experiment structure and requires every eligible query. The expected
packet manifest must originate from complete preparation; this reference cannot prove
its historical completeness or match unknown trial identities to biological people.

The receipt hashes the expected packet manifest and comparator bytes, records complete
query/fold counts, output projections and cases with any missing energy across all
eleven examples. Missing actual energy continues to block claims of incremental EEG
information beyond physical intensity. The receipt does not qualify competence even
when all energies are present.

The per-packet byte limit is 384 MiB, a refusal bound rather than a measured memory
guarantee. Authentic full-assay memory/time cost is unmeasured. The function does not
implement a candidate sandbox, model execution, tokenizer capacity, real EEG loading,
signal normalization or protected scoring. Complete packet iteration belongs to the
owner; target custody and candidate exposure controls remain external.

## Verification and source fidelity

The generated suite checks two independently derived ridge solutions, query-blind
preprocessing, EEG invariance, missing energy, decimal/zero ratings, median controls,
identity and answer-bearing-field refusal, complete existing producer-to-reference-to-
scorer compatibility over all 678 nominal people and 679 queries, and fail-closed batch
coverage/support consistency. The extra generated query checks a data-derived trial
denominator. No generated observation is represented as authentic EEG or a result.

The canonical `task.json` sections `competent_references`, `protected_split` and current neural
understanding contract retain scientific authority. The exact fixed feature coding
and prediction projection above fill previously unspecified reference choices; they
are explicit benchmark implementation choices, not original paper findings. The
retained primary-source audit pins the collection paper
[doi:10.1038/s41597-025-05900-1](https://www.nature.com/articles/s41597-025-05900-1)
and official technical-validation revision
[`daf9f0b83df047c506cc4714d39551b99980d537`](https://github.com/XiangyueZhao/Supplement-Data/tree/daf9f0b83df047c506cc4714d39551b99980d537).
No source paper, author code, real epochs, target values or private paths are included.

Authentic source chronology, complete native census, physical-energy joins, participant
reuse, marker corrections, representation qualification and all-channel source
preparation remain unresolved. Neural physiology/waveform references, full-training
references, protected access modes and empirical comparator competence remain separate
work. This addition creates no new task or qualified benchmark count.
