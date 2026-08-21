## GRATIO-002

**Proposal Title:** Aggregate g-ratio mapping across a heterogeneous cohort — an execution-hard reconstruction task (recipe divergence + coupled-physics assembly + hidden NaN-aware robustness)

**Scientific Domain:** Life Sciences · **Field:** Neuroscience · **Subfield:** Quantitative MRI / microstructure (g-ratio)

**Source paper:** Stikov et al. 2015, *NeuroImage* (in vivo histology of the myelin g-ratio with MRI, https://doi.org/10.1016/j.neuroimage.2015.05.023); Mohammadi & Callaghan 2021, *J. Neurosci. Methods* (g-ratio mapping); Zhang et al. 2012, *NeuroImage* (NODDI, https://doi.org/10.1016/j.neuroimage.2012.03.072). Dataset: a **synthetic** g-ratio (myelin + neurite) qMRI cohort (8 subjects), generated deterministically at `synth_build/generate_fixtures.py`; planted ground-truth maps held out under `synth_build/fixture_spec.json`.

**Status: FULL runnable Harbor task.** This is a **reconstruction** task, *not* a recognition / "spot-the-confound" task — `instruction.md` names the deliverable (per-voxel MVF, FVF, aggregate g-ratio); the difficulty is *execution*, not an un-cued judgement. The agent assembles the g-ratio **from scratch** (no reference implementation bundled), over a **heterogeneous cohort where subjects need different computations**, with a **hidden NaN-aware robustness** requirement, graded voxelwise against a **held-out reference** on **convention-invariant** volume fractions.

### Why this is hard (the four difficulty drivers)

1. **Recipe divergence** — subjects need *different code paths*, discoverable only from each sidecar: the myelin index is an MTsat-like map on some subjects (MVF = per-subject calibration × index) and an already-fractional MTV map on others (calibration 1.0); the neurite input is a two-map NODDI set (`FVF = v_ic·(1−v_iso)`) on some and a single restricted-fraction map (`FVF = fr`) on others; and — the omit fork — three subjects carry a **non-quantitative decoy** input (FA for neurite, plain T1w for myelin) declared only by the sidecar `model` field, so the affected map is **not computable** and must be **omitted**, not fabricated from the decoy. Trusting mere file presence fabricates a map on every decoy subject.
2. **Coupled-physics assembly** — `AVF = (1−MVF)·FVF`, `FVF = v_ic·(1−v_iso)`, and `g = sqrt(AVF/(AVF+MVF))` compound both inputs; the g-ratio is **undefined (NaN)** in CSF / near-void voxels where the axonal volume fraction collapses toward zero. An error in any link corrupts a different subset of the 24 (subject × map) panels.
3. **Hidden robustness (the dominant, un-announced driver)** — the myelin index is delivered as **three repeated acquisitions**, and on a **majority (6 of 8)** subjects one repeat is corrupted over disjoint tissue-voxel subsets by (a) a localised motion **spike** (additive outlier) and (b) a **failed-fit NaN** (the standard qMRI sentinel). No single repeat is clean. A solver that **averages** the repeats propagates the spike and is NaN-poisoned; a plain per-voxel `np.median` rejects the spike but is **still** NaN-poisoned (`median{a, a′, NaN} = NaN`), so its MVF and g-ratio become NaN across the failed-fit voxels. Only a **NaN-aware** robust combine (`np.nanmedian`, or drop-the-NaN-then-drop-most-deviant) recovers the true index from the two good repeats. Nothing in `instruction.md` flags the corruption.
4. **Convention-invariant grading** — no voxel is corrupted in more than one repeat and the repeat-to-repeat noise is tiny, so **any** NaN-aware single-outlier-rejecting combine reproduces every computable panel; the pinned volume-fraction arithmetic has no reporting-convention freedom (proven below).

### Verifier

`tests/test_outputs.py` recomputes every map from the bundled inputs with a **held-out reference** pipeline (`gratio_pipeline` + `gratio_ref`, shipped only under `tests/` + `solution/`, never under `/app/data`) and grades **voxelwise** over the brain mask. The reference derives the myelin index as the per-voxel `np.nanmedian` of the repeats, then applies the pinned arithmetic. Each of the 24 (subject × map) panels is its own parametrized test; the binary Harbor reward requires all to pass. A computable map passes at ≥90% agreement within a per-map tolerance (MVF/FVF rtol 5%/atol 0.01 and must be **finite** in-mask; g_ratio rtol 3%/atol 0.02, a NaN voxel agreeing only against a NaN); an unsupported (decoy-derived) map passes only when the submission **omits** it.

**Grading-invariance proof (the key check).** An independent from-scratch implementation using a **different** NaN-aware robust combine (drop-the-NaN then drop-most-deviant) and a **different** NaN floor reproduces all 24 panels; 4 distinct robust combines × 5 floors spanning [0.06, 0.24] all score 24/24. The plausible-but-wrong pipelines each fail only their own axis: a **plain-median (NaN-unaware) combine** (the frontier-agent proxy) fails MVF and g across the failed-fit majority (11/24); a **mean** fails 12/24; a **one-recipe-for-all** pipeline fails 21/24; **fixed calibration**, **FVF = v_ic**, **AVF = FVF**, **no NaN-masking**, and **trust-file-presence** each fail only their own panels.

### Difficulty — measured on the frontier gate

Oracle **reward 1.0**, in-container (deterministic; oracle == verifier).

| agent | runs | reward | what it did |
|---|---|---|---|
| **gpt-5.6-sol (codex, xhigh)** | **k=1** | **0.0** | Solved **19/24 panels** — got the calibration, FVF, and decoy-omit forks right (beating the plain-median proxy's 11/24), but 5 panels fail on the hidden NaN-aware robust-repeat-combine and CSF NaN-masking axis, and the binary Harbor reward zeroes on any failed panel. |
| **2nd frontier family (Claude/Gemini)** | _k≥3_ | _pending_ | _to be run by the maintainer at gate calibration_ |

**Failure mode (measured for gpt-5.6-sol; hypothesis for the 2nd family):** the model threads the recipe forks and the decoy omit correctly (19/24), but does not fully handle the un-announced failed-fit NaN in the repeated myelin acquisitions (and/or the CSF NaN-masking of the g-ratio), leaving a residual set of robustness panels NaN or biased — enough for 0.0. The residual failures land on the dominant hidden axis, not a format bug.

### Notes / honesty

- **Reconstruction paradigm.** This task's difficulty is executional (thread the recipe forks and, above all, a NaN-aware robust combine of corrupted repeats, with no bundled implementation), unlike the recognition-tier "un-cued judgement" tasks in this repo. `instruction.md` names the deliverable and the pinned definitions but never flags the repeat corruption or the decoy inputs — the agent must discover them.
- **Data.** Synthetic, small, deterministic, and **leakage-clean** (the held-out reference and planted maps are never under `/app/data`). Regenerable via `synth_build/generate_fixtures.py`.
- **allow_internet=false.** The task is self-contained (dependencies baked in the image; no network at run or verify time).
