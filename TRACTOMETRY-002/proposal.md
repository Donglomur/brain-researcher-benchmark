## TRACTOMETRY-002

**Proposal Title:** Along-tract quantitative profiling of a heterogeneous fibre-bundle cohort — per-node mean FA/MD with coordinate-space and coverage forks — an execution-hard reconstruction task (recipe divergence + coupled-physics assembly + hidden robustness)

**Scientific Domain:** Life Sciences · **Field:** Neuroscience · **Subfield:** Diffusion MRI / tractometry

**Source paper:** Yeatman et al. 2012, *PLoS ONE* (Automated Fiber Quantification / AFQ tract profiles of white-matter properties, https://doi.org/10.1371/journal.pone.0049790). Dataset: a **synthetic** diffusion tractometry cohort, generated deterministically at `synth_build/generate_fixtures.py`; planted ground-truth profiles held out under `synth_build/fixture_spec.json`.

**Status: FULL runnable Harbor task.** This is a **reconstruction** task, *not* a recognition / "spot-the-confound" task — the instruction names the deliverable (produce the along-tract mean FA and mean MD profile at each reference node, per subject); the difficulty is *execution*, not an un-cued judgement. The agent implements AFQ-style along-tract profiling **from scratch** (no profiling tool bundled), over a **heterogeneous 8-subject cohort where subjects need different computations**, with a **hidden robustness** requirement, graded node-wise against a **held-out reference** on a **convention-invariant** quantity.

### Why this is hard (the four difficulty drivers)

1. **Recipe divergence** — discoverable only from each sidecar + the data: streamline vertices are stored in **world millimetres** for some subjects and in **voxel indices** for others (a world-only pipeline mislocates the voxel-space subjects entirely, sampling garbage and mis-assigning nodes); each subject's per-voxel affine (voxel size + origin) genuinely differs, so the world↔voxel transform must be threaded through both the trilinear sampling and the node assignment.
2. **Coupled-physics assembly** — affine inversion, trilinear interpolation, nearest-reference-node assignment, spatial-outlier rejection, per-node averaging and the omit rule must **all** be assembled correctly; an error in any one corrupts a different subset of the (subject × scalar) panels.
3. **Hidden robustness** — bundles are heterogeneous in **coverage**: some are intact (every node determined), others are **fragmented** (all streamlines truncate at one end, or a mid-tract gap splits the bundle) so a contiguous run of nodes has no supporting streamlines and is undeterminable and must be **omitted** (NaN), with the determinable segment differing per subject; and, never announced, a **majority** of subjects carry a few **spurious streamlines** that have strayed ~11 mm out of the bundle core into low-FA/high-MD tissue and must be recognised as not belonging and excluded before averaging, else every node mean is biased ~9–10% (well past tolerance).
4. **Convention-invariant grading** — nearest-node assignment and trilinear sampling are unique given the affine, the fragmentation gap is empty (nodes jump from 0 to ≥41 supporting streamlines, so the omit-set is threshold-independent), and the spurious streamlines sit in a wide empty gap (~3 mm core vs ~11 mm strays) so any robust physical-distance rule prunes exactly them; two independent correct implementations agree to ~1e-8 (proven below), so a correct solver can pass while wrong pipelines fail — no reporting-convention ambiguity.

### Verifier

`tests/test_outputs.py` recomputes both profiles for every subject from the bundled streamlines + volumes with a **held-out reference** pipeline (`tract_pipeline` + `tract_ref`, shipped only under `tests/` + `solution/`, never under `/app/data`) and grades **node-wise**. Reward is **fractional**: each of the **16 (subject × scalar) panels** is its own test, so the score is the fraction of panels correct. A panel passes when the **omit rule** is honoured (every undeterminable node NaN, every determinable node finite) **and** ≥90% of the determinable nodes agree within a per-scalar tolerance (FA rtol 5%/atol 0.01; MD rtol 5%/atol 0.02e-3).

**Grading-invariance proof (the key check).** A genuinely-correct independent implementation (`scipy.map_coordinates` trilinear, a Tukey-fence outlier rule instead of the reference's median-distance rule, a different omit threshold) reproduces every determinable node to ~1e-8 and the identical omit-set on all 16 panels. The plausible-but-wrong pipelines each fail only their own axis: **world-only sampling** → only the voxel-space subjects; **per-streamline arc-length resampling instead of reference-node projection, or filling instead of omitting** → only the fragmented subjects; **no outlier pruning** → only the contaminated subjects. A naive pipeline that makes every one of those mistakes fails 14 of 16 panels — so partial credit is monotone in correctness.

### Difficulty — measured on the frontier gate

Oracle **reward 1.0**, in-container (deterministic; oracle == verifier).

| agent | runs | reward | what it did |
|---|---|---|---|
| **gpt-5.6-sol (codex, xhigh)** | k=1 | 0.0 | Solved **6/16 panels**; the 10 it missed fall on the hard axes — the world-mm vs voxel-index coordinate-space fork (per-subject affine), the fragmented-coverage omit (NaN) rule, and the un-cued spurious-streamline spatial-outlier pruning. Full-suite gate reward 0. |
| **2nd frontier family (Claude/Gemini)** | pending | pending | to be run by the maintainer at gate calibration |

**Failure mode (measured for gpt-5.6-sol; hypothesis for the 2nd family):** the model implements a single world-space profiling pipeline and does not thread the per-subject coordinate-space fork, honour the fragmentation omit, nor discover-and-prune the unannounced spurious streamlines. The specific failing set is characterised from the task's hard axes (per-panel identities were not logged for this k=1 run); the 10-panel miss is the count the gate recorded and lands on the genuine hard axes, not a format bug.

### Notes / honesty

- **Reconstruction paradigm.** This task's difficulty is executional (get the per-subject coordinate space, the coverage omit, and the outlier robustness right with no recipe), unlike the recognition-tier "un-cued judgement" tasks in this repo. `instruction.md` names the deliverable but never enumerates the pitfalls (the voxel-space subjects, the fragmentation gaps, the spurious streamlines) — the agent must discover them from the data.
- **Data.** Synthetic, small, deterministic, and **leakage-clean** (the held-out reference and planted profiles are never under `/app/data`). Regenerable via `synth_build/generate_fixtures.py`.
- **allow_internet=false.** The task is self-contained (dependencies baked in the image; no network at run or verify time).
