## APTPH-002

**Proposal Title:** pH-weighted amide-proton-transfer (APT) CEST ratiometric indices over a heterogeneous Z-spectrum cohort — an execution-hard reconstruction task (recipe divergence + coupled B0/robustness assembly + convention-invariant grading)

**Scientific Domain:** Life Sciences · **Field:** Neuroscience · **Subfield:** CEST / molecular MRI

**Source paper:** McVicar et al. 2014, *J. Cereb. Blood Flow Metab.* (concentration-independent AACID pH imaging, https://doi.org/10.1038/jcbfm.2014.12); Zhou et al. 2003, *Nat. Med.* (amide proton transfer / APT-CEST). Dataset: a **synthetic** APT-CEST saturation Z-spectrum cohort, generated deterministically at `synth_build/generate_fixtures.py`; planted ground-truth indices held out under `synth_build/fixture_spec.json`.

**Status: FULL runnable Harbor task.** This is a **reconstruction** task, *not* a recognition / "spot-the-confound" task — the instruction names the deliverable (produce the per-voxel ratiometric APT indices APTR and AACID); the difficulty is *execution*, not an un-cued judgement. It follows the shape of the maintainer's reconstruction tasks (e.g. `pcasl-cbf-quantifier`): the agent implements the ratiometric pH-weighted analysis **from scratch** (no fitter bundled), over a **heterogeneous cohort where subjects need fundamentally different computations**, with a **hidden robustness** requirement, graded voxelwise against a **held-out reference** on **convention-invariant** ratio quantities.

### Why this is hard (the four difficulty drivers)

1. **Recipe divergence** — subjects need *different code paths*, discoverable only from each sidecar's acquired-offset list. Four subjects densely sample the guanidinium/amine region (~2.5–3.0 ppm), so the concentration-independent AACID pH index is determinable; four **gap** that region (only the amide side is sampled), so AACID is **not computable and must be omitted** (like a water-reference-absent absolute concentration) while the always-determinable ratiometric APTR index is still produced. A single fixed offset schedule cannot fit the cohort.
2. **Coupled-physics assembly** — the graded indices are exact ratios of B0-corrected Z-values, but their definitions (which offsets; the direct spectrum, not a parametric pool-model fit; amine at 2.75 ppm, not 2.0 ppm) must all be assembled correctly, and each mistake corrupts a different subset of the (subject × index) panels.
3. **Hidden robustness** — threaded through every subject is a per-voxel B0 correction (the B0-corrected Z-value at pinned offset Ω is the cleaned spectrum interpolated at Ω+b0); six of eight subjects carry strong ±0.30 ppm shifts, and skipping it biases both indices. Independently, a **majority** of subjects (six of eight) carry one or two grossly motion-corrupted whole-offset frames that must be **detected as outliers** of the otherwise-smooth Z-spectrum and rejected before the pinned offsets are read. Neither is announced in `instruction.md`.
4. **Convention-invariant grading** — both indices are ratios of B0-corrected Z-values, so the M0/normalisation scale cancels; two independent correct implementations compute them identically (proven below), so a from-scratch solver can pass while wrong pipelines fail — no reporting-convention ambiguity.

### Verifier

`tests/test_outputs.py` recomputes both indices from the bundled Z-spectra with a **held-out reference** pipeline (`aptph_pipeline` + `aptph_ref`, shipped only under `tests/` + `solution/`, never under `/app/data`) and grades **voxelwise** over the brain mask, one parametrized test per (subject × index) panel (16 panels). A computable index passes when ≥90% of brain voxels agree within (rtol 6%, atol 0.03); an unsupported index (AACID where the amine offset 2.75 ppm is not bracketed) passes only when the submission **omits** it. The authoritative Harbor reward is binary (pytest rc → 1.0 iff every panel passes).

**Grading-invariance proof (the key check).** A fully independent from-scratch implementation (PCHIP monotone-cubic B0 interpolation instead of linear; a different, mean-aggregated batch outlier rejection instead of median-aggregated iterative; **no** import of the reference) reproduces every computable panel to ~1% median / <5% max relative error, 0% of voxels outside tolerance — so the ratios are convention-invariant. The plausible-but-wrong pipelines each fail only their own axis: **skip B0** fails 7/16, **no frame rejection** fails 7/16, **AACID for all** or **AACID for none** fails 12/16, **amine at 2.0 ppm** fails 12/16; a naive uniform pipeline (ignore B0, no rejection, AACID for everyone) fails 14/16 — so partial credit is monotone in correctness.

### Difficulty — measured on the frontier gate

Oracle **reward 1.0**, in-container (deterministic; oracle == verifier).

| agent | runs | reward | what it did |
|---|---|---|---|
| **gpt-5.6-sol (codex, xhigh)** | **k=1** | **0.0** | Solved **7/16 panels**, failing the per-voxel B0-correction, corrupted-frame-rejection, and AACID omit-fork axes the task is built around. |
| **2nd frontier family (Claude/Gemini)** | _k≥3_ | _pending_ | _to be run by the maintainer at gate calibration_ |

**Failure mode (measured for gpt-5.6-sol; hypothesis for the 2nd family):** the model implements a single clean ratiometric pipeline and applies it uniformly — solving the standard/mild panels but missing the unannounced hidden-robustness axes (per-voxel B0 threading, discover-and-reject the corrupted frames) and the per-subject AACID omit fork. The nine failed panels are the ones gated on those hard axes; the k=1 gate reports the count (7/16), and a per-panel itemization will come from the maintainer's calibration run.

### Notes / honesty

- **Reconstruction paradigm.** The difficulty is executional (get many coupled quantitative decisions right with no recipe), unlike the recognition-tier "un-cued judgement" tasks in this repo. `instruction.md` names the deliverable and the physics conventions but never enumerates the pitfalls (per-voxel B0, the corrupted frames, the AACID omit fork) — the agent must discover them from the data.
- **Data.** Synthetic, small, deterministic, and **leakage-clean** (the held-out reference and planted parameters are never under `/app/data`). Regenerable via `synth_build/generate_fixtures.py`.
- **allow_internet=false.** The task is self-contained (dependencies baked in the image; no network at run or verify time).
