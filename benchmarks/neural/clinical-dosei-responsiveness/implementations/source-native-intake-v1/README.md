# DOSE-I source-native intake

This component reads actual released metadata schemas and original native EEG CSVs, preserves protected annotation candidates, and constructs complete 30-second sparse windows. **It does not make this benchmark ready or emit an admitted scorer policy.** The authenticated metadata, native representation and unresolved clinical timing differ materially from assumptions in the inherited task.

## Findings that prevent canonical admission

The fixed [Zenodo v2 record 22145442](https://zenodo.org/records/22145442) has 171 metadata IDs and the exact same 171 static-data IDs. Its authenticated metadata aggregates to **7,345 MOAAS assessments and 1,132 SOC transitions**. The inherited scorer requires 7,328 and 1,129. These new figures are metadata aggregates, not an independently recovered original-EVENT census. V2 release notes describe changed truncation and repaired recordings. A release difference is plausible, but the exact 17-assessment/3-transition discrepancy requires raw-event reconciliation. No cases are removed to meet the inherited counts.

The metadata ID header is an empty string; static data uses `ID`. Category-count blanks remain null. A match of published study IDs does not establish a biological-person crosswalk across repeated procedures. Neither this implementation nor its person-join validator infers identity from demographics.

The [technical report, A.1–A.2](https://arxiv.org/html/2607.02570v1) describes a fixed 4 ms, 250 Hz CSV table with sparse native EEG samples. Nominal EEG sampling is 125 Hz, while the reported observed rate is 124.28 Hz. No fixed even/odd-row extraction phase is established. This implementation preserves **7,500 time rows, each with two sparse channels** per 30-second window. That is not the registered dense 7,500-value condition. There is no interpolation, phase selection, resampling, forward filling, scaling or clipping.

The exact EVENT token grammar and the marker's relationship to assessment onset remain unresolved. The generic packet API accepts a caller-supplied grid cutoff, and its machine fields say `source_event_marker_verified:false` and `assessment_onset_verified:false`. A complete preceding window does not prove it excludes the clinical assessment stimulus. `project_existing_scorer` always refuses until the scientific definition and source operands are reviewed.

Root's reviewed design decision adopts **`native_marker_relative_30s_v1`**, a retrospective marker-associated observation condition for the same released five-category target. It may contain challenge or response activity; it does not claim prediction before the challenge. [SOURCE_CONDITION_AMENDMENT.json](SOURCE_CONDITION_AMENDMENT.json) records the exact source condition and pending public binding. The source-row-bound `candidate_window` requires original nonempty EVENT and MOAAS cells and returns the same complete sparse projection. It proves candidate-row presence within the supplied hash-bound file, not authentic release membership, unique-assessment identity or complete EVENT grammar. All direct/viewer/tool/program conditions must receive that same complete projection. The old pre-onset/dense condition remains preserved as historical and unavailable.

## Implemented interfaces

`source_intake.py` uses Python 3.11 standard library only.

| Interface | Delivered behavior |
| --- | --- |
| `reconcile_metadata` / `metadata` CLI | Authenticates pinned metadata/static ZIP bytes; joins the complete 171-ID sets; preserves nullable category counts; records release-count disagreement. No clinical covariates enter the report. |
| `scan_recording` / `scan` CLI | Hash-binds one original CSV; validates its native clock and channel schema; retains every nonempty EVENT/MOAAS/SOC row in an evaluator-private ledger; reports coded-row counts and complete/incomplete prior-grid support. Nonempty MOAAS rows are explicitly candidates, not a complete original assessment census. |
| `marker_window` / `packet` CLI | Produces all grid positions in `[cutoff−30,000 ms, cutoff)`, with relative timestamps, two channels and explicit observed masks. EEG/clinical values at the cutoff and future rows are not parsed into the window. |
| `candidate_window` / `candidate-packet` CLI | Privately binds a source row to nonempty original EVENT/MOAAS cells, then produces the adopted retrospective condition with explicit unverified unique-assessment identity and onset. It passes no raw annotation or label to the participant. |
| `artifact_intervals` / `artifact_window_audit` | Reads authentic artifact timestamp columns, validates contiguous two-second epochs, and records conservative overlap privately. Endpoint inclusivity and causal availability remain unverified. It does not determine eligibility. |
| `validate_person_join` | Validates a complete proposed recording-to-person map and retains repeated-recording groups. A supplied source hash is not proof of biological identity; verified status stays false. |
| `cohort_report` | Requires a report for every metadata ID and compares coded-row counts with metadata. Equal counts alone never establish original-EVENT parity. This callable combines trusted in-process scan reports, not arbitrary untrusted JSON evidence. |
| `project_existing_scorer` | Refuses canonical projection. No policy, protected targets or scientific score is emitted. |

Released MOAAS literal strings `1`–`5` are recognized without recoding. Empty ratings are missing; every other spelling is ambiguous and remains null until the original source grammar is verified. In particular, `0`, `6`, `1.0` and conflicting tokens are never guessed into a category. SOC stays separate. No label is inferred from neighboring rows or EVENT text.

Native headers accept the documented channel base names or explicit `-uV`, `-µV`, `-μV` suffixes. The report establishes microvolts for the base names. Other unit suffixes refuse rather than silently scale. Empty sample cells are missing; non-finite, malformed or out-of-hardware-range (outside ±187.5 µV) numbers refuse. In particular a 300 sentinel is never admitted as signal or silently converted. Values at the documented saturation boundary remain observed values, not an invented eligibility decision. Missing grid rows, duplicate timestamps and off-grid cutoffs refuse, while missing channel samples remain present as null values with false masks.

Participant windows contain no recording/person identifier, absolute timestamp, source hash, raw EVENT, MOAAS, SOC, dose, other clinical column, or released artifact mask. Supply a fresh opaque case ID unrelated to source identity. Artifact masks can depend on future low-variance epochs and short-segment postprocessing; they remain private and unresolved. The window's local observed mask only states whether that row/channel contains a source value.

## Commands

Authentic metadata reconciliation was executed against the pinned small archives; no native EEG archive was acquired or prepared for this delivery. Native commands below are interfaces, not claims of authentic runs. [ACQUISITION.md](ACQUISITION.md) records the exact original archive and staged preparation protocol; reserve storage and review that protocol before executing on the original archive.

```sh
python3 -I -S -B source_intake.py metadata \
  --metadata-zip /approved/source/metadata.zip \
  --static-zip /approved/source/static.zip \
  --output /private/fresh_metadata_report.json

python3 -I -S -B source_intake.py scan \
  --csv /approved/source/10-003.csv \
  --source-sha256 EXPECTED_MEMBER_SHA256 --recording-id 3 \
  --output /private/fresh_recording_ledger.json

python3 -I -S -B source_intake.py packet \
  --csv /approved/source/10-003.csv \
  --source-sha256 EXPECTED_MEMBER_SHA256 \
  --cutoff 'YYYY-MM-DD HH:mm:ss.fff' --case-id OPAQUE_CASE_ID \
  --output /private/fresh_window.json

python3 -I -S -B source_intake.py candidate-packet \
  --csv /approved/source/10-003.csv \
  --source-sha256 EXPECTED_MEMBER_SHA256 \
  --source-row ZERO_BASED_ORIGINAL_DATA_ROW --case-id OPAQUE_CASE_ID \
  --output /private/fresh_marker_window.json
```

Inputs must be stable regular files; symlinks and checksum disagreement refuse. Hashes bind bytes, not scientific authority. `source_release_authenticated` is true only for the exact pinned metadata/static pair. Native inputs remain unverified as release members until a separately reviewed full-archive receipt exists; file SHA alone does not upgrade that status. Data/target custody is the evaluator's responsibility: these Python callables are not a security sandbox against a process with shared filesystem access.

Administrative ceilings refuse the entire input: 1 GiB per native CSV, 4,000,000 rows, 50,000 annotation rows, 64 KiB per physical CSV line; 16 MiB per small ZIP, 512 archive entries, 2 MiB per member and 16 MiB total expansion; 16 MiB per JSON output. These are format bounds, not estimates of source sizes or resource qualification. Maximum-bound inputs have not been performance tested. A full acquisition may reveal larger members and require a separately reviewed bound revision. ZIPs are inspected without extraction; duplicate members, traversal names, symlinks and encrypted entries refuse. CSVs stream except bounded small metadata and annotation ledgers. The packet buffer is 7,500 rows. Complete file SHA checks occur before and after CSV processing; there is no protection against a hostile writer altering and restoring bytes concurrently.

Outputs require fresh paths and are created mode 0600; use a private output directory. Normal write errors remove incomplete files, though interruption by process kill can leave a partial file. A successfully serialized report still explicitly has canonical admission held.

## Validation and remaining work

`test_source_intake.py` supplies generated controls for the full 171-record metadata scope, exact sparse-window boundaries, clinical/future-payload noninterference, nullable labels, private artifact overlap, group completeness, malformed clocks, source hashes, unsafe archive paths and fresh private outputs. Generated signals and identities are invented software fixtures, not physiological validation. Independent review probes and authentic metadata receipts live in the parent evidence record; see `PROVENANCE.json` for source pins and review scope.

Outstanding work is substantive: authenticate the complete raw archive and its members, reconcile all original EVENT assessments and transitions, resolve nullable/ambiguous annotation spellings, establish biological-person grouping, bind the adopted sparse source condition to the public definition, freeze eligibility without future leakage, and then build protected scorer operands and participant transports. Assessment onset remains unknown and does not become a prerequisite falsely inferred for the adopted retrospective condition; it would be necessary to revive the historical pre-challenge claim. The existing ordinal scorer, secondary metrics and training prior are unchanged. There is no model run, trained comparator, clinical diagnosis claim, new benchmark count or qualified result in this component.
