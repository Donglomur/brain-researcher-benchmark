# Deterministic tractography structural connectivity of a heterogeneous cohort

## Task
`/app/data/` holds a cohort of diffusion exams (`sub-01` … `sub-08`). Each subject provides a
per-voxel **FOD peak field**, a gray-matter **atlas**, a brain **mask**, and a per-subject
**seed mask**. For every subject, run the **pinned deterministic streamline tracker** below and
build the **atlas structural connectivity matrix** — the streamline count for each ROI pair —
then write it out.

The cohort is **heterogeneous**: the seed mask decides, per subject, which voxels are seeds —
some subjects are whole-brain seeded, others seed only a subset of the ROIs — so the set of
ROI pairs a subject's seeding can determine varies. **Report a count only for a pair your
seeding determines; where it does not, omit it (NaN).** Adapt per subject; one fixed recipe
will not fit them all.

Grading is **outcome-based and entrywise**: each subject's connectome is recomputed from the
peak field by a held-out reference and compared entry-by-entry. Partial cohorts and partial
matrices are scored proportionally, so produce every count you can determine and omit the rest.

## Shared tracking + output contract (`/app/data/protocol.json`)
Read it first. It pins the physics and conventions common to all subjects: the **grid** and
voxel size, the **peak-field** layout, the **atlas** and **mask** conventions, the exact
**deterministic tracker**, the **connectome** definition, and the **determinability / omit**
rule. The graded quantity is the **per-ROI-pair streamline count** under the pinned tracker and
each subject's seeding — an integer, uniquely determined by the field once the step, angle
threshold, seeding, and atlas are pinned.

## The pinned deterministic tracker
- **Grid & step.** Volumes are 3-D arrays of shape `grid_shape = (NX,NY,NZ)`; voxel
  coordinates are integer indices. Track with a fixed step of **1.0 voxel**; look the
  orientation up at the **nearest voxel** (round the current position).
- **Seeds.** Launch **one streamline per seed-mask voxel**, from the voxel centre. Set the
  initial direction to the seed voxel's **largest-amplitude peak** and track in **both**
  directions (`+d0` and `−d0`), concatenating into one streamline. A seed voxel with no peak
  launches no streamline.
- **Stepping.** At each step, among the current voxel's peaks pick the one whose orientation is
  **closest to the incoming direction** (maximal `|unit(peak)·d|`), signed so it continues
  forward (`·d ≥ 0`). **Stop** if the turn angle exceeds `angle_threshold_deg`, or the next
  voxel leaves the mask or has no peak.
- **Endpoints & atlas.** A streamline's endpoints are its first and last voxels; each endpoint's
  ROI is the atlas label at that voxel (`0` = white matter / background = not an ROI). A
  streamline connects ROIs `i` and `j` only if **both** endpoints land in gray-matter ROIs.

## Peak field (`/app/data/sub-XX/`)
- `sidecar.json` — `grid_shape`, `voxel_size_mm` (isotropic), `n_roi`, the file names, and this
  subject's `seeding` / `seed_rois`.
- `peaks.npy` — shape `(NX,NY,NZ,2,3)`: up to two FOD peaks per voxel. Each peak is a 3-vector
  whose **direction** is the fiber orientation and whose **norm** is the peak amplitude; an
  all-zero 3-vector means "no peak".
- `atlas.npy` — `(NX,NY,NZ)` integer ROI labels: `0` = not an ROI; `1..n_roi` = the ROIs.
- `mask.npy` — `(NX,NY,NZ)` brain mask (`0/1`); tracking terminates on leaving it.
- `seed_mask.npy` — `(NX,NY,NZ)` seed voxels (`0/1`) for this subject.

## Connectome & determinability
Build a **symmetric** `(n_roi, n_roi)` matrix. For each seed's streamline whose endpoints fall
in ROIs `i` and `j`, add 1 to entries `[i-1, j-1]` and `[j-1, i-1]` (0-indexed; both endpoints
in the same ROI adds to the diagonal). A pair `(i,j)` is **determined** only if at least one of
ROI `i`, ROI `j` contains a seed voxel — then report its count (`0` if unconnected). A pair
whose **both** ROIs are un-seeded is **not determined** by this subject's seeding and must be
reported as **NaN**.

## Required output (`/app/output/sub-XX/`)
Write `connectome.npy`: a float32 array of shape `(n_roi, n_roi)`. Determined pairs hold the
streamline count; un-determined pairs hold `NaN`.

## Failure handling
If a subject cannot be processed for an unexpected reason, still write valid `connectome.npy`
files for the subjects you can produce so the rest of the cohort can be graded.
