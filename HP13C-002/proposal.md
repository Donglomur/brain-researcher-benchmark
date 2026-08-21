## HP13C-002

**Proposal Title:** Kinetic mapping of a heterogeneous hyperpolarized 13C-pyruvate dynamic cohort — an execution-hard reconstruction task (model/inflow recipe divergence + coupled kinetic assembly + hidden robustness)

**Scientific Domain:** Life Sciences · **Field:** Neuroscience · **Subfield:** Hyperpolarized 13C metabolic imaging

**Source paper:** Zierhut et al. 2010, *J. Magn. Reson.* (kinetic modeling of hyperpolarized 13C1-pyruvate metabolism, https://doi.org/10.1016/j.jmr.2009.11.010); Larson et al. 2018, *Magn. Reson. Med.* (kinetic-modeling methods for hyperpolarized 13C). Dataset: a **synthetic** dynamic hyperpolarized 13C-pyruvate cohort, generated deterministically at `synth_build/generate_fixtures.py`; planted ground-truth rate maps held out under `synth_build/fixture_spec.json`.

**Status: FULL runnable Harbor task.** This is a **reconstruction** task, *not* a recognition / "spot-the-confound" task — the instruction names the deliverable (produce the per-voxel kPL and kPB conversion-rate maps); the difficulty is *execution*, not an un-cued judgement. It follows the shape of the maintainer's reconstruction tasks (e.g. `pcasl-cbf-quantifier`): the agent implements the kinetic estimator **from scratch** (no fitter bundled), over a **heterogeneous cohort where subjects need fundamentally different computations**, with a **hidden robustness** requirement, graded voxelwise against a **held-out reference** on **convention-invariant** rate quantities.

### Why this is hard (the four difficulty drivers)

1. **Recipe divergence** — subjects need *different code paths*, discoverable only from each sidecar. Some resolve a bicarbonate channel and require the **three-site** model (fit kPL **and** kPB) while others acquire only pyruvate+lactate and require the **two-site** model (kPB not determinable → must be **omitted**; and fitting two-site to three-site data also biases kPL because the →HCO3 loss is mis-attributed). Independently, some subjects were imaged during a continuous infusion (a vascular input function is provided and the forward model must be **driven** by it) while others received a compact bolus (a closed system decaying from the initial pyruvate) — using the wrong inflow model biases kPL by 40–50%.
2. **Coupled-physics assembly** — the discrete matrix-exponential propagation of the longitudinal magnetization, the per-frame RF flip depletion, the piecewise inflow term, the fixed per-subject T1 relaxation, and the profiled-amplitude least-squares rate solve must **all** be assembled correctly; an error in any one compounds. Per-subject T1 constants and per-frame flip-angle schedules (constant or ramped) must be threaded into the discrete model.
3. **Hidden robustness** — a **majority** of subjects carry one or two grossly corrupted dynamic frames (an RF-spike or signal-dropout timepoint) that must be detected and rejected before the fit, while every subject's late frames are low-SNR as the hyperpolarization decays. This is never announced in `instruction.md`.
4. **Convention-invariant grading** — kPL and kPB (1/s) are uniquely determined given the pinned discrete kinetic model with the common signal amplitude profiled out; two independent correct implementations compute them identically (proven below), so a from-scratch solver can pass while wrong pipelines fail — and the model-free AUC-ratio shortcut is a different, biased quantity everywhere.

### Verifier

`tests/test_outputs.py` recomputes every map from the bundled signals with a **held-out reference** pipeline (`hp13c_pipeline` + `hp13c_ref`, shipped only under `tests/` + `solution/`, never under `/app/data`) and grades **voxelwise** over the brain mask, one parametrized test per (subject × map) panel (16 panels). A computable map passes when ≥90% of brain voxels agree within a per-map tolerance (kPL rtol 6%/atol 0.0015; kPB rtol 6%/atol 0.001); an unsupported map (kPB for a two-site subject) passes only when the submission **omits** it. Reward is binary (pytest rc → 1.0 iff every panel passes).

**Grading-invariance proof (the key check).** A fully independent implementation (a hand-rolled fixed-step RK4 forward integrator instead of the matrix exponential; a vectorised grid + zoom optimiser instead of a scipy polish; a different gross-frame detector; **no** import of the reference) reproduces every computable panel to well within tolerance (p95 ≤ 1.3%, max ≤ 1.7% relative). The plausible-but-wrong pipelines (ignore the inflow, two-site for all, three-site for all, single global T1, no frame rejection, AUC-ratio shortcut) each fail only the panels on their own axis, and a naive uniform pipeline fails a majority (10 of 16) — so partial credit is monotone in correctness.

### Difficulty — measured on the frontier gate

Oracle **reward 1.0**, in-container (deterministic; oracle == verifier).

| agent | runs | reward | what it did |
|---|---|---|---|
| **gpt-5.6-sol (codex, xhigh)** | **k=1** | **0.0** | Solved **9/16 panels**, failing the two-vs-three-site omit fork, the infusion-vs-bolus inflow fork, the per-subject T1/flip threading, and the unannounced corrupted-frame-rejection axes the task is built around. |
| **2nd frontier family (Claude/Gemini)** | _k≥3_ | _pending_ | _to be run by the maintainer at gate calibration_ |

**Failure mode (measured for gpt-5.6-sol; hypothesis for the 2nd family):** the model implements a single clean kinetic pipeline and applies it uniformly — solving the standard panels but missing the per-subject model fork (kPB only where bicarbonate is resolved), the inflow fork (VIF-driven vs closed bolus), and the discover-and-reject of the unannounced corrupted frames. The seven failed panels are the ones gated on those hard axes; the k=1 gate reports the count (9/16), and a per-panel itemization will come from the maintainer's calibration run.

### Notes / honesty

- **Reconstruction paradigm.** The difficulty is executional (assemble a coupled discrete kinetic model and get the per-subject decisions right with no fitter), unlike the recognition-tier "un-cued judgement" tasks in this repo. `instruction.md` names the deliverable and the kinetic conventions but never enumerates the pitfalls (the model/inflow forks, the per-subject T1, the corrupted frames) — the agent must discover them from the data.
- **Data.** Synthetic, small, deterministic, and **leakage-clean** (the held-out reference and planted parameters are never under `/app/data`). Regenerable via `synth_build/generate_fixtures.py`.
- **allow_internet=false.** The task is self-contained (dependencies baked in the image; no network at run or verify time).
