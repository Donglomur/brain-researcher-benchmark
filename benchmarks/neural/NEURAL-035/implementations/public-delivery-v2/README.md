# NEURAL-035 complete public input loader, version 2

This loader fixes a participant delivery defect while retaining the existing
`neural035-public-v1` manifest, two-array NPZ format, and `load(folder, np)` return
value. It admits all 14 opaque sessions, 1,012 session-local cells and 28 queries
at the original times before reading a single session archive. It rejects changed
window starts, missing cells, duplicated identities and additional metadata.

The historical standalone loader checked array shape against the supplied cell
list but did not enforce the total cell count or chronological metadata. For
example, a manifest could relabel a query as starting at 150 seconds and still
load. Stronger metadata checks already existed in the frozen programme's output
contract; this repair applies that task-specific contract at the public input
boundary, where standalone participants actually obtain their arrays.

Each archive must contain exactly `calibration.npy` and `validation.npy`.
Before invoking NumPy, the loader bounds each decompressed member, parses a
bounded NPY header, verifies the exact `(4, 300, cells)` or `(1, 300, cells)`
geometry, and requires an exact float64 payload length. Declared enormous shapes,
object arrays and trailing payloads therefore cannot reach NumPy allocation.
The original content-hash and ordinary-file capture implementation is reused
from `../delivery-source/io_utils.py`; no private input is resolved or read.

```python
import numpy as np
from load_public import load

sessions = load(public_directory, np)
calibration = sessions[0]["calibration"]  # four early blocks
validation = sessions[0]["validation"]   # one early block
metadata = sessions[0]["metadata"]      # opaque public identities only
```

Keep this directory beside `delivery-source` in its current task layout. The
caller supplies its qualified NumPy module; the source programme's prescribed
environment is NumPy 2.2.6. This file does not select or qualify another runtime.
The optional test command is `python3 -B test_load_public.py` in this directory.
During the parallel construction wave it must run through the reviewed shared
test pool. The tests create generated arrays in an automatically removed
temporary directory and require no scientific data or network access.

The tests include a real predecessor witness for the changed-query-time defect,
complete generated payload readback, manifest rejection before any archive
access, and allocation/array-integrity failures. Generated software controls do
not qualify authentic delivery or demonstrate prediction accuracy. Exact
historical delivery bindings and prepared authentic inputs remain absent; none
are fabricated here. The loader cannot prove that a self-described manifest
matches the original cohort without independently authenticated delivery pins.

This is an input component for the frozen-program condition. It does not add a
direct-observation, viewer or interactive-investigation transport, change the
peak-rank scorer, or establish a model result. All historical task, programme,
grading and numerical evidence files remain unchanged.

## Source and scientific scope

The task remains within-session chronological prediction from four calibration
blocks at 0, 30, 60 and 90 seconds and one validation block at 150 seconds; queries
begin at 210 and 270 seconds. Each block has 300 samples on the processed 10 Hz
grid. Seven paired mice are the biological units. Cells are session-local; the
loader permits the same opaque cell identifier in different sessions without
claiming correspondence across contexts. No amplitude subset, query observation,
private mouse mapping, target peak or surrogate target is introduced.

The evidence is the existing benchmark participant contract and programme input
contract, pinned in [SOURCE_PROVENANCE.json](SOURCE_PROVENANCE.json). The archived
author reference is [rsenne/dCA1_Paper at
5be84b41dc3580dd4942ea72b8c50a3248538821](https://github.com/rsenne/dCA1_Paper/tree/5be84b41dc3580dd4942ea72b8c50a3248538821)
with [Zenodo record 21780255](https://zenodo.org/records/21780255). This patch uses
the inspected local task sources; it makes no fresh remote availability claim.
The fixed-window benchmark remains narrower than the source paper's
event-specific scientific analysis.
