# NEURAL-091 initial evaluator component

This component implements a prospective, exposure-aware Allen Visual Coding
Neuropixels stimulus-family evaluation from a pinned local JSON export. It builds
separate allowed-input and protected-target packets, computes train-only controls,
and scores exact keyed predictions. It does **not** establish an authentic cohort,
NWB compatibility, a competent stimulus-transfer reference, scientific validation,
or submission readiness. The canonical specification remains unchanged.

The biological target is a recorded neuron's response to a held-out stimulus
family after calibration on allowed families in the same session. Neuron IDs do
not correspond across mice. No calcium input or new-mouse inference is supported.

## Source and policies

The canonical `task.json` SHA256 is
`b42c6803c1aede42efe4f65e422494247b355b2dd2799e5817ef61d759cc2445`.
Official AllenSDK tag `v2.16.2` resolves to commit
`a9b5c685396126d9748f1ccecf7c00f440569f69`. See the package's
`COMPONENT_SOURCE.json` for immutable source URLs and semantic mappings. The
source/control worker inspected those immutable source views; the independent
reviewer also checked official generated documentation, explicitly labeled
`latest`. Raw source byte hashes could not be measured because terminal raw-file
fetches failed and GitHub API requests were rate limited. These observations
must not be represented as a verified local SDK installation or exact raw-byte
comparison. No Allen code, stimulus, or recording is vendored.

Allen stimulus presentation times and spikes share a master time axis. Official
stimulus condition IDs are session-local. The SDK histogram uses both endpoints,
and spike access warns about invalid intervals without removing their spikes.
This component deliberately adopts **half-open** `[start, stop)` spike windows to
avoid counting a boundary spike twice. It subtracts the union of invalid neural
intervals from both counts and exposure. An invalid `stimulus` interval masks the
entire presentation with the SDK's closed-overlap convention, including touching
endpoints. These are separate operations. Positive overlap between presentation
rows is rejected; adjacent rows are valid.

The following choices are prospective construction policies, not published
benchmark results or an already approved cohort protocol:

- Freeze one Neuropixels session type, exact mouse/session/unit roster, all
  presentation IDs, the presentation-table digest, held-out families, guard time,
  state history, pupil maximum age, and state-control prior before seeing outcomes.
- All presentations in each held-out family go to query. Remove calibration
  presentations within the declared symmetric temporal guard, with an exclusion
  record. A condition cannot cross families or splits within a session.
- Each selected unit must retain calibration exposure and exposure in every
  held-out family. Otherwise preparation fails; it does not drop that unit or
  mouse. Zero-exposure presentations are explicitly audited. The protocol's full
  presentation roster prevents silently omitting a repeated stimulus from export.
- State covariates use only `[onset - state_history_seconds, onset)`. Running
  velocity intervals must have ended by onset. Pupil area uses the last observed
  value, held no longer than `pupil_max_age_seconds`; a missing observation breaks
  the hold. No future interpolation occurs. Means use covered time only, and
  coverage fractions are reported. Missing eye or running data retains the row.
- Quality selection is an explicitly recorded upstream policy. The implementation
  does not infer quality from response outcomes. SDK numeric defaults (amplitude
  cutoff <=0.1, presence ratio >=0.95, ISI violations <=0.5) also depend on good
  quality, valid channels and anatomical metadata. A default label alone does not
  establish those checks; complete real unit metadata must be audited before use.

## Export interface

`evaluator.py` uses Python's standard library. `prepare(bundle, protocol)` accepts
an explicitly curated JSON export. It does not read NWB, install AllenSDK, acquire
payloads, or verify that declared NWB hashes match actual recording bytes. That
native adapter/authenticity work remains held. Public data are built by an
allowlist; SDK whole-session firing rates, tuning tables, neural state summaries,
filenames, and assessment spikes never enter allowed inputs.

The bundle has `source: "Allen Visual Coding Neuropixels"` and a `sessions` list.
Each session contains:

| Field | Meaning |
|---|---|
| `session_id`, `mouse_id` | Nonempty canonical IDs encoded as strings |
| `session_type` | `brain_observatory_1.1` or `functional_connectivity`; no pooling |
| `source_file_sha256`, `source_file_bytes` | Declared actual NWB identity, matched to frozen protocol |
| `units` | Exactly the selected units: string `unit_id`, string `probe_id`, sorted finite `spike_times` in seconds |
| `presentations` | Complete frozen table: string `presentation_id`, `stimulus_name`, session-local string `stimulus_condition_id`, finite `start_time`, `stop_time`, optional `stimulus` object |
| `invalid_intervals` | `start_time`, `stop_time`, and `scope`: `stimulus`, `all_probes`, or selected probe ID |
| `running_samples` | Nonoverlapping `start_time`, `stop_time`, `velocity` intervals; null velocity explicitly missing |
| `pupil_samples` | Strictly increasing `time`, nonnegative `pupil_area` or null |

The allowed `stimulus` attributes are numeric/null `orientation`, `contrast`,
`spatial_frequency`, `temporal_frequency`, `phase`, `frame`, and `color`. Image or
movie pixels are not distributed by this component. Native table export must
normalize missing numeric stimulus fields to JSON null, map IDs to strings, map
running `end_time` to `stop_time`, and resolve SDK probe-description invalid tags
to actual selected probe IDs. `invalid_presentation` may have a null condition ID.
For native blank periods with an empty name, an explicit recorded blank/spontaneous
family label and session-local condition key must be frozen in the presentation
table; do not omit those intervals. Pupil ellipse-area mapping, blink masking,
clock alignment, blank normalization, and complete native export remain required
native-schema checks. The generated fixture is not evidence that those source
transformations have been performed.

The protocol fields are `schema_version: 1`, `contract_sha256`, `sdk_commit`,
`session_type`, nonempty unique `heldout_families`, nonnegative
`temporal_guard_seconds`, positive `state_history_seconds`, positive
`pupil_max_age_seconds`, positive `state_prior_seconds`, and a nonempty
`quality_selection_policy`. Each item in `sessions` contains `session_id`,
`mouse_id`, `source_file_sha256`, `source_file_bytes`, exact unique `unit_ids`,
exact unique `presentation_ids`, and `presentation_table_sha256`.
The latter is `digest(session["presentations"])`: SHA256 of UTF-8 JSON using sorted
object keys, compact separators, and no nonfinite numbers. Presentation list order
is part of this pin. Source recording pins are declarations until independently
checked against actual bytes. The full exported table pin protects against later
metadata loss; it cannot prove that the initial export was complete.

The public packet has `training` rows with counts and `query` rows without counts.
Both contain an exact `[session_id, unit_id, presentation_id]` key, mouse and
family identity, condition ID, start/stop time, valid exposure, allowed stimulus
attributes, and past-state summaries/coverage. The protected packet contains exact
query counts, exclusion audit and source roster; it binds the public packet's
canonical JSON digest. Predictions are a JSON list of exactly
`{"key": ["session", "unit", "presentation"], "rate_hz": 1.2}` rows. Every query
key must occur once, with no extra keys or fields. Rates must be finite,
nonnegative numeric values; booleans are rejected.

## Controls and scoring

For a session/unit, the mean-rate control is total calibration spikes divided by
total valid calibration exposure. Whole-session SDK `firing_rate` is never used.
The running/pupil control forms train-only low/high/missing categories using each
unit's observed calibration-row medians. A state cell predicts
`(cell_spikes + state_prior_seconds * mean_rate) /
(cell_exposure + state_prior_seconds)`. Unseen cells fall back to the training
mean. This is a deterministic nuisance control, not a qualified stimulus-transfer
model; calibration and prior choices require pre-outcome freezing.

For count `y`, predicted rate `r`, training-rate comparator `r0`, and valid exposure
`e`, the log-likelihood gain is `y * (log(r) - log(r0)) - e * (r - r0)`.
The Poisson log-factorial cancels. Sum gains and spikes within each mouse over all
eligible sessions, units and held-out trials, divide by that mouse's spikes times
`log(2)`, then average mice equally. Repeat this computation by stimulus family.
Neither neurons nor trials are independent animals. The 95% percentile interval
resamples complete mouse scores with replacement (1,000 draws, recorded seed);
one mouse or a nonfinite estimand gives no interval.

No epsilon is introduced. A positive target with zero calibration rate makes the
comparison undefined. A mouse with zero held-out spikes stays in the cohort and
makes the macro score undefined. Zero predicted rate with a positive target and
positive comparator yields an explicit `negative_infinity` status. JSON reports
null numeric values with those statuses; it never silently drops them or emits
nonstandard infinity. Numeric overflow fails explicitly. A mean-rate prediction
has exactly zero gain whenever the defined positive-spike estimand exists.

## Running and verification

From the package directory:

```sh
PYTHONDONTWRITEBYTECODE=1 python3 -m unittest discover -p 'test_*.py' -v
python3 evaluator.py prepare --bundle bundle.json --protocol protocol.json --public public.json --private private.json
python3 evaluator.py controls --public public.json --output controls.json
python3 evaluator.py score --public public.json --private private.json --predictions predictions.json --output score.json --bootstrap-seed 0
```

`controls.json` contains two named prediction lists; select one as
`predictions.json`. The API also exposes `prepare`, `fit_controls`, and `score`.
Private CLI output is created with permissions 0600. A real executor still needs
separate trusted preparation/scoring and participant isolation: distinct JSON
files and a digest do not sandbox an agent that can read the source bundle.

Independent controls include Decimal-derived variable-exposure and mouse-macro
oracles, half-open boundaries, overlapping invalid intervals, keyed completeness,
family/repeat and temporal guards, cohort/metadata pins, future-state and query
target invariance, missing state, zero-rate/zero-spike cases, and CLI round trips.
All checks use bounded generated engineering inputs. They establish computational
behavior, not measured neuroscience performance or authentic reproduction.

## Gates retained

Actual Neuropixels session/mouse/unit eligibility; exact recording bytes, complete
presentation and repeat population; SDK/NWB environment and header compatibility;
timing/invalid interval/eye-tracking schema; stimulus and data rights; protected
execution; a signal-derived predictive reference; genuine complete-cohort controls
and independently reproduced scoring all remain unresolved. Allen's code license
contains a commercial redistribution restriction and is not simply plain BSD;
code terms do not settle data or stimulus redistribution. No recording, stimulus,
checkpoint, or authentic scientific result was acquired or generated here.
