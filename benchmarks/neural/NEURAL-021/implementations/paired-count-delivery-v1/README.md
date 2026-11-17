# NEURAL-021 exact-count visual delivery

This component adds task-specific direct and typed-viewer source for the existing
272-training / 92-query somatosensory velocity task. It supplies exact numerical
count views, all training trajectories, restricted unit/time crops, and a complete
30-by-2 answer collector. It does not fit a decoder or change the endpoint.

The existing producer, deferred grader, historical predictions and contracts are
unchanged. This is source plus generated software controls, not an authenticated
participant deployment or an authentic-data result. No dataset or target arrays
are included. The exact public input loader has not been run on authentic data in
this revision. Runtime isolation, actual displayed readability, participant
evaluation and a mode-specific protected grading handoff remain unqualified.

## Exact observations and timing

The original public feature tensor has shape `[trial,30,6,65]`. For each trial,
`X[j,h,u] = C[j+h,u]`, where `C` has 35 count bins and 65 units. The implementation
checks every repeated count before collapsing; an inconsistent history fails.
This changes storage/view layout without dropping any permitted information.
All counts appear as literal integers, including zeros. The renderer does not
normalize, saturate, smooth, interpolate, select units or summarize spikes.

Count column `k` is the half-open interval `[-220+20k,-200+20k)` milliseconds from
released movement onset, for `k=0..34`. Response bin `j` is
`[-100+20j,-80+20j)`, for `j=0..29`, with history columns `j..j+5`. Thus the last
neural bin ends at +480 ms and the last target bin ends at +500 ms. Anonymous
U01..U65 retain source unit-column order; they are not claimed to be persistent
cell identities. Every view retains absolute relative-time and unit labels.

The output remains signed velocity in the source x/y column order, in m/s.
Training labels are already converted; the renderer performs no additional
scaling. The original adapter averages 20 native 1 kHz samples after multiplying
by the recorded 0.01 conversion once. That source implementation is the basis
for these units, not a new numerical qualification. `passive` means the source
perturbation condition; the extended trajectory can contain voluntary correction.
Source onset uses future acceleration, and all batch histories are accessible.
Neither arm is an online or purely passive causal experiment.

## Operator API

Use Python 3.11 or later. The visual API and generated tests use only the standard
library. Loading the original NPZ packet additionally uses the operator's existing
NumPy dependency. This package installs nothing.

```python
import numpy as np
from delivery import load_public, Session

# Operator only: exactly the selected public directory, never its private sibling.
packet = load_public(public_root, np)
session = Session(packet, "direct_observation")  # or "typed_viewer"
svg = session.calibration(0)     # All 272 training entries are available: 0..271.
svg = session.view("q0000")     # Always show the complete query first.
# Typed viewer only: an additional exact-count unit/time view.
# svg = session.view("q0000", unit_start=0, unit_stop=20, bin_start=0, bin_stop=12)
session.answer("q0000", velocity_m_s)  # Exactly 30 finite signed x/y pairs.
# Continue for all 92 queries, in any order, without target or score feedback.
submission_bytes, receipt_bytes = session.finish()
```

`load_public` captures the original `cases.json`, `training.npz` and `queries.npz`
once each, checks their fixed original producer byte counts and SHA-256 pins, then
parses those captured bytes. It does not discover source files or traverse private
directories. NPZ members and allocation headers are bounded before NumPy loads
them with `allow_pickle=False`. Full 272/92 scope, 52 active/40 perturbation query
counts, row/condition alignment, exact metadata, valid counts and every history
overlap are required. Query packets containing a velocity field are refused.

`Packet.from_arrays` is a value-validation API for trusted preparation and
generated controls. It does not authenticate provenance. Deployment must enter
through `load_public`; a Python caller can replace code or construct objects and
is not an untrusted participant boundary.

Both arms have the same complete 272-trial calibration catalog, same 92 query
observations, source conditions and response endpoint. The direct arm admits only
the fixed complete query view. The typed viewer adds half-open unit/time cropping
after the complete view, without arbitrary computation, raw-array export, model
calls or labels. At most 2,048 total training/query views are admitted per session;
both arms share this explicit delivery budget. A caller should deliver identical
calibration access and preregister any stricter matched exposure policy before
assessment. Actual view histories are retained, so different exposure is visible.
Tool-assisted and frozen-program access retain their existing numerical packet
and lifecycle rules; this component does not relabel them as direct understanding.

Keep the session object, NumPy, packet arrays, source files and filesystem in the
operator process. Deliver only admitted SVG views and answer acknowledgments to
participants. In a real no-tools deployment the service/browser must enforce that
boundary; these Python methods do not create it. SVG contains no scripts, links,
remote resources or hidden target fields. The cumulative view cap is an API
bound, not an operating-system CPU/RSS enclosure.

## Answers and scoring handoff

Each query must be viewed before its one immutable response. Partial trajectories,
booleans, nonfinite values, duplicate answers, unknown queries and out-of-envelope
values fail. Completion requires all 92 trajectories; no favorable subset can be
exported. The unchanged original public interface validates the final submission,
which uses the original schema and exact `cases_sha256`. The source scorer's
equal-condition mean variance-weighted trajectory R², null/negative handling and
squared loss are unchanged. This component neither loads private targets nor
scores its own answers.

The receipt records arm, shared observation hash, exact submission hash, and an
ordered hash chain of rendered-view and answer hashes. It is useful lineage for a
trusted owner, not a signature, independently witnessed execution or proof of
participant isolation. The existing deferred grader admits frozen-program
producer receipts; these new visual receipts are **not** a substitute for that
admission. A separately reviewed protected handoff for these access modes is
still required before a numerical participant result can be reported.

## Verification and qualification limits

Run generated controls through the shared two-slot test pool using
`python3 -I -B /ABS/COMPONENT/test_delivery.py`. They use an invented full 272/92
packet, independently check physical-time mapping and every rendered cell, refuse
overlap corruption and wrong scope, exercise mode restrictions and budget failure,
and submit all 92 trajectories in both modes through the original validator.
They do not open authentic arrays, private historical targets or native models.

The package closes a concrete representation/response source gap. It does not
establish competent neural versus condition/time controls, direct-understanding
performance, no-tools enforcement, contamination resistance or scientific
qualification. Former query labels remain historically public. One animal/session
and 92 nested trials do not establish between-animal generalization.

`SOURCE_MANIFEST.json` records exact source derivation and file hashes.
`HANDOFF.md` records tests actually executed and remaining integration work.
