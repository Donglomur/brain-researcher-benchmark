## VASO-002

**Proposal Title:** VASO cerebral-blood-volume quantification for a heterogeneous cohort — an execution-hard reconstruction task (recipe divergence + coupled-physics assembly + hidden robustness)

**Scientific Domain:** Life Sciences · **Field:** Neuroscience · **Subfield:** Perfusion MRI / VASO

**Source paper:** Lu et al. 2003, *MRM* (Functional MRI based on changes in vascular space occupancy / VASO, https://doi.org/10.1002/mrm.10519); Huber et al. 2014, *MRM* (Slab-selective, BOLD-corrected VASO / SS-SI-VASO at 7 T, https://doi.org/10.1002/mrm.24916). Dataset: a **synthetic** VASO functional cohort (8 subjects, block-design task; some with an interleaved not-nulled BOLD run), generated deterministically at `synth_build/generate_fixtures.py`; planted ground truth held out under `synth_build/fixture_spec.json`.

**Status: FULL runnable Harbor task.** This is a **reconstruction** task, *not* a recognition / "spot-the-confound" task — the instruction names the deliverable (produce the per-voxel task-evoked CBV-change maps, and the BOLD percent-change where supported); the difficulty is *execution*, not an un-cued judgement. It follows the shape of the maintainer's `pcasl-cbf-quantifier`: the agent implements the VASO CBV-change quantification **from scratch** (no pipeline bundled), over a **heterogeneous cohort where subjects need fundamentally different computations**, with a **hidden robustness** requirement, graded voxelwise against a **held-out reference** on a **convention-invariant** quantity.

### Why this is hard (the four difficulty drivers)

1. **Recipe divergence** — a **BOLD-correction fork**, discoverable only from the sidecar: SS-SI-VASO subjects (five of eight) ship both a blood-nulled and a not-nulled (BOLD) image and their CBV change **must** be formed from the BOLD-corrected VASO signal `Vc = nulled/not-nulled` (which cancels the activation-driven T2*/BOLD weighting — long TE means the raw nulled signal is contaminated, even sign-flipped, by BOLD); plain-VASO subjects ship the nulled image only (short TE, BOLD negligible) and `Vc = nulled`. Applying the plain recipe to an SS-SI subject biases — and can sign-flip — the CBV change. Two **omit forks** follow: `dCBV_task2` exists only for two-condition subjects, and `dBOLD` only for SS-SI subjects — computing either where the acquisition cannot support it is wrong, like an absolute concentration with no water reference.
2. **Coupled-physics assembly** — the frame rejection, the BOLD-corrected ratio, the per-condition block means over rest/task frames, and the pinned CBV-change definition `dCBV_taskK = −100·(1−V0)·(mean_taskK(Vc) − mean_rest(Vc))/mean_rest(Vc)` (with the pinned baseline `V0`) must all be assembled correctly; an error in any one corrupts a different subset of panels.
3. **Hidden robustness** — spanning a *majority*: six of eight subjects carry a few grossly corrupted time frames (motion / inversion-failure spikes scaling a whole frame by ~0.5×–1.8×) that must be **rejected** before the block means, else the perfusion contrast is biased. None of the artifacts is announced.
4. **Convention-invariant grading** — the receive/M0/TI/TR scale factors cancel in the temporal ratio, so the graded quantities are convention-invariant given the pinned `V0` and definitions; a genuinely different frame-rejection method reproduces every panel, so two independent correct implementations agree.

### Verifier

`tests/test_outputs.py` recomputes every map from the bundled VASO time-series with a **held-out reference** pipeline (`vaso_pipeline` + `vaso_ref`, shipped only under `tests/`+`solution/`, never under `/app/data`) and grades **voxelwise** over the grey+white-matter ROI. Each (subject × map) is its own parametrized test — 24 panels (8 subjects × {`dCBV_task1`, `dCBV_task2`, `dBOLD`}) — so the CTRF breakdown is monotone in correctness while the Harbor reward is binary (all panels must pass). A computable map passes when ≥90% of ROI voxels agree with the reference within (rtol 0.08, atol 0.30); an unsupported map (`dCBV_task2` for a one-condition subject, `dBOLD` for a plain-VASO subject) passes only when the submission **omits** it.

**Grading-invariance proof (the key check).** A genuinely-correct independent implementation (a different frame-rejection method — spatial-outlier-fraction vs temporal MAD-z — and its own fork branching; **no** import of the reference) reproduces every computable panel to within ~1e-7 (median relative error ~2e-8); even a pessimistic correct solver (log-ratio form, dropping an extra clean frame per condition) fails under 1% of voxels. The plausible-but-wrong pipelines each fail only their own axis: **skip the BOLD correction** fails only the SS-SI `dCBV` panels; **no frame rejection** fails only the motion subjects; **compute an unsupported map** fails only the omit panels — a naive uniform pipeline fails 15 of 24.

### Difficulty — measured on the frontier gate

Oracle **reward 1.0**, in-container (deterministic; oracle == verifier).

| agent | runs | reward | what it did |
|---|---|---|---|
| **gpt-5.6-sol (codex, xhigh)** | **k=1** | **0.0** | Solved **12/24 panels**, failing the genuine hard axes — the SS-SI vs plain BOLD-correction fork (which can sign-flip the CBV change), the unannounced corrupted-frame rejection, and the `dCBV_task2` / `dBOLD` omit forks. |
| **2nd frontier family (Claude/Gemini)** | _k≥3_ | _pending_ | _to be run by the maintainer at gate calibration_ |

**Failure mode (measured for gpt-5.6-sol; hypothesis for the 2nd family):** the model implements one clean VASO pipeline and applies it uniformly — it does not thread the per-subject BOLD-correction fork, does not discover-and-reject the unannounced corrupted frames, and does not honour the omit forks. The 0.0 is earned on the genuine hard axes, not a format bug.

### Notes / honesty

- **Reconstruction paradigm.** The difficulty is executional (branch the BOLD-correction fork, reject corrupted frames, form the pinned CBV-change definition, and honour the omit forks — with no bundled pipeline), unlike the recognition-tier "un-cued judgement" tasks in this repo. `instruction.md` names the deliverable and pins the definitions but never enumerates the pitfalls (the corrupted frames, which fork applies) — the agent must discover them from the data.
- **Data.** Synthetic, small, deterministic, and **leakage-clean** (the held-out reference and planted parameters are never under `/app/data`). Regenerable via `synth_build/generate_fixtures.py`.
- **allow_internet=false.** The task is self-contained (dependencies baked in the image; no network at run or verify time).
