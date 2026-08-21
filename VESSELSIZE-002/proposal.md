## VESSELSIZE-002

**Proposal Title:** Vessel-size imaging (VSI) from a heterogeneous dynamic-susceptibility-contrast cohort — an execution-hard reconstruction task (recipe divergence + coupled-physics assembly + hidden robustness)

**Scientific Domain:** Life Sciences · **Field:** Neuroscience · **Subfield:** Perfusion MRI / vessel-size imaging

**Source paper:** Tropès et al. 2001, *Magn. Reson. Med.* (vessel-size imaging); Jensen & Chandra 2000, *Magn. Reson. Med.* (vessel-density index Q); Boxerman, Schmainda & Weisskoff 2006, *AJNR* (contrast-agent leakage correction). Dataset: a **synthetic** dynamic-susceptibility-contrast vessel-size-imaging cohort, generated deterministically at `synth_build/generate_fixtures.py`; planted ground-truth rCBV / vessel_radius / Q maps held out under `synth_build/fixture_spec.json`.

**Status: FULL runnable Harbor task.** This is a **reconstruction** task, *not* a recognition / "spot-the-confound" task — the instruction names the deliverable (produce rCBV and, where determinable, vessel_radius and Q maps); the difficulty is *execution*, not an un-cued judgement. It follows the shape of the maintainer's `pcasl-cbf-quantifier`: the agent implements the VSI inversion **from scratch** (no fitter bundled), over a **heterogeneous 8-subject cohort where subjects need fundamentally different computations**, with a **hidden robustness** requirement, graded voxelwise against a **held-out reference** on a **convention-invariant** physical quantity.

### Why this is hard (the four difficulty drivers)

1. **Recipe divergence** — subjects need *different code paths*, discoverable only from each sidecar. Five subjects carry **both** a gradient-echo and a spin-echo dynamic series (vessel radius and density index Q are then determinable) and three are **GE-only** (radius/Q are not determinable and must be **omitted**). The vessel maps are defined only in parenchyma, so CSF and large-vessel voxels (a labelled macrovascular population) must be written as **NaN**. The vessel-radius calibration uses **each subject's own AIF peak** susceptibility, so a fixed susceptibility biases the radius on every subject whose dose/AIF differs.
2. **Coupled-physics assembly** — the log-signal-to-ΔR2* conversion, the leakage regression and first-pass integral, the AIF-peak susceptibility calibration, and the peak-ratio vessel-size / density inversion must **all** be assembled correctly; every bolus has a spatially-varying recirculation second pass, so rCBV must integrate the **first pass only** — integrating past it biases rCBV on every subject.
3. **Hidden robustness** — a majority of subjects carry a contrast-agent-leakage region whose gradient-echo curve is corrupted by a slowly-accumulating T1 term that biases **both** rCBV and the bolus-peak vessel maps unless it is **detected and removed** (a Boxerman–Weisskoff two-parameter fit against a white-matter reference curve).
4. **Convention-invariant grading** — rCBV (WM-normalized first-pass integral), vessel_radius (µm, with pinned constants and the bolus-peak convention), and Q are uniquely determined given the pinned signal model, so two independent correct implementations compute them identically (proven below); undeterminable voxels agree as NaN.

### Verifier

`tests/test_outputs.py` recomputes every map from the bundled signals with a **held-out reference** pipeline (`vsi_pipeline` + `vsi_ref`, shipped only under `tests/`+`solution/`, never under `/app/data`) and grades **voxelwise** over the brain mask, one parametrized test per (subject × map) panel — 24 panels total. Reward is **binary** (the run passes only when **all** panels pass). A computable map passes when ≥90% of brain voxels agree within a per-map tolerance (rCBV rtol 10%/atol 0.05; vessel_radius rtol 12%/atol 0.3 µm; Q rtol 10%/atol 0.05), where a voxel agrees if reference and submission are **both** NaN (undeterminable) or **both** finite and within tolerance; an unsupported map (vessel_radius/Q for a GE-only subject) passes only when the submission **omits** it.

**Grading-invariance proof (the key check).** A fully independent from-scratch implementation (median baseline, scipy leakage regression with a rectangular cumulative integral, a time-invariant robust peak/ratio estimator; **no** import of the reference) reproduces every computable panel to well within tolerance (median voxel error 0.5%/2.7%/1.5% for rCBV/radius/Q). The plausible-but-wrong pipelines each fail only their own axis: **no leakage correction** biases rCBV and the vessel maps only on the leaky subjects; **whole-curve integration** biases rCBV on every subject; **no parenchyma NaN** or **vessel maps for GE-only subjects** fails the NaN / omit rules; a **fixed AIF** biases only the radius on the off-reference subjects. A naive uniform pipeline with all flaws fails every panel.

### Difficulty — measured on the frontier gate

Oracle **reward 1.0**, in-container (deterministic; oracle == verifier).

| agent | runs | reward | what it did |
|---|---|---|---|
| **gpt-5.6-sol (codex, xhigh)** | **k=1** | **0.0** | Solved **16/24 panels**; the failures fall on the task's hard axes — the unannounced Boxerman–Weisskoff leakage correction on the leaky subjects, the first-pass-only rCBV integral, the parenchyma NaN masking and GE-only omit rule, and the per-subject AIF-peak radius calibration. |
| **2nd frontier family (Claude/Gemini)** | _k≥3_ | _pending_ | _to be run by the maintainer at gate calibration_ |

**Failure mode (measured for gpt-5.6-sol; hypothesis for the 2nd family):** the model converts the DSC signals and computes vessel maps but does not detect-and-remove the unannounced contrast leakage, restrict rCBV to the first pass, or thread the NaN/omit and per-subject AIF rules, so the residual failures land on the genuine hard axes rather than a format bug.

### Notes / honesty

- **Reconstruction paradigm.** The difficulty is executional (get many coupled quantitative decisions right with no recipe). `instruction.md` names the deliverable and the physics conventions but never enumerates the pitfalls (the leakage region, the first-pass window, the NaN/omit forks) — the agent must discover them from the data.
- **Data.** Synthetic, small, deterministic, and **leakage-clean** — no benchmark leakage (the held-out reference and planted maps are never under `/app/data`; distinct from the modelled contrast-agent leakage the task asks the agent to correct). Regenerable via `synth_build/generate_fixtures.py`.
- **allow_internet=false.** The task is self-contained (dependencies baked in the image; no network at run or verify time).
