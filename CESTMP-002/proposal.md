## CESTMP-002

**Proposal Title:** Multi-pool CEST Z-spectrum quantification of a heterogeneous saturation-offset cohort — an execution-hard reconstruction task (recipe divergence + coupled-physics assembly + hidden robustness)

**Scientific Domain:** Life Sciences · **Field:** Neuroscience · **Subfield:** Quantitative MRI / CEST (chemical-exchange saturation transfer)

**Source paper:** Zaiss & Bachert 2013, *Phys. Med. Biol.* (CEST / Z-spectrum review, https://doi.org/10.1088/0031-9155/58/22/R221); Windschuh et al. 2015, *NMR Biomed.* (multi-pool Lorentzian fit / B1 correction, https://doi.org/10.1002/nbm.3283); Zhou et al. 2003, *Nat. Med.* (amide proton transfer). Dataset: a **synthetic** multi-pool CEST Z-spectrum cohort, generated deterministically at `synth_build/generate_fixtures.py`; planted ground-truth pool amplitudes held out under `synth_build/fixture_spec.json`.

**Status: FULL runnable Harbor task.** This is a **reconstruction** task, *not* a recognition / "spot-the-confound" task — the instruction names the deliverable (produce per-voxel amide and NOE amplitude maps); the difficulty is *execution*, not an un-cued judgement. It follows the shape of the maintainer's `pcasl-cbf-quantifier`: the agent implements the multi-pool Lorentzian Z-spectrum inversion **from scratch** (no fitter bundled), over a **heterogeneous cohort where subjects need fundamentally different computations**, with a **hidden robustness** requirement, graded voxelwise against a **held-out reference** on a **convention-invariant** physical quantity.

### Why this is hard (the four difficulty drivers)

1. **Recipe divergence** — subjects need *different code paths*, discoverable only from each sidecar's acquired saturation offsets: a densely-sampled two-sided Z-spectrum identifies **both** CEST pools (amide at +3.5 ppm and NOE at −3.6 ppm), whereas a one-sided (positive-only or negative-only) spectrum has no local support for the opposite pool, whose amplitude is then **not determinable and must be omitted** (like an absolute concentration with no water reference). A single fixed recipe cannot fit the cohort.
2. **Coupled-physics assembly** — form `Z = S/S0`, apply the **per-voxel B0** frequency-axis shift (`dw_true = dw − B0`) inside a **fixed-centre/width** Lorentzian basis, divide out the per-voxel B1 saturation-efficiency factor `eta`, keep the broad **MT background pool** in the design, and solve the per-voxel ordinary-least-squares amplitudes over `{water, MT, each identifiable CEST pool}`; an error in any stage compounds across the (subject × pool) panels.
3. **Hidden robustness** — a majority of subjects carry one or two grossly motion-corrupted saturation frames (a whole offset image scaled) that must be **detected and rejected** before the fit or the amplitudes are biased; this is never announced in `instruction.md`.
4. **Convention-invariant grading** — because the centres and widths are pinned, the amplitudes `A_amide` and `A_noe` are the **unique** ordinary-least-squares coefficients of the fixed Lorentzian basis; two independent correct implementations compute them identically (proven below), so a from-scratch solver can pass while wrong pipelines fail — no reporting-convention ambiguity.

### Verifier

`tests/test_outputs.py` recomputes every amplitude map from the bundled Z-spectrum signals with a **held-out reference** pipeline (`cest_pipeline` + `cest_ref`, shipped only under `tests/`+`solution/`, never under `/app/data`) and grades **voxelwise** over the brain mask, one parametrized test per (subject × pool). There are **16 panels** (8 subjects × {amide, noe}). A determinable pool passes when ≥90% of brain voxels agree within a per-pool tolerance (rtol 5%, atol 0.003 Z-fraction); an un-identifiable pool (amide with no positive-side sampling, NOE with no negative-side sampling) passes only when the submission **omits** it. Reward is binary (pytest exit 0 → 1.0).

**Grading-invariance proof (the key check).** A genuinely-independent from-scratch implementation (SVD pseudo-inverse instead of the normal equations, batch sigma-clip instead of one-at-a-time frame rejection, its own B0/B1/identifiability handling; **no** import of the reference) reproduces every determinable panel to ~2e-9 (max abs diff) — a million-fold inside tolerance — confirming the graded amplitudes are convention-invariant. The plausible-but-wrong pipelines each fail only their own axis: **ignore B0** biases amide/NOE only on the B0-inhomogeneous subjects; **ignore B1** biases only the B1-miscalibrated subjects; **compute an un-identifiable pool** violates the omit rule; **no frame rejection** is biased only on the motion-corrupted subjects; **drop the MT pool** biases every amide/NOE panel. A naive uniform pipeline fails all 16, so partial credit is monotone in correctness.

### Difficulty — measured on the frontier gate

Oracle **reward 1.0**, in-container (deterministic; oracle == verifier).

| agent | runs | reward | what it did |
|---|---|---|---|
| **gpt-5.6-sol (codex, xhigh)** | **k=1** | **0.0** | Solved **8/16 panels**: correct on the standard, two-sided, well-conditioned subjects, but failed the hard axes — the per-voxel B0/B1 corrections on the inhomogeneous/miscalibrated subjects, the unannounced motion-corrupted saturation-frame rejection, and the omit rule on the one-sided subjects. A clean multi-axis execution failure. |
| **2nd frontier family (Claude/Gemini)** | _k≥1_ | _pending_ | _to be run by the maintainer at gate calibration_ |

**Failure mode (measured for gpt-5.6-sol; hypothesis for the 2nd family):** the model implements a single clean multi-pool Lorentzian fit and applies it uniformly — it handles the standard subjects but does not correctly thread the per-voxel B0/B1 corrections through the inhomogeneous subjects, nor discover-and-reject the unannounced corrupted saturation frames, and mishandles the omit forks on the one-sided spectra. Its underlying least-squares fit is otherwise correct (the standard panels pass), so the 0.0 is earned on the genuine hard axes, not a format bug.

### Notes / honesty

- **Reconstruction paradigm.** This task's difficulty is executional (assemble a coupled per-voxel inversion with no recipe), unlike the recognition-tier "un-cued judgement" tasks in this repo. `instruction.md` names the deliverable and the physics conventions but never enumerates the pitfalls (per-voxel B0/B1, the corrupted frames, the omit forks, the MT background pool) — the agent must discover them from the data.
- **Data.** Synthetic, small, deterministic, and **leakage-clean** (the held-out reference and planted amplitudes are never under `/app/data`; the `fixture_spec.json` is explicitly build-provenance only). Regenerable via `synth_build/generate_fixtures.py`.
- **allow_internet=false.** The task is self-contained (dependencies baked in the image; no network at run or verify time).
