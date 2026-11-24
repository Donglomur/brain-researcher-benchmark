# Complete observed text for NEURAL-092

This source component fills the task's missing observation representation and
response-collection step for its **later observed association reconstruction**.
It provides identical, bounded text pages to a restricted-observation arm and a
program-from-text arm, then emits the unchanged original scorer submission.
The original protected QUERY prediction programme and its primary deviance
endpoint are separate and unchanged. This is source preparation; no participant,
authentic packet, runtime profile, or scientific result is supplied.

`render_panel` preserves every field of the admitted public session metadata,
every original unit and trial in order, and every observed QUERY count. It
exposes no reconstructed effects, reference outputs, or scoring feedback. Unit
records retain FIT baseline and QC information needed for all15 matched area
contrasts. Trial records retain exact native condition keys, clocks and state
bins. Count records are integer-valued chunks indexed by original QUERY row and
unit; no averaging, clipping, resampling or selection occurs. JSON float spelling
round-trips the source binary64 metadata, including non-rounded FIT baselines.

Both arms receive **the same manifest and page bytes**, including the mathematical
instructions. The program arm parses these pages; it receives no extra raw NPZ,
FIT/VALIDATION count planes, reference/scorer source or answer fixtures. The
original observed reconstruction needs metadata plus QUERY counts, and the
generated controls verify unchanged reconstruction and scorer outputs after an
independent text round trip. This representation establishes equal supplied
information for these two later-observation arms, not equal compute or perceptual
effort, and not equivalence with the earlier frozen prediction programme.

## Caller API

Only an operator that has completed the existing full32 protected-prediction
freeze and scoring barrier may provide the observed arguments. This module does
not read files, issue a host capability, or turn a claimed receipt into release
authority. In the original host the relevant boundary is
`Host.release_observed_query_and_execute_original_investigation`, after
`publish_private_scores`. A future selected host composition must place delivery
at that boundary; do not use this component to obtain QUERY counts beforehand.

```python
delivery = render_panel(
    admitted_metadata,                 # all32 original session metadata objects
    observed_query_counts_as_lists,     # all QUERY rows x all original units
    authenticated_session_to_mouse,    # original32 distinct mice; caller-owned
    max_page_bytes=selected_page_cap,
    max_total_bytes=selected_total_cap,
    count_chunk_units=selected_chunk_size,
)
# Mount/show delivery.manifest and every delivery.pages entry unchanged to both
# arms. read_page(index) returns only that declared page; it performs no analysis.
submission, receipt = collect_responses(
    delivery,
    'restricted_observation',           # or 'program_from_text'
    captured_response_bytes,
    max_response_bytes=selected_response_cap,
)
```

The captured response is JSON with exactly `arm`, `observation_sha256` from the
manifest, and `sessions`. The sessions map must contain all32 original IDs.
Each session contains `running` and `pupil`; each mode contains all six `areas`
and all15 `matched` pairs, with finite signed numbers or explicit null. The
collector emits `neuropixels_state_submission_v1` / `NEURAL-092` for the original
`source/score.py`. It checks complete axes and supplied observation identity
before any scorer call, but only the original scorer determines whether each
null is supported. The receipt records transport identity, never a score.

Choose page, total and response caps prospectively. Total delivery size includes
the manifest. Oversize records or a complete panel that cannot fit fail as a
whole: no selected sessions, omitted units, shortened arrays or truncation are
returned. Pages are held in memory; logical byte bounds do not qualify physical
memory or model context capacity. The API does not authenticate caller-owned
metadata/roster or replace the existing packet/source binding checks. The caller
must preserve the returned immutable `Delivery` object as its trusted reference.

## Endpoint and remaining limits

The original six areas, all15 pair comparisons, 32 sessions/mice, complete QUERY
counts, FIT baselines, state bins, exact stimulus/other-state pairing and original
error aggregation are retained. All32 pupil dispositions remain; source absence
in six mice makes the full pupil endpoint unavailable, without promoting a
26-mouse replacement. Reconstruction remains observational and numerical, with
no causal interpretation or broad scientific-reasoning grade.

Missing work includes authentic full-panel preparation, original prediction
closure, host integration, actual participant transport/session resets, restricted
tool enforcement, compute matching, full-context feasibility and measured model
performance. Source equality cannot establish that a participant read or used
every page. No native isolation, execution qualification, new benchmark or
scientific improvement is claimed. Existing historical source and qualification
pins remain unchanged.

## Generated controls and integration

The focused test exercises all32 invented sessions with all six areas and all15
matched contrasts. It verifies exact round-trip metadata/counts, use of identical
bytes by both arms, unchanged actual original reconstruction/scoring, retained
missing-pupil unavailability, changed responses when counts change, final-axis
failures, complete response admission, bounds, tampering and numeric parsing.
No reference model is fitted and no native host issuer is called.

```sh
python -I -B benchmarks/neural/NEURAL-092/implementations/observed-text-delivery-v1/test_observed_text.py
```

Tests require the already declared NumPy dependency. For a detached staged
component, set `N092_BASE_TASK` to the read-only original task directory. Tests
write no fixtures or bytecode. The original dependency hashes are recorded in
`SOURCE_BINDINGS.json` and checked by the focused test. This package changes no
registry, workflow, runtime or historical source descriptor. Integration must
enroll the test in real component CI and register this component's source scope;
future host selection requires a complete bound successor and native capacity
review. A source registration must not upgrade current access-condition or
scientific-readiness status.
