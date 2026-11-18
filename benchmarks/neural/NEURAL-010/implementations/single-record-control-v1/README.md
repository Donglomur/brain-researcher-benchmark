# Proposed one-record projection compatibility control

`control.py` is an executable proposal for one bounded authentic engineering
control. **No authentic control was run while constructing this package.** An
independently approved native protocol, free native lease and 96 MiB artifact
reservation must precede a future invocation.

The control uses the already-local `chb01/chb01_03.edf` (42,399,744 bytes, SHA256
`4c4a95a9b4331aeaadadd538763eb2e735950d9aa615b85ee6246c784be8ae90`) and its historical
projected H5 (42,568,544 bytes, SHA256
`6ebeeea5ee48d1d0e691be394bde4a96a49105b7ea999b999492f6f8b0c5d10f`). These are
historical identities pending fresh validation in the future native run.

The supervisor authenticates the selected interpreter and distribution metadata,
creates a fresh private output directory, and starts one owned worker process
group. The worker captures the exact ten-member original preparation closure and
executes its unchanged `edf_adapter.project()` function once. That original
function freshly verifies the entire EDF before projection. The historical H5 is
independently hashed before comparison. Before/after file identity checks bind
both originals across hashing, projection and comparison; the sources are never
copied, edited or deleted.

The comparison covers every one of the **21,196,800 int16 samples**, in 3,600
one-second chunks, plus all channel labels in order including duplicates, source
channel indices, calibration vectors, dataset representations, required schema
attributes and complete observed geometry. It retains the new source header.
It neither samples a few windows nor applies a floating tolerance. HDF5 container
hashes may differ across library builds; it records the actual new hash and
semantic equality separately.

No annotation summary, historical `SCHEMA_CHECK.json`, private key, scorer,
detector, trained model or full-cohort receipt is read or produced. A successful
result explicitly means **one projected record out of 686**, and says that full
cohort preparation and scientific/runtime readiness remain false. This control
does not exercise a complete reference-study or detector campaign.

## Exact future command

Run only after root's separate native admission, inside the existing native
resource wrapper:

```text
/opt/homebrew/Cellar/python@3.11/3.11.6/Frameworks/Python.framework/Versions/3.11/bin/python3.11 -I -B /selected/control.py
  --original-source-root /Users/nicholas/Documents/Codex/neuro-repository-overhaul-20261116-v1/benchmarks/neural/NEURAL-010/implementations/programme-source/implementation-v1/program/preparation
  --edf /Users/nicholas/Documents/Codex/neuroscience-benchmark-planning/authoring/delivery-20261105/neural009/source_recording/chb01_03.edf
  --historical /Users/nicholas/Documents/Codex/neuroscience-benchmark-planning/authoring/delivery-20261105/neural009/inspection/continuous.h5
  --output /Users/nicholas/Documents/Codex/neuroscience-benchmark-data/neural010-single-record-compatibility-01
```

Replace `/selected/control.py` with the exact source file selected and pinned by
the reviewed protocol. The output path must not exist. The internal worker mode
is launched by the supervisor and is not a standalone authorized command.

The selected local runtime is **Darwin arm64, Python 3.11.6, NumPy 2.4.6 and h5py
3.16.0**. The executable and four distribution metadata/RECORD files have fixed
pins in the source. The worker also checks actual loaded versions/origins,
records the loaded HDF5 version and hashes the loaded NumPy core and h5py H5
extensions within a 32 MiB identity-read allowance. This does not authenticate the
complete transitive native dependency closure and does not qualify the legacy
reference environment, which requires NumPy 2.2.6 and h5py 3.14.0. No package is
installed or changed by this control.

## Bounded execution and evidence

- One worker, one-thread environment for numerical libraries, no retries.
- Supervisor deadline of 120 seconds while waiting on the worker, including a
  blocked native call; at most 10 additional seconds for owned-group cleanup.
  A separate 140-second process alarm spans supervisor metadata work, launch,
  worker wait and result publication; if that alarm interrupts a live worker,
  the same at-most-10-second cleanup applies. Thus the source-controlled
  supervisor interval is at most 150 seconds in normal interruptible operation,
  excluding interpreter startup and pathological kernel stalls.
  The alarm is deferred during bounded cleanup so it cannot skip owned-group
  termination; its remaining original deadline is restored afterward.
  The generic resource-control lease has no wall timer, so it must wrap this
  supervisor rather than replace it. A failed or interrupted attempt remains
  in its fresh output directory for inspection.
- Worker kernel CPU limits of 90 seconds soft / 95 seconds hard, and a per-file
  `RLIMIT_FSIZE` of 93,188,096 bytes, the original `2B + 8 MiB` projection ceiling.
- Combined output allowance of **96 MiB**. Worker logs retain at most 512 KiB;
  overflow terminates the owned group. Metadata files are individually capped
  at 128 KiB. The worker writes one H5, and the directory inventory is checked
  against a fixed filename allowlist. No source staging copy is made.
- **512 MiB logical selected-body read allowance**, including supervisor
  metadata/control-source reads, exact source closure, the original projection
  reservation, historical/new H5 hashes, full semantic comparison and selected
  native extension identities. Bounded worker-pipe and post-worker result reads
  are reserved before launch and included once in the worker's supervisor prefix.
  This is conservative operation accounting, not
  measured kernel/C-library physical I/O. Dynamic-loader, OS caching and HDF5
  internal reads are not separately instrumented.
- **1 GiB declared working RAM**, with actual worker peak RSS reported on the
  selected Darwin host. This is not an OS-enforced resident-memory limit. The
  independent native lease must inspect available memory and monitor the run.

The control has no networking code. It is a trusted-operator engineering tool,
not a hostile-code sandbox or a proof of OS network/filesystem isolation. Native
process qualification, independent resource admission, namespace custody and
failure reconciliation remain external requirements. The supervisor's bounded
wait does not make filesystem `fsync` or other kernel calls interruptible; a
host-level execution supervisor remains necessary for pathological host stalls.

Output consists of the initial supervision intent, bounded worker log, one new
projection, a success or failure receipt, and the supervisor's lifecycle receipt.
All output stays private and contains no full task-success claim. Inspection of
metadata and generated controls is not a substitute for the future body checks.

## Construction controls

`test_control.py` imports only standard-library code. It tests natural child
completion, the wall deadline, output overflow, exclusive log creation, read
reservation limits and source-metadata/symlink rejection with tiny generated
fixtures. It never calls the native worker, imports NumPy/h5py, opens an EDF/H5
body or invokes the original projector. Execute it only through the bounded
short-test pool with a fresh `NEURAL010_SINGLE_CONTROL_TEST_ROOT`.
