# Source-supported private annotation events

`annotation_events.py` converts already authenticated original-source annotation-ledger rows into private event records. It retains every source row and raw field. It is a deterministic adapter, not an archive authenticator, native EEG reader, final cohort builder or scorer.

The completed v2 census and full saved-ledger reconciliation establish exact pairs for all 7,345 MOAAS markers: `MOAAS1` through `MOAAS5` correspond to the strings `1.0` through `5.0`. These are the published five grouped categories: category 1 combines original 0/1, and category 5 combines original 5/6. The adapter does not recover the original seven scores. Its MOAAS output never implies an SOC state.

The 1,132 explicitly annotated SOC transitions use `LOC` with `0.0` and `ROC` with `1.0` (566 each). SOC is derived only from those exact matching pairs, never from an MOAAS threshold or a forward-filled target. Source documentation establishes the clinical meaning; the complete census establishes the exact release spellings.

Unknown spellings, marker/derived-field disagreement, unexpected companion annotations and invalid clock correspondence produce null targets with explicit reasons. Malformed input envelopes or duplicate/reordered source-row identities raise an integrity error. The caller must retain partial output and report incompleteness if a stream fails. No whitespace/case normalization or invented delimiter parsing is applied.

Repeated ratings and duplicate timestamps remain separate source events. Identity is `(recording_id, source_row)`, never timestamp alone and never an inferred biological person. The adapter rechecks each raw calendar timestamp against its saved integer milliseconds. Recording 41 and 43 clock anomalies remain explicit; no timestamp is rewritten.

`BEGIN`, `END`, `PARA` and `PROP` remain ungraded source markers with their raw fields. Their broad meanings are documented, but they are not this task's prediction targets. Propofol grouping/time allocation is unresolved: 4,127 `PROP` markers correspond to 1,570 nonempty derived dose cells and 2,557 event-only rows. Aggregate dose agreement does not license inventing a per-marker dose.

All outputs are evaluator-private and carry null biological-person identity, unconstructed EEG-packet eligibility and false canonical-scoring admission. They use the adopted retrospective `native_marker_relative_30s_v1` condition without claiming a verified challenge onset. The historical 7,328/1,129 scorer counts are not replaced or activated by this component. Authentic whole-cohort adapter execution and native EEG packet production are not claimed by generated tests.

Run the generated ambiguity and identity controls with Python's standard library:

```sh
python -I -S -B -m unittest discover -s benchmarks/neural/clinical-dosei-responsiveness/implementations/source-annotation-events-v1 -p test_annotation_events.py -v
```

No external dependency, install, model API or original-data access is required for these tests. `PROVENANCE.json` binds the source evidence and exact code reviewed for this adapter.
