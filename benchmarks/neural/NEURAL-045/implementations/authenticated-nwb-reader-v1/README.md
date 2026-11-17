# Authenticated reward-spacing NWB reader

This component supplies the file reader missing from the shared reward-spacing
`native_export.export_corpus(manifest, reader)` interface. It reads actual NWB HDF5
fields into that existing interface, including both appetitive `eventLog` and
aversive `photometry_event_times` layouts. It preserves the stored fluorescence
samples and exact timestamps; it never interpolates, normalizes, applies the NWB
data conversion/offset attributes, fits a reference, or constructs a substitute
target.

Each file is authenticated against its asset ID, byte count and SHA-256 before
HDF5 parsing. Reads use that same file descriptor and check its stability after
parsing. Required datasets must be bounded and local, with hard HDF5 links and
no external/virtual storage. The reader checks source subject identity, vector
shape, ordered finite clocks, finite fluorescence, exact unit annotations and
the source-row event ledger. Required cue, outcome and lick events cannot be
silently removed. Aversive cue and shock events receive the same protection.
Session-end and cue-offset rows remain accounted for as explicit exclusions.

The operator supplies the asset paths, independently reviewed biological and
trial joins, physical-unit evidence, condition support and eligibility protocol.
The reader does not establish those scientific facts. In particular, matching a
source subject string does not resolve biological aliases. An absent NWB unit
annotation is represented as `null`; it is not guessed to mean seconds or dF/F.
The mandatory unit-evidence commitment must document its physical meaning.

Use `export_authenticated_corpus(manifest, items, export_corpus)`, passing the
unchanged shared `native_export.export_corpus` function as its third argument.
The wrapper binds every reader item to the complete exporter manifest before
opening files, requiring matching condition, source subject and digest, unit
verification and identity-preserving scales. This prevents code 7 from changing
from a distractor under `60s-CSminus` into delivered milk under `600s-bgdmilk`.
Omitted, extra or duplicate assets fail preflight. The low-level reader callable
is internal and is not a supported standalone export route. Each item contains:

- `asset_id`, `path` (explicit absolute external path), `bytes`, `sha256`, and
  `expected_source_subject_id`;
- `condition`, `event_layout` (`appetitive` or `aversive`), `max_samples` and
  `max_events` (declared allocation bounds);
- `units_verified: true`, `unit_evidence_sha256`, and `expected_units` with exact
  `fluorescence`, `photometry_time`, and `event_time` annotations;
- `event_join_evidence_sha256`, `event_rows` containing zero-based `source_row`,
  reviewed `id` and `trial_id`, and `excluded_event_rows` containing `source_row`
  and `reason`. The two lists must partition the entire original event table.

Call the existing exporter with the same asset IDs/digests. Preserve the released
sample target by using `fluorescence_scale: 1`, `timestamp_scale: 1` and
`clock_offset: 0` for the source-native seconds convention; any different clock
interpretation needs a separately reviewed scientific protocol. The wrapper
attaches its file-authentication receipts to the returned corpus's
`source_receipts` ledger alongside the existing exporter receipts. They record
source row lineage and exclusions without signal values or local source paths.
Keep both outputs in operator custody. This is not a participant-facing loader.

`test_nwb_reader.py` creates small invented HDF5 files, verifies positive and
negative reader behavior, and passes a generated source through the real shared
exporter and NEURAL-045 retrospective trajectory preparation. It checks the exact
37-point native window, stored values and omission semantics. The tests require
an existing environment containing h5py and NumPy. Run them through the project's
reviewed lightweight test pool; no environment installation is needed.

Initial validation on 2026-11-17 passed 12 generated tests with NumPy 2.2.6 and
h5py 3.13.0. Independent review then identified the cross-condition event
reinterpretation boundary, repaired by the manifest wrapper and two additional
controls. These are software controls, including one real exporter/preparation
integration; they are not authentic-source preparation or biological validation.

The scientific scope remains unchanged: complete condition folds, grouped
biological aliases, native-time equal-animal scoring and the current R0
denominator. This reader does not populate the full original-condition panel,
validate the source trial joins, resolve anatomy, qualify all nine references,
or enable the shared controller's authentic execution route. Direct observation
and typed-viewer delivery remain undelivered; tool-assisted and frozen-program
modes retain their existing source-only qualification limits. No authentic NWB
payload, model trial, new prediction result or benchmark-readiness claim was
produced by this implementation.
