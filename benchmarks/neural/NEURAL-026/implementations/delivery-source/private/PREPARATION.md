# Operator recipe — unexecuted, full raw support absent

Run commands only after selecting storage/compute for the full inputs.
The ten original imaging files total12,707,357,935 bytes; the current300MB
construction allowance does not authorize their acquisition. Source inventory
contains exact version-one filenames, IDs, byte counts, URLs and provider MD5s.
The reused `provision.py` requires explicit download opt-in and whole-source
byte budget, verifies provider metadata and full bytes/checksums, and records
new SHA256s. Its NEURAL025 labels describe its unchanged provenance, not a new
NEURAL026 empirical qualification. No acquisition runs automatically.

1. Install the pinned requirements in a separately selected environment.
   `python private/provision.py --inventory private/source_inventory.json
   --output ORIGINALS --maximum-bytes 12707357935 --download-imaging-data`
   is an explicit future acquisition command, not a completed operation.
2. For each inventory file, use `python private/prepare.py align --mat FILE
   --asset-id ID --sha256 ACTUAL_FULL_SHA256 --output FRESH_SESSION_DIR`.
   It authenticates originals, selects source-eligible windows, reads LR and
   same-clock event intervals, derives the centroid nuisance basis, selects
   ROI ordinals without outcomes, and writes an operator-only numeric session.
   Consolidate the exact ten session `.npz`/`.json` pairs into `SESSIONS`.
   Fail unsupported schema/timing/ROI budgets; never fabricate labels.
3. `python private/prepare.py design --sessions SESSIONS --output DESIGN.json`.
   This consumes only aligned metadata to match whole-trial target counts and
   select the fixed50 cases. It does not fit any model or examine query scores.
4. Stage **one** case at a time with `prepare.py stage-case --sessions SESSIONS
   --design DESIGN.json --case-id cfa17_M1_fold0 --public-output FRESH_PUBLIC
   --private-output FRESH_PRIVATE`. Candidate sees only that public directory
   plus the task/schema/method. Private target data and all other folds stay
   outside its sandbox. Never mount the operator package root.
5. A future authorized trusted method run uses `private/run_method.py --input
   FRESH_PUBLIC/input.npz --output FRESH_REFERENCE.npz`. This fits models and
   was **not run** during construction. Preserve all50 reference predictions
   and targets with exact file byte/SHA256 descriptors in a root-authenticated
   `neural026_private_binding_v1` JSON, `cases` mapping all50 IDs to
   `{target:{file,bytes,sha256},reference:{file,bytes,sha256}}`. The files are
   distinct flat safe basenames in the operator's private root. No unbound
   placeholder counts as a reference. Candidate execution/isolation and
   reference provenance must be established externally; no new controller is
   included here.
6. Future grading command: `python private/score.py --submission SUBMISSION
   --design DESIGN.json --private-root PRIVATE --binding BINDING.json
   --output NEW_GRADE.json`. Both DESIGN and BINDING are trusted operator
   inputs, not candidate claims. This command is unexecuted on real data.

Preparation is deterministic, retrospective, and may retain only complete
finite eligible windows. It records excluded IDs. Positive phase intervals,
target values, matched>=10 trials per target/area and128 ROIs must be validated
on every real session before the task is considered supported. No exact
runtime peak/duration is claimed; streaming source reads still need selected
memory for one original field, aligned session and transient arrays. The
source recipe inherits bounded2GiB file/512MiB individual-array guards; these
are rejection limits, not measured memory requirements or allocation grants.

No public raw/prepared payload or private reference is bundled. The dependency
specification is NumPy2.2.6/SciPy1.15.3/h5py3.13.0, Python3.11; wheels and a built
runtime image are not bundled. MATLAB-port parity remains unmeasured.
