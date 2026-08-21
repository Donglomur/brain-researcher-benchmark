## R1RHODISP-002

**Proposal Title:** Quantitative T1rho dispersion of a heterogeneous spin-lock cohort — an execution-hard reconstruction task (recipe divergence + coupled-physics assembly + hidden robustness)

**Scientific Domain:** Life Sciences · **Field:** Neuroscience · **Subfield:** Quantitative MRI / relaxometry

**Source paper:** Cobb, Xie & Gore 2011, *MRM* (Contributions of chemical exchange to T1ρ dispersion in a tissue model, https://doi.org/10.1002/mrm.22833); Chopra, McClung & Jordan 1984, *JMR* (chemical-exchange spin-lock dispersion model). Dataset: a **synthetic** T1rho spin-lock cohort (8 subjects, differing spin-lock-frequency sampling), generated deterministically at `synth_build/generate_fixtures.py`; planted ground-truth maps held out under `synth_build/fixture_spec.json`.

**Status: FULL runnable Harbor task.** This is a **reconstruction** task, *not* a recognition / "spot-the-confound" task — the instruction names the deliverable (produce `R1rho_ref` always, and the dispersion asymptotes `R1rho_inf` / `Rex_amp` where determinable); the difficulty is *execution*, not an un-cued judgement. It follows the shape of the maintainer's `pcasl-cbf-quantifier`: the agent implements the two-stage T1rho-dispersion inversion **from scratch** (no fitter bundled), over a **heterogeneous cohort where subjects need fundamentally different computations**, with a **hidden robustness** requirement, graded voxelwise against a **held-out reference** on a **convention-invariant** quantity.

### Why this is hard (the four difficulty drivers)

1. **Recipe divergence** — the spin-lock-frequency (FSL) *sampling* forks the recipe, discoverable only from each sidecar: most subjects sample 5–7 distinct FSL and their chemical-exchange dispersion is determinable (report `R1rho_inf` and `Rex_amp`), but a minority sample only one or two frequencies, where the dispersion is under-determined and both must be **omitted** (like a water-reference-absent absolute concentration); every subject samples a common reference frequency, so `R1rho` at that FSL is always reported.
2. **Coupled-physics assembly** — two stages must both be assembled correctly: stage one is a per-block mono-exponential fit of the spin-lock decay `S(TSL) = S0·exp(−R1rho·TSL)` (TSL in seconds → rate in 1/s) at every FSL; stage two fits the Lorentzian dispersion `R1rho(ω1) = R1rho_inf + Rex/(1+(ω1·τ)²)` with `ω1 = 2π·FSL`, reporting the exchange-independent floor and the dispersion amplitude. A straight-line dispersion model gets the amplitude wrong on every dispersion subject.
3. **Hidden robustness** — two unannounced axes span a *majority* of the cohort: (1) a gross motion spike corrupts one TSL image inside a spin-lock block on six of eight subjects (mostly the reference block) and must be rejected before the mono-exponential fit, else `R1rho_ref` is biased; (2) a B1/B0 incomplete-spin-lock artifact grossly biases the whole-block `R1rho` of one interior FSL on four of six dispersion subjects — a **high-leverage** outlier a flexible 3-parameter Lorentzian would otherwise absorb into an inflated amplitude — so it must be found by a drop-one best-subset / robust search (a naive residual drop is fooled by leverage) and rejected before the dispersion fit.
4. **Convention-invariant grading** — `R1rho_ref`, `R1rho_inf`, and `Rex_amp` are convention-invariant asymptotes (the correlation time τ is not graded); a genuinely different parameterisation (a characteristic frequency in Hz rather than a correlation time) reproduces them, so two independent correct implementations agree.

### Verifier

`tests/test_outputs.py` recomputes every map from the bundled spin-lock signals with a **held-out reference** pipeline (`r1rho_pipeline` + `r1rho_ref`, shipped only under `tests/`+`solution/`, never under `/app/data`) and grades **voxelwise** over the parenchyma (GM+WM). Reward is fractional over 24 (subject × map) panels. A computable map passes when ≥90% of parenchyma voxels agree within a per-map tolerance (`R1rho_ref` rtol 6%/atol 0.5; `R1rho_inf` rtol 6%/atol 0.5; `Rex_amp` rtol 15%/atol 0.6); an unsupported map (`R1rho_inf`/`Rex_amp` for a subject with fewer than four distinct FSL) passes only when the submission **omits** it.

**Grading-invariance proof (the key check).** A genuinely-correct independent implementation (nonlinear `curve_fit` mono-exponential and Lorentzian, the dispersion parameterised by a characteristic frequency in Hz rather than a correlation time, a different robust rejection; **no** import of the reference) reproduces every computable panel to well within tolerance (median disagreement < 0.4% for the rates, < 3% for the amplitude). The plausible-but-wrong pipelines each fail only their own axis: **no motion-spike rejection** biases `R1rho_ref` only on the spiked subjects; **no banded-block rejection** biases `R1rho_inf`/`Rex_amp` only on the banded subjects; **no omit rule** fails the under-sampled subjects; **a straight-line dispersion** gets the amplitude wrong on every dispersion subject — a naive uniform pipeline fails 16/24.

### Difficulty — measured on the frontier gate

Oracle **reward 1.0**, in-container (deterministic; oracle == verifier).

| agent | runs | reward | what it did |
|---|---|---|---|
| **gpt-5.6-sol (codex, xhigh)** | **k=1** | **0.0** | Solved **10/24 panels**, failing the genuine hard axes — the unannounced motion-spike rejection (biasing `R1rho_ref`), the high-leverage banded-block rejection (biasing the dispersion asymptotes), the fewer-than-four-FSL omit rule, and the Lorentzian (not straight-line) dispersion. |
| **2nd frontier family (Claude/Gemini)** | _k≥3_ | _pending_ | _to be run by the maintainer at gate calibration_ |

**Failure mode (measured for gpt-5.6-sol; hypothesis for the 2nd family):** the model implements one clean two-stage fit and applies it uniformly — it does not discover-and-reject the unannounced motion spikes and high-leverage banded blocks, nor honour the dispersion omit fork. The 0.0 is earned on the genuine hard axes, not a format bug.

### Notes / honesty

- **Reconstruction paradigm.** The difficulty is executional (robust per-block mono-exponential fits, a leverage-aware dispersion fit, and the determinability omit — with no bundled fitter), unlike the recognition-tier "un-cued judgement" tasks in this repo. `instruction.md` names the deliverable and the models but never enumerates the pitfalls (the motion spikes, the banded blocks) beyond pinning the determinability rule — the agent must discover the robustness axes from the data.
- **Data.** Synthetic, small, deterministic, and **leakage-clean** (the held-out reference and planted parameters are never under `/app/data`). Regenerable via `synth_build/generate_fixtures.py`.
- **allow_internet=false.** The task is self-contained (dependencies baked in the image; no network at run or verify time).
