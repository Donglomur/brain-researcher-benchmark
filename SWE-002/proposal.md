## SWE-002

**Proposal Title:** Shear-wave elastography of a heterogeneous ultrafast-imaging cohort — an execution-hard reconstruction task (recipe divergence + coupled-physics assembly + hidden robustness)

**Scientific Domain:** Life Sciences · **Field:** Neuroscience · **Subfield:** Elastography / tissue biomechanics

**Source paper:** Bercoff, Tanter & Fink 2004, *IEEE Trans. Ultrason. Ferroelectr. Freq. Control* (supersonic shear imaging / ultrafast shear-wave elastography, https://doi.org/10.1109/TUFFC.2004.1295425). Dataset: a **synthetic** ultrafast shear-wave-elastography cohort, generated deterministically at `synth_build/generate_fixtures.py`; planted ground-truth modulus and usable-region maps held out under `synth_build/fixture_spec.json`.

**Status: FULL runnable Harbor task.** This is a **reconstruction** task, *not* a recognition / "spot-the-confound" task — the instruction names the deliverable (produce a Young's-modulus map and, where determinable, an inter-push reliability map); the difficulty is *execution*, not an un-cued judgement. It follows the shape of the maintainer's `pcasl-cbf-quantifier`: the agent implements the shear-wave time-of-flight inversion **from scratch** (no estimator bundled), over a **heterogeneous 9-subject cohort where subjects need fundamentally different computations**, with a **hidden robustness** requirement, graded voxelwise against a **held-out reference** on a **convention-invariant** physical quantity.

### Why this is hard (the four difficulty drivers)

1. **Recipe divergence** — subjects need *different code paths*, discoverable only from each sidecar and the data quality. The cohort mixes three push geometries, and "two pushes ⇒ the whole field is covered" is **false**: (1) **single-push** subjects illuminate one side well while the far side decays into tracking noise, so an inter-push reliability map is not determinable and both must be omitted (NaN / no file); (2) **opposite-origin 2-push** subjects jointly illuminate the whole field and report per-push agreement as a reliability map; (3) **same-side 2-push** subjects fire both pushes from the same window, so the opposite far side is dead from both pushes and must still be masked **even though the subject has ≥2 pushes**. The frame period `dt = 1/frame_rate` differs per subject, so a delay in frames must be scaled per subject to become a speed.
2. **Coupled-physics assembly** — the cross-correlation delay estimate, the direction-aware wavefront handling (the wave leaves the push in both directions, so the band containing the push has a non-monotonic arrival), the per-push consistency check, the multi-push combination that only credits regions some push actually reaches, the frame-rate scaling, and the `E=3·rho·c²` conversion must **all** be assembled correctly.
3. **Hidden robustness** — never stated in the instruction: a stiff inclusion reflects the wave, and inside such a region a comparable-amplitude reverse-propagating copy overlaps the forward wave so adjacent traces de-cohere and a naive cross-correlation delay is spurious — the region must be **masked**. A majority of subjects (8 of 9) carry at least one un-estimable region; only one clean opposite-origin control has nothing to mask.
4. **Convention-invariant grading** — the forward field is a non-dispersive, shape-preserving lateral translation with a region-constant speed, so the adjacent-trace cross-correlation delay is exactly `dx/c` and every correct time-of-flight implementation converges to the same speed (proven below).

### Verifier

`tests/test_outputs.py` recomputes every map from the bundled velocity movies with a **held-out reference** pipeline (`swe_pipeline` + `swe_ref`, shipped only under `tests/`+`solution/`, never under `/app/data`) and grades **voxelwise** over the in-field pixels, one parametrized test per (subject × map) panel — 18 panels total. Reward is **fractional** (fraction of panels correct). A modulus panel passes when ≥90% of in-field pixels agree (**both** masked NaN or **both** finite within rtol 0.12/atol 0.6 kPa); a reliability panel passes when a single-push subject **omits** it, and when a multi-push subject emits a same-shape [0,1] map whose finite/NaN pattern matches the usable-region mask (its numeric content, a reporting convention, is not graded).

**Grading-invariance proof (the key check).** A fully independent implementation (FFT cross-correlation, Gaussian sub-sample peak fit, per-row arrival-vs-distance-from-push regression, an agreement-FRACTION usability criterion instead of a MAD dispersion, SNR-weighted combination; **no** import of the reference) reproduces all 18 panels (max modulus diff ~0.29 kPa, median ~0.09 kPa) and its usable/masked decision agrees with the reference on every one of the 54 (subject × band × reachable-push) cells — the usable dispersion stays ≤0.085 while every masked cell exceeds 0.56, so any cut in [0.10, 0.55] gives the identical mask (invariance is not threshold-tuned). The plausible-but-wrong pipelines each fail on their own axis: the shear modulus `rho·c²` fails all 9 modulus panels; emitting reliability for single-push subjects fails 4 panels; never emitting it fails 5; a single fixed frame period fails the 6 off-rate modulus panels; using only the first push mis-masks the multi-push subjects. A naive never-mask uniform pipeline (correct estimator and reliability policy, but no robustness) fails 12 of 18 panels (passfrac 0.333) — 8 modulus panels plus the 4 multi-push reliability panels whose masked regions it fills.

### Difficulty — measured on the frontier gate

Oracle **reward 1.0**, in-container (deterministic; oracle == verifier).

| agent | runs | reward | what it did |
|---|---|---|---|
| **gpt-5.6-sol (codex, xhigh)** | **k=1** | **0.0** | Solved **13/18 panels**; the failures fall on the task's hard axes — the hidden masking of un-estimable regions (far-field decay, the same-side dead far side, and the wave-reflection regions), the per-geometry reliability omit/emit policy, and the per-subject frame-rate scaling. |
| **2nd frontier family (Claude/Gemini)** | _k≥3_ | _pending_ | _to be run by the maintainer at gate calibration_ |

**Failure mode (measured for gpt-5.6-sol; hypothesis for the 2nd family):** the model implements the time-of-flight estimator and modulus conversion but does not discover-and-mask the unannounced un-estimable regions (assuming multiple pushes cover the whole field), so the residual failures land on the genuine hidden-robustness axis rather than a format bug.

### Notes / honesty

- **Reconstruction paradigm.** The difficulty is executional (get the wave physics, per-geometry coverage, and masking right with no recipe). `instruction.md` names the deliverable and the physics conventions but never enumerates the pitfalls (the reflections, the far-field/same-side dead regions) — the agent must discover them from the data.
- **Data.** Synthetic, small, deterministic, and **leakage-clean** (the held-out reference and planted maps are never under `/app/data`). Regenerable via `synth_build/generate_fixtures.py`.
- **allow_internet=false.** The task is self-contained (dependencies baked in the image; no network at run or verify time).
