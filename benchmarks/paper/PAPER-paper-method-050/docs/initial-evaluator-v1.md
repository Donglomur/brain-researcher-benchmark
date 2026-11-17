# Initial conversion and longitudinal assessment component

This package implements the pinned `spikeInfo` conversion interface and paired DANT/UnitMatch tracking diagnostics for PAPER-paper-method-050. It is a construction component. No authentic recordings, DANT run, UnitMatch run, paper reconstruction, identity ground truth, calibrated probability, or scientifically qualified benchmark is established.

The immutable task SHA256 is `fcd65edd8550ca28997a59ad5199df24179aea1c304ad4140177ba1d45b707d3`. The pyDANT revision is `96060c1dd816181f32f089aaa686801aeae821bb`. `provenance.json` maps each operation to primary source or an explicitly prospective choice; `roster.json` preserves all 13 source-reported file identities, sizes, URLs and MD5 values from version 20019489. Source byte hashes were not independently recovered: terminal raw GitHub requests failed TLS and API rate limiting, so the two source reviewers inspected rendered primary contents. No rendered-text hash is represented as a raw-source pin.

## Commands and dependencies

Python 3.11+, NumPy and h5py are required; no package installation is performed. Controls were tested with Python 3.11, NumPy 2.4.6 and h5py 3.16.0. Use an existing interpreter with these dependencies available; `python3` in the commands below denotes that selected interpreter.

From this task's implementation directory:

```sh
python3 evaluator.py convert /operator/spikeInfo_Nasha.mat /operator/converted/Nasha --dataset Nasha
python3 evaluator.py score /operator/protected_packet.json /operator/diagnostics.json
PYTHONDONTWRITEBYTECODE=1 python3 -m unittest discover -s tests -v
```

The destination must be new; conversion stages outputs before an atomic rename, and scoring uses exclusive creation. `--generated-engineering-control` permits generated MAT fixtures explicitly marked as such throughout the receipt and assessment. It never establishes authentic readiness. Standard scoring reads JSON only and never unpickles the author's object-dictionary `Output.npz`; the trusted operator must export numeric `IdxCluster` and original `IdxUnit` into assignment rows.

## Conversion

`convert_spikeinfo(source, destination, dataset, source_kind=...)` verifies production bytes and the frozen source-reported MD5 before loading. It reads MATLAB v7.3 HDF5 references from `spikeInfo`, preserves zero-based original unit positions, transposes each samples-by-channels Waveform to channels-by-samples, retains positive contiguous SessionIndex values, and emits:

- `waveform_all.npy`: units × channels × samples;
- `session_index.npy`: one integer session per unit;
- `channel_locations.npy`: channel rows of Xcoords/Ycoords;
- `channel_shanks.npy`: Kcoords;
- `spike_times/Unit{k}.npy`: original spike times, without scaling;
- optional `peth.npy`: units × bins;
- `conversion.json`: original unit/session inventory, source/contract binding and output SHA256s.

Pinned preprocessing uses the first unit's coordinate references. This bridge additionally rejects disagreement across units, invalid times, absent references, noninteger/gapped/nonpositive sessions, inconsistent waveform or PETH shapes, and nonfinite values. These stricter engineering checks preserve failures instead of silently repairing inputs. Pinned downstream settings assume milliseconds; authentic time units remain unverified. SessionIndex is ordinal, not elapsed days. Full payload schema compatibility remains a gate.

## Protected assessment packet

`evaluate(packet)` accepts an operator-frozen JSON object. The test fixture in `tests/test_evaluator.py::packet` is a complete executable small example, explicitly generated. Required fields are:

| Field | Meaning |
|---|---|
| task_id, contract_sha256 | Exact immutable contract binding |
| source_kind | `source_asset` or `generated_engineering_control` |
| units | Complete rows `{dataset, unit_id, session, shank, peth}`; source unit IDs must be contiguous from zero |
| conversion_receipts | One converter receipt per dataset, with matching original unit/session inventory |
| dataset_to_animal | Each dataset's verified biological animal identity |
| animal_grouping_provenance | Metadata source used to establish those identities |
| animal_splits | Disjoint `train`, `validation`, `test` lists of biological animal IDs; test cannot be empty |
| feature_lineage_frozen_before_matching | Must be true |
| peth_schema | For authentic mode, `press_release_poke_3x1000_bins_1ms_plus_minus_500ms` |
| methods | Exactly one candidate and one UnitMatch reference |

Each method contains `role`, `algorithm`, complete `assignments` rows `{dataset, unit_id, track_id}`, `validation_feature: "PETH"`, `validation_used_for_selection: false`, `all_matching_settings_supplied: true`, nonempty nested `settings`, `settings_provenance`, and shared `quality_filter_provenance`. The UnitMatch reference must declare `half_waveforms_verified: true`. Assignments use positive tracks and `-1` unmatched; positive singleton tracks, same-session collisions, cross-shank tracks, omissions, extras and duplicates fail closed. Track labels are local to each dataset. The operator must supply real unit/shank metadata; the converter does not guess unit shanks from waveform maxima.

Authentic mode requires all 13 datasets and all original units/sessions. Thirteen datasets are not thirteen proven independent animals: EkkoM1/EkkoDMS and PunchM1/PunchDMS must share biological animal groups. `Animals.xlsx` and native RatName metadata need independent verification. No source dataset or final sessions may be omitted merely because the original paper truncated two large datasets after UnitMatch memory failure. The prospective full-population rule requires matched source/UnitMatch unit eligibility to be resolved before native use; an arbitrary intersection of method outputs is not supported.

**Trust boundary:** the scorer validates the supplied operator packet and declarations. It does not authenticate JSON receipts against files on disk, verify how an external executable selected units, prove the declared shank/animal grouping, or prove PETH stayed protected. Conversion verifies source files and output hashes when invoked. An operator must independently audit receipt lineage, complete matching/curation/tuning settings, grouping, matched quality filters and first/second-half UnitMatch waveform availability before native qualification. Candidate software must never receive the protected packet. Public source features/results remain publicly exposed.

## Metric semantics

Pinned AutoCuration counts one shared positive track per distinct session pair. The directional fraction from session s to t is `shared_tracks(s,t) / all_units(s)`. Both directions are reported; diagonals are omitted, and sessions with no matches contribute zero. The scalar dataset summary averages all ordered distinct session pairs. Tracked observation fraction, longitudinal track count and all-session track count are separate descriptive outputs. They are not true-positive rates or probabilities. No lag-to-days conversion is made.

The paper's independent comparison excludes PETH from **every** DANT stage; author defaults include PETH in motion estimation. The scorer recursively rejects any PETH token anywhere in declared matching settings, including shared motion, feature updates, clustering, curation or tuning. This is necessary, but declarations alone cannot demonstrate executable independence.

Functional consistency is the Fisher transform `atanh(Pearson r)` for concatenated press/release/poke PETHs, 3 × 1000 one-millisecond bins. Every unordered pair within each curated positive track contributes once, including nonadjacent sessions. Constant vectors remain undefined and their count is visible. Correlations within eight float64 machine epsilons of ±1 are prospectively snapped to that endpoint and use signed-infinity JSON strings; a mean combining both signs is undefined. This explicit numerical policy makes perfectly affine vectors stable under benign scaling; centering uses pre-scaled values to avoid overflow. It is a prospective engineering policy, not an author-specified tolerance. Finite paired candidate-minus-reference differences are reported; absent/infinite values produce null, never an invented zero.

**This does not reconstruct Figure 5E–G.** The primary paper additionally selects consecutive recording days, excludes units with mean firing rate below 1 Hz or peak below 5 Hz, requires at least 100 valid matched pairs in each of three methods, and uses a median/Friedman comparison. Its unmatched-pair outlier endpoint uses a >50 micrometer Gaussian null and 20 micrometer bins. Those endpoints require actual day metadata, rate eligibility, common three-method support, the unmatched population and distance/EMD evidence. None is silently replaced by this all-pair, two-method diagnostic. They remain unimplemented and unqualified.

Aggregation is prospective: pair means within dataset, equal dataset means within biological animal, then equal animal means within the frozen split. Reports expose denominators and undefined support, including missing regional evidence. These choices are not frozen numerical targets from the canonical source. All-split diagnostics include exposed training/validation groups; only the explicitly labelled test group can describe declared animal holdout, and that still requires lineage audit. Candidate and UnitMatch yields use the same complete population; their selected matched pairs can differ, so a PETH difference remains descriptive and can reflect selection/yield tradeoffs.

## Controls and remaining gates

Independent hand derivation uses seven observations with sessions `[1,1,1,2,2,3,3]` and tracks `[1,2,-1,1,2,1,-1]`: four unordered matched pairs, five tracked observations, two tracks, directional yields 1→2 of 2/3 and 2→1 of 1. A separate orthogonal-vector derivation gives correlation 0.6 and Fisher z `log(2)`. Tests cover actual generated HDF5 dereferencing/transposition, source checksum admission, partial-write cleanup, identity/permutation behavior, leakage across settings, unmatched/constant cases, splits, shanks, and population failures.

All measurements are generated engineering controls. Native source and UnitMatch parity, full-cohort schema/rights/exposure verification, independent motion reference, actual identity labels for accuracy/calibration, independently executed references, numerical targets/tolerances, resource measurement, meaningful difficulty and submission admission remain open. The executable always reports `scientific_qualified: false`, `full_contract_complete: false`, no registered reward, and no native runs performed. Source code GPL-3.0 and data CC-BY-4.0 attribution obligations remain; no author source or dataset payload is vendored.
