## MTV-002

**Proposal Title:** Macromolecular tissue volume (MTV) and water content from a heterogeneous proton-density-mapping cohort — an execution-hard reconstruction task (omit-fork recipe divergence + coupled PD assembly + hidden robustness)

**Scientific Domain:** Life Sciences · **Field:** Neuroscience · **Subfield:** Quantitative MRI / relaxometry

**Source paper:** Mezer et al. 2013, *Nat. Med.* (macromolecular tissue volume / MTV mapping, https://doi.org/10.1038/nm.3390); Volz et al. 2012, *NeuroImage* (quantitative proton-density / water-content mapping). Dataset: a **synthetic** proton-density-mapping cohort, generated deterministically at `synth_build/generate_fixtures.py`; planted ground-truth maps held out under `synth_build/fixture_spec.json`.

**Status: FULL runnable Harbor task.** This is a **reconstruction** task, *not* a recognition / "spot-the-confound" task — the instruction names the deliverable (produce the per-voxel WF_rel, R2star, MTV maps); the difficulty is *execution*, not an un-cued judgement. It follows the shape of the maintainer's reconstruction tasks (e.g. `pcasl-cbf-quantifier`): the agent implements the water-content inversion **from scratch** (no fitter bundled), over a **heterogeneous cohort where subjects need fundamentally different computations**, with a **hidden robustness** requirement, graded voxelwise against a **held-out reference** on **convention-invariant** physical quantities.

### Why this is hard (the four difficulty drivers)

1. **Recipe divergence** — subjects need *different code paths*, discoverable only from each sidecar and tissue map. MTV = 1 − PD/PD_water is absolute and needs a CSF ROI to anchor pure water — three of eight subjects have a parenchyma-only field of view with **no** CSF voxels, where the absolute normalisation cannot be pinned and MTV must be **omitted** (only the WM-referenced relative water fraction is reported), exactly like a water-reference-absent absolute concentration; and R2* is determinable only for the six multi-echo subjects (the two single-echo subjects must **omit** it). Forcing MTV without CSF, or R2* on a single echo, fails the omit rule.
2. **Coupled-physics assembly** — S0 is the TE=0 intercept of a log-linear fit whose slope is R2*; the receive-corrected proton density PD = S0/rx feeds **both** the WM-median relative water fraction and the CSF-anchored absolute MTV, so an error in the fit, the receive division, or the reference compounds through every downstream quantity.
3. **Hidden robustness** — spanning a **majority** and unannounced: a provided receive-sensitivity map must be divided out (strongly inhomogeneous on six of eight subjects); a majority of the multi-echo subjects (five of six) carry one or two grossly motion-corrupted echo volumes that must be rejected before the TE=0 fit; the pure-water reference must be estimated **robustly** (the high mode of the CSF proton density, because partial-volumed CSF drags a mean/median below pure water and biases MTV); and the first echo carries real T2* weighting, so using it in place of the extrapolated TE=0 intercept biases the ratios. None of these is announced in `instruction.md`.
4. **Convention-invariant grading** — the global gain G cancels in every quantity, and the pure-water (MTV) and WM-median (WF_rel) anchors are physical, so the graded values are convention-invariant; two independent correct implementations agree (proven below), so a from-scratch solver can pass while wrong pipelines fail.

### Verifier

`tests/test_outputs.py` recomputes every quantity from the bundled signals with a **held-out reference** pipeline (`mtv_pipeline` + `mtv_ref`, shipped only under `tests/` + `solution/`, never under `/app/data`) and grades **voxelwise** over the brain mask, one parametrized test per (subject × map) panel (24 panels = 8 × {WF_rel, R2star, MTV}). A computable map passes when ≥90% of brain voxels agree within a per-map tolerance (WF_rel rtol 6%/atol 0.03; R2star rtol 10%/atol 2; MTV rtol 8%/atol 0.03); an unsupported map (R2* for a single-echo subject, MTV where there is no CSF ROI) passes only when the submission **omits** it. Reward is binary (all 24 panels must pass → 1.0).

**Grading-invariance proof (the key check).** A fully independent implementation (Tukey-biweight IRLS TE=0 fit with a scipy backend, a histogram-mode pure-water reference, independent receive/normalisation handling — sharing **no** code with the reference) reproduces every computable panel to well within tolerance (worst-case median absolute difference 0.0002 for WF_rel, 0.011 for R2*, 0.0009 for MTV), so the tolerances are not method-dependent. The plausible-but-wrong pipelines (ignore the receive map, use the first echo, no echo rejection, CSF-mean reference, force MTV without CSF, force R2* on a single echo) each fail only the panels on their own axis, and the naive uniform pipeline scores 3/24 — so partial correctness is monotone.

### Difficulty — measured on the frontier gate

Oracle **reward 1.0**, in-container (deterministic; oracle == verifier).

| agent | runs | reward | what it did |
|---|---|---|---|
| **gpt-5.6-sol (codex, xhigh)** | **k=1** | **0.0** | Solved **15/24 panels**, failing the CSF-anchor MTV omit fork and single-echo R2* omit, the coupled TE=0-fit → receive-division → reference chain, and the unannounced receive-correction / echo-rejection / robust pure-water-reference axes the task is built around. |
| **2nd frontier family (Claude/Gemini)** | _k≥3_ | _pending_ | _to be run by the maintainer at gate calibration_ |

**Failure mode (measured for gpt-5.6-sol; hypothesis for the 2nd family):** the model implements a single clean PD pipeline and applies it uniformly — solving the standard panels but missing the per-subject omit forks (MTV needs a CSF anchor; R2* needs multiple echoes) and the unannounced hidden-robustness axes (receive division, echo rejection, robust high-mode pure-water reference, TE=0 vs first echo). The nine failed panels are the ones gated on those hard axes; the k=1 gate reports the count (15/24), and a per-panel itemization will come from the maintainer's calibration run.

### Notes / honesty

- **Reconstruction paradigm.** The difficulty is executional (get many coupled quantitative decisions right with no fitter), unlike the recognition-tier "un-cued judgement" tasks in this repo. `instruction.md` names the deliverable and the physics conventions but never enumerates the pitfalls (the CSF omit fork, the receive map, the corrupted echoes, the robust pure-water reference) — the agent must discover them from the data.
- **Data.** Synthetic, small, deterministic, and **leakage-clean** (the held-out reference and planted maps are never under `/app/data`). Regenerable via `synth_build/generate_fixtures.py`.
- **allow_internet=false.** The task is self-contained (dependencies baked in the image; no network at run or verify time).
