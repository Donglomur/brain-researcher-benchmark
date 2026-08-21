## TRACTOCONN-002

**Proposal Title:** Deterministic-tractography structural connectivity of a heterogeneous seeded cohort — an execution-hard reconstruction task (seeding recipe divergence + coupled tracker assembly + hidden cleanup)

**Scientific Domain:** Life Sciences · **Field:** Neuroscience · **Subfield:** Diffusion MRI / tractography

**Source paper:** Mori et al. 1999, *Ann. Neurol.* (FACT deterministic streamline tractography, https://doi.org/10.1002/1531-8249(199902)45:2<265::AID-ANA21>3.0.CO;2-3); Hagmann et al. 2008, *PLoS Biol.* (structural connectome from tractography). Dataset: a **synthetic** deterministic-tractography peak-field cohort, generated deterministically at `synth_build/generate_fixtures.py`; planted ground-truth connectomes held out under `synth_build/fixture_spec.json`.

**Status: FULL runnable Harbor task.** This is a **reconstruction** task, *not* a recognition / "spot-the-confound" task — the instruction names the deliverable (run the pinned tracker and build the atlas connectivity matrix); the difficulty is *execution*, not an un-cued judgement. It follows the shape of the maintainer's reconstruction tasks (e.g. `pcasl-cbf-quantifier`): the agent implements the deterministic-tractography connectivity pipeline **from scratch** (no tracker bundled), over a **heterogeneous cohort where subjects need fundamentally different computations**, with a **hidden cleanup** requirement, graded entrywise against a **held-out reference** on an **exactly-determined** integer quantity.

### Why this is hard (the four difficulty drivers)

1. **Recipe divergence** — subjects need *different code paths*, discoverable only from each subject's seed mask. Some subjects are **whole-brain** seeded (every brain voxel is a seed, so the full connectome is determined) and others are **ROI-seeded** (only a strict subset of the gray-matter ROIs is seeded, so only pairs touching a seeded ROI are determinable and the rest must be **omitted** as NaN). Because ROI-seeding launches from far fewer voxels, it also yields *different counts* on the pairs it does determine, so a pipeline that seeds the whole brain regardless is wrong on both the values and the omitted pairs.
2. **Coupled-physics assembly** — the tracker is delicate: fixed-step nearest-voxel FACT-style stepping, bidirectional from each seed, with the crossing rule that at a two-peak voxel you follow the peak closest to the **incoming direction** (NOT the largest-amplitude peak) — get that wrong and the smaller bundle is truncated at every crossing and its ROI-pair count collapses.
3. **Hidden robustness / cleanup** — a **majority** of the cohort additionally carries spurious short fascicles (both ends in gray matter but far below any real bundle length) that contaminate the connectome and must be excluded by a minimum streamline length before counting — this cleanup is **not stated** in the instruction and must be inferred from the bimodal streamline-length distribution.
4. **Convention-invariant grading** — because tracking steps a fixed unit between integer voxel centres, the reference counts are bit-exact; any in-gap minimum-length cut gives identical integer counts, so exact integer agreement is the convention-invariant bar. Two independent correct implementations reproduce all determined entries with zero error (proven below), so a from-scratch tracker can pass while wrong pipelines fail.

### Verifier

`tests/test_outputs.py` recomputes every subject's connectome from the bundled peak field with a **held-out reference** tracker (`tracto_pipeline` + `tracto_core`, shipped only under `tests/` + `solution/`, never under `/app/data`) and grades **entrywise** over 16 panels (8 subjects × {values, omit}). The VALUES panel passes when every determined ROI-pair count matches the reference exactly (nearest integer); the OMIT panel passes when every un-determined pair is NaN and every determined pair is present. The Harbor reward is fractional over the 16 panels.

**Grading-invariance proof (the key check).** A fully independent implementation (integer-voxel stepping, a different in-gap minimum-length cut of 24 mm vs the reference 20 mm, stacked-argmax peak selection, dict-based accumulation; **no** import of the reference) reproduces all 211 determined entries with **zero** error — so exact integer agreement is the convention-invariant bar. The plausible-but-wrong pipelines each fail only their own axis: whole-brain-always 6/16, no-length-cleanup 10/16, fill-zero-omit 11/16, largest-amplitude-peak 13/16, and the plainest naive pipeline (whole-brain + no cleanup + no omit) fails a majority at 4/16 — so partial credit is monotone in correctness.

### Difficulty — measured on the frontier gate

Oracle **reward 1.0**, in-container (deterministic; oracle == verifier).

| agent | runs | reward | what it did |
|---|---|---|---|
| **gpt-5.6-sol (codex, xhigh)** | **k=1** | **0.0** | Solved **10/16 panels**, failing the whole-brain-vs-ROI-seeded omit fork (NaN un-determined pairs), the incoming-direction crossing rule, and the unannounced minimum-length spurious-fascicle cleanup axes the task is built around. |
| **2nd frontier family (Claude/Gemini)** | _k≥3_ | _pending_ | _to be run by the maintainer at gate calibration_ |

**Failure mode (measured for gpt-5.6-sol; hypothesis for the 2nd family):** the model implements a single clean deterministic tracker and applies it uniformly — solving some panels but missing the per-subject seeding omit fork (NaN the un-determined pairs; ROI-seeding changes the determined counts too), the exact incoming-direction crossing rule at two-peak voxels, and the discover-and-apply of the unannounced minimum-length cleanup. The six failed panels are the ones gated on those hard axes; the k=1 gate reports the count (10/16), and a per-panel itemization will come from the maintainer's calibration run.

### Notes / honesty

- **Reconstruction paradigm.** The difficulty is executional (implement an exact deterministic tracker and get the per-subject decisions right with no tracker bundled), unlike the recognition-tier "un-cued judgement" tasks in this repo. `instruction.md` names the deliverable and pins the tracker but never announces the pitfalls (the seeding omit fork, the incoming-direction crossing rule, the spurious-fascicle cleanup) — the agent must discover them from the data.
- **Data.** Synthetic, small, deterministic, and **leakage-clean** (the held-out reference and planted connectomes are never under `/app/data`). Regenerable via `synth_build/generate_fixtures.py`.
- **allow_internet=false.** The task is self-contained (dependencies baked in the image; no network at run or verify time).
