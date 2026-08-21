## DICS-002

**Proposal Title:** DICS source-power imaging of a heterogeneous MEG cohort — an execution-hard reconstruction task (recipe divergence + coupled-physics assembly + hidden robustness)

**Scientific Domain:** Life Sciences · **Field:** Neuroscience · **Subfield:** MEG source imaging

**Source paper:** Gross et al. 2001, *PNAS* (Dynamic Imaging of Coherent Sources / DICS, https://doi.org/10.1073/pnas.98.2.694); Van Veen et al. 1997, *IEEE TBME* (LCMV beamformer / Neural Activity Index, https://doi.org/10.1109/10.623056). Dataset: a **synthetic** MEG frequency-domain cohort (8 subjects, sensor Fourier coefficients + forward leadfields), generated deterministically at `synth_build/generate_fixtures.py`; planted ground truth held out under `synth_build/fixture_spec.json`.

**Status: FULL runnable Harbor task.** This is a **reconstruction** task, *not* a recognition / "spot-the-confound" task — the instruction names the deliverable (produce the per-source relative power image `Prel`, and the Neural Activity Index `NAI` where an empty-room recording exists); the difficulty is *execution*, not an un-cued judgement. It follows the shape of the maintainer's `pcasl-cbf-quantifier`: the agent implements the DICS beamformer **from scratch** (no beamformer library bundled), over a **heterogeneous cohort where subjects need fundamentally different spatial filters**, with a **hidden robustness** burden, graded per-source against a **held-out reference** on a **convention-invariant** quantity.

### Why this is hard (the four difficulty drivers)

1. **Recipe divergence** — the regularised CSD inverse forks on rank, discoverable only from each sidecar and the data: full-rank (raw) subjects take the ordinary loaded inverse, but a *majority* are rank-deficient because an interference-suppression step (SSS/ICA cleaning) projected the sensor data onto a lower-dimensional subspace, so the inverse must be **truncated** to the sidecar's `data_rank` or the near-null directions leak into the filter and corrupt the power. A uniform `(C+λI)⁻¹` recipe is right on the full-rank subjects and wrong on the rank-deficient majority. The `NAI` further forks on an empty-room noise CSD that is present for some subjects and **absent** for the rest, where it must be omitted (like a water-reference-absent absolute concentration).
2. **Coupled-physics assembly** — the complex-Hermitian linear algebra is heavily coupled: the mean outer-product CSD, the eigen-truncated diagonally-loaded inverse `Ci = Σ_{k≤R} u_k u_kᴴ/(σ_k+λ)`, the unit-gain vector filter `W = inv(Lᴴ Ci L) Lᴴ Ci`, and the trace power reduction must **all** be assembled correctly; an error in any one compounds across the (subject × image) panels.
3. **Hidden robustness** — an un-cued burden spanning a *majority* of the cohort: grossly bad sensors (dead/railing channels whose band power is orders of magnitude off) corrupt the CSD and must be detected and dropped from **both** the CSD and the leadfield, and grossly corrupted epochs (blink/movement bursts) must be rejected before the epochs are averaged into the CSD. None of this is announced.
4. **Convention-invariant grading** — `Prel` is median-normalised (the CSD and leadfield scale cancel) and `NAI` is a same-filter power ratio (the filter normalisation cancels), and the eigen-truncated loaded inverse depends only on eigen-**projectors** (invariant to eigenvector phase/sign), so two independent correct implementations compute them identically — no reporting-convention ambiguity.

### Verifier

`tests/test_outputs.py` recomputes every image from the bundled Fourier coefficients + leadfield with a **held-out reference** pipeline (`dics_pipeline` + `dics_ref`, shipped only under `tests/`+`solution/`, never under `/app/data`) and grades **per-source** over the whole grid. Each of the 16 (subject × image) panels is its own parametrized test; reward is 1 only when every panel is correct. A computable image passes when ≥90% of grid sources agree within a per-image tolerance (`Prel` and `NAI` rtol 5% / atol 0.05); an unsupported image (`NAI` with no empty-room noise recording) passes only when the submission **omits** it.

**Grading-invariance proof (the key check).** A genuinely-correct independent implementation (einsum CSD, log-ratio bad-channel and log-z artifact detection, scipy eigen-truncation, pseudo-inverse filter; **no** shared code with the reference) reproduces every computable panel to a max relative error ~6e-8. The plausible-but-wrong pipelines each fail only their own axis: **keep bad channels** fails only the bad-channel subjects; **keep artifact epochs** fails only the artifact subjects; **no rank truncation** fails only the rank-deficient subjects; **force NAI** fails only the no-noise subjects — and a naive uniform pipeline fails 13 of the 16 panels.

### Difficulty — measured on the frontier gate

Oracle **reward 1.0**, in-container (deterministic; oracle == verifier).

| agent | runs | reward | what it did |
|---|---|---|---|
| **gpt-5.6-sol (codex, xhigh)** | **k=3** | **0.0 (all 3)** | Solved only **3/16 panels**, failing on every genuine hard axis — the rank-truncated inverse on the rank-deficient majority, the bad-channel and artifact-epoch rejection, and the `NAI` omit rule — a clean, reproducible multi-axis execution failure confirmed across k=3 trials. |
| **2nd frontier family (Claude/Gemini)** | _k≥3_ | _pending_ | _to be run by the maintainer at gate calibration_ |

**Failure mode (measured for gpt-5.6-sol; hypothesis for the 2nd family):** the model implements one uniform loaded-inverse DICS pipeline and applies it everywhere — it never threads the per-subject rank truncation, never discovers-and-drops the bad channels / artifact epochs, and does not correctly honour the `NAI` omit fork. The 0.0 is earned on the genuine hard axes, not a format bug.

### Notes / honesty

- **Reconstruction paradigm.** The difficulty is executional (assemble the coupled complex-Hermitian beamformer correctly and adapt it per subject, with no bundled library), unlike the recognition-tier "un-cued judgement" tasks in this repo. `instruction.md` names the deliverable and pins the physics but never enumerates the pitfalls (the rank fork, the bad-channel / artifact rejection, the `NAI` omit) — the agent must discover them from the data.
- **Data.** Synthetic, small, deterministic, and **leakage-clean** (the held-out reference and planted parameters are never under `/app/data`). Regenerable via `synth_build/generate_fixtures.py`.
- **allow_internet=false.** The task is self-contained (dependencies baked in the image; no network at run or verify time).
