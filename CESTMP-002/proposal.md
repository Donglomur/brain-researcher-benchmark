## CESTMP-002

**Proposal Title:** Multi-pool CEST Z-spectrum quantification of a heterogeneous saturation-offset cohort — an execution-hard reconstruction task (recipe divergence + coupled-physics assembly + declared robustness with hidden realization)

**Scientific Domain:** Life Sciences · **Field:** Neuroscience · **Subfield:** Quantitative MRI / CEST (chemical-exchange saturation transfer)

**Source paper:** Zaiss & Bachert 2013, *Phys. Med. Biol.* (CEST / Z-spectrum review, https://doi.org/10.1088/0031-9155/58/22/R221); Windschuh et al. 2015, *NMR Biomed.* (multi-pool Lorentzian fit / B1 correction, https://doi.org/10.1002/nbm.3283); Zhou et al. 2003, *Nat. Med.* (amide proton transfer). Dataset: a **paper-parameterized** multi-pool CEST Z-spectrum cohort, generated deterministically at `synth_build/generate_fixtures.py`; grading is against a held-out **pinned-method target** at `tests/planted_truth.npz` (built by `synth_build/build_truth.py`), never shipped under `/app/data`.

**Status: FULL runnable Harbor task.** This is a **reconstruction** task, *not* a recognition / "spot-the-confound" task — the instruction names the deliverable (produce per-voxel amide and NOE amplitude maps); the difficulty is *execution*, not an un-cued judgement. It follows the shape of the maintainer's `pcasl-cbf-quantifier`: the agent implements the multi-pool Lorentzian Z-spectrum inversion **from scratch** (no fitter bundled), over a **heterogeneous cohort where subjects need fundamentally different computations**, with a **publicly-declared robustness** requirement (the corrupted-frame realization hidden), graded voxelwise against a **held-out pinned-method target** on a **convention-invariant** physical quantity.

### Why this is hard (the four difficulty drivers)

1. **Recipe divergence** — subjects need *different code paths*, discoverable only from each sidecar's acquired saturation offsets: a densely-sampled two-sided Z-spectrum identifies **both** CEST pools (amide at +3.5 ppm and NOE at −3.6 ppm), whereas a one-sided (positive-only or negative-only) spectrum has no local support for the opposite pool, whose amplitude is then **not determinable and must be omitted** (like an absolute concentration with no water reference). A single fixed recipe cannot fit the cohort.
2. **Coupled-physics assembly** — form `Z = S/S0`, apply the **per-voxel B0** frequency-axis shift (`dw_true = dw − B0`) inside a **fixed-centre/width** Lorentzian basis, divide out the per-voxel B1 saturation-efficiency factor `eta`, keep the broad **MT background pool** in the design, and solve the per-voxel ordinary-least-squares amplitudes over `{water, MT, each identifiable CEST pool}`; an error in any stage compounds across the (subject × pool) panels.
3. **Declared robustness, hidden realization** — a majority of subjects (5 of 8) carry one or two grossly motion-corrupted saturation frames (a whole offset image scaled) that must be **detected and rejected** before the fit or the amplitudes are biased. `instruction.md` now *declares* this contract (a *Robustness / data-quality contract* section); only the *realization* — which subjects, which frames — is hidden. The corruption is a gross, unambiguous outlier (each corrupted frame's median |residual| is ~30×–70× the largest clean-frame residual — measured), so the retained frame set is unambiguous.
4. **Convention-invariant grading** — because the centres and widths are pinned, the amplitudes `A_amide` and `A_noe` are the **unique** ordinary-least-squares coefficients of the fixed Lorentzian basis on the retained frames; four independent solvers compute them identically (proven below), so a from-scratch solver can pass while wrong pipelines fail — no reporting-convention ambiguity.

### What changed in this revision (grade-vs-planted rework)

The graded amplitudes are estimated from a **noisy** Z-spectrum whose CEST dips sit near the
measurement-noise floor, so the noise-free (clean-signal) amplitude is **not recoverable** to
grading tolerance by any estimator (a clean-signal target agreed with the oracle only ~81–90%).
The rescue is **Pattern C — a frozen pinned-method target**:

1. **Graded against a held-out pinned-method target, not a private pipeline.** The verifier no
   longer imports or runs a reference. It compares each submitted map, voxelwise, to
   `tests/planted_truth.npz` = the **pinned ordinary-least-squares amplitudes on the real
   signals with the ground-truth-corrupted frames removed** (built by `synth_build/build_truth.py`,
   which uses a different linear-algebra path — SVD `lstsq` — from the old reference's normal
   equations). This is legitimate **only because the estimator is uniquely determined**: the pool
   centres/widths are pinned, so the amplitudes are the unique OLS coefficients of a fixed linear
   basis on a fixed frame set. The dead reference modules (`cest_pipeline.py`, `cest_ref.py`) were
   `git rm`'d from `tests/`.
2. **Invariance proof (decisive gate, measured).** Four independent solvers — SVD pseudo-inverse,
   QR, the normal equations, and `scipy.linalg.lstsq` — plus the original reference all reproduce
   the frozen target to **≤1.3×10⁻⁶ relative (max), ~3×10⁻¹⁰ absolute → 100% voxel agreement at
   the verifier tolerance**, confirming the amplitudes are convention-invariant. The corrupted
   frames are gross, unambiguous outliers (median |residual| **29×–67×** the largest clean-frame
   residual), so every reasonable robust rule keeps exactly the same frame set → the target is
   well-defined.
3. **Robustness contract made public.** `instruction.md` now declares the *Robustness /
   data-quality contract* (corrupted frames exist and must be rejected; do not drop clean frames);
   only the realization stays hidden. Grade-vs-target language replaces the old "recomputed by a
   held-out reference" wording, and states any scientifically valid estimator is accepted.

### Verifier

`tests/test_outputs.py` grades **voxelwise** over the brain mask against `tests/planted_truth.npz`,
one parametrized test per (subject × pool) — **16 panels** (8 subjects × {amide, noe}). An
identifiable pool passes when ≥90% of brain voxels agree with the pinned-method target within a
**tight** per-pool tolerance (rtol 2×10⁻³, atol 2×10⁻⁵ Z-fraction — ~1000× tighter than the old
5% noise-floor tolerance, since any faithful OLS implementation matches to ~10⁻⁶); an
un-identifiable pool (amide with no positive-side sampling, NOE with no negative-side sampling)
passes only when the submission **omits** it. Reward is binary (pytest exit 0 → 1.0).

**Validity / discrimination evidence (measured this revision).** The **oracle passes all 16
panels** (12 identifiable at 100% voxel agreement, 4 correctly omitted) against the frozen target.
A **naive fit that keeps the corrupted frames (no rejection) fails 8 panels** — exactly the five
motion-corrupted subjects (sub-01, sub-03 [two corruptions], sub-04, sub-05, sub-08), at ~0% voxel
agreement — while the three uncorrupted subjects (sub-02, sub-06, sub-07) still pass, and the omit
panels on the corrupted-but-one-sided subjects (sub-05/noe, sub-08/amide) pass as omissions. The
other plausible-but-wrong pipelines each fail only their own axis: **ignore B0** biases amide/NOE
on the B0-inhomogeneous subjects; **ignore B1** biases the B1-miscalibrated subjects; **compute an
un-identifiable pool** violates the omit rule; **drop the MT pool** biases every amide/NOE panel.
So a from-scratch correct solver passes and single-axis shortcuts fail, on axes the instruction
now *declares*.

### Difficulty — frontier gate

Oracle **reward 1.0**, verified in-container against the held-out target (the pinned-method
target is recovered on all 16 panels; the oracle no longer *is* the verifier — it is one valid
estimator among many that match the frozen target).

On the *previous* (hidden-contract, reference-recompute) version, **gpt-5.6-sol (codex, xhigh)
scored 0.0 at k=1**, solving 8/16 panels — correct on the standard two-sided well-conditioned
subjects but failing the hard axes (per-voxel B0/B1 on the inhomogeneous/miscalibrated subjects,
the corrupted-frame rejection, the one-sided omit rule).

**Frontier re-gate on this revised (public-contract, grade-vs-target) version: PENDING.** Because
this revision *discloses* the robustness requirement and tightens the tolerance, the old gate
number does not transfer and must be re-measured — not overclaimed here. The expectation is that
the multi-axis assembly stays hard (per-voxel B0/B1 threading, discover-and-reject the hidden
corrupted frames without dropping clean ones, the one-sided omit forks, keeping the MT background
pool); the local discrimination above shows every single-axis shortcut still fails. A 2nd frontier
family (Claude/Gemini) gate is likewise pending at maintainer calibration.

### Notes / honesty

- **Reconstruction paradigm.** This task's difficulty is executional (assemble a coupled per-voxel inversion with no recipe), unlike the recognition-tier "un-cued judgement" tasks in this repo. `instruction.md` names the deliverable and the physics conventions but never enumerates the pitfalls (per-voxel B0/B1, the corrupted frames, the omit forks, the MT background pool) — the agent must discover them from the data.
- **Data.** Paper-parameterized, small, deterministic, and **leakage-clean** (the held-out pinned-method target `tests/planted_truth.npz` lives only under `tests/`, never under `/app/data`; the `fixture_spec.json` is explicitly build-provenance only). Regenerable via `synth_build/generate_fixtures.py` then `synth_build/build_truth.py`.
- **allow_internet=false.** The task is self-contained (dependencies baked in the image; no network at run or verify time).
