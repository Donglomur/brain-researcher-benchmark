## MEGBEAM-002

**Proposal Title:** LCMV beamformer source reconstruction of a heterogeneous MEG cohort — an execution-hard reconstruction task (recipe divergence + coupled-physics assembly + hidden robustness)

**Scientific Domain:** Life Sciences · **Field:** Neuroscience · **Subfield:** MEG source reconstruction

**Source paper:** Van Veen, van Drongelen, Yuchtman & Suzuki 1997, *IEEE Trans. Biomed. Eng.* (LCMV beamforming / neural activity index, https://doi.org/10.1109/10.623056). Dataset: a **synthetic** MEG sensor-covariance cohort, generated deterministically at `synth_build/generate_fixtures.py`; planted ground-truth NAI maps held out under `synth_build/fixture_spec.json`.

**Status: FULL runnable Harbor task.** This is a **reconstruction** task, *not* a recognition / "spot-the-confound" task — the instruction names the deliverable (produce per-condition NAI maps); the difficulty is *execution*, not an un-cued judgement. It follows the shape of the maintainer's `pcasl-cbf-quantifier`: the agent implements the LCMV beamformer **from scratch** (no beamformer bundled, method not spelled out step-by-step), over a **heterogeneous 8-subject cohort where subjects need structurally different weight computations**, with a **hidden robustness** requirement, graded per-source against a **held-out reference** on a **convention-invariant** physical quantity.

### Why this is hard (the four difficulty drivers)

1. **Recipe divergence** — subjects need *structurally different weight computations*, discoverable only from the data. A majority of subjects' sensor covariances are rank-reduced (SSS/ICA-cleaned: the data live in an r<n_chan subspace with a hard eigenvalue gap); those need the numerical rank detected and a **truncated Moore–Penrose inverse**, whereas a plain `np.linalg.inv` — or `np.linalg.pinv` at its default rcond, which keeps the near-null directions — blows up and produces garbage NAI only on those subjects. Only some subjects acquired a second condition (B); its NAI is not computable elsewhere and must be **omitted**.
2. **Coupled-physics assembly** — a per-source neural activity index couples several steps that must **all** be assembled correctly: robustly averaging the epoch covariances, inverting on the numerical rank, contracting `L^T C^+ L` against the leadfield, and normalizing by the **provided** colored empty-room noise covariance via `L^T C^+ N C^+ L`. Normalizing by the identity instead of the provided noise covariance biases every panel.
3. **Hidden robustness** — unannounced: a majority of subjects carry one or two grossly corrupted (broadband, high-amplitude) epoch covariances that must be **rejected** before averaging, and two subjects carry a grossly gain-corrupted sensor that must be **detected and dropped** from the covariance, noise, and leadfield.
4. **Convention-invariant grading** — NAI is leadfield scale/sign invariant and uniquely determined once the gross artifacts and numerical rank are fixed, so two independent correct implementations compute it identically (proven below).

### Verifier

`tests/test_outputs.py` recomputes every NAI map from the bundled epoch covariances with a **held-out reference** pipeline (`beam_pipeline` + `beam_ref`, shipped only under `tests/`+`solution/`, never under `/app/data`) and grades **per-source** over the grid, one parametrized test per (subject × condition) panel — 16 panels total. Reward is **fractional** (fraction of panels correct). A computable map passes when ≥90% of source grid points agree within (rtol 5%, atol 0.06); an unsupported map (condition B not acquired) passes only when the submission **omits** it.

**Grading-invariance proof (the key check).** A fully independent from-scratch implementation (gap-based bad-channel detection, batch sigma-clip epoch rejection on the Frobenius norm, an SVD gap-rank pseudo-inverse, and the long-form unit-gain NAI contraction; **no** import of the reference) reproduces every computable panel to ~1e-7 relative — far inside tolerance. The plausible-but-wrong pipelines each fail only their axis: a **plain inverse** fails the rank-reduced subjects (7 panels), **averaging every epoch** fails the artifact subjects (6 panels), **keeping the bad sensor** fails the bad-channel subjects (3 panels), **identity-noise normalization** fails broadly (11 panels), and **fabricating condition B** fails the omit panels (5); a single naive recipe fails 10 of 16 panels.

### Difficulty — measured on the frontier gate

Oracle **reward 1.0**, in-container (deterministic; oracle == verifier).

| agent | runs | reward | what it did |
|---|---|---|---|
| **gpt-5.6-sol (codex, xhigh)** | **k=1** | **0.0** | Solved **9/16 panels**; the failures fall on the task's hard axes — the numerical-rank truncated pseudo-inverse on the rank-reduced subjects, the unannounced corrupted-epoch and bad-sensor rejection, the provided-noise-covariance normalization, and the condition-B omit rule. |
| **2nd frontier family (Claude/Gemini)** | _k≥3_ | _pending_ | _to be run by the maintainer at gate calibration_ |

**Failure mode (measured for gpt-5.6-sol; hypothesis for the 2nd family):** the model implements a clean LCMV beamformer but does not detect the numerical rank for a truncated inverse on the rank-reduced subjects, nor discover-and-reject the unannounced corrupted epochs and gain-corrupted sensor, so the residual failures land on the genuine hard axes rather than a format bug.

### Notes / honesty

- **Reconstruction paradigm.** The difficulty is executional (assemble a coupled beamformer with no recipe). `instruction.md` names the deliverable and the NAI/rank conventions but never enumerates the pitfalls (which subjects are rank-reduced, the corrupted epochs, the bad sensor) — the agent must discover them from the data.
- **Data.** Synthetic, small, deterministic, and **leakage-clean** (the held-out reference and planted maps are never under `/app/data`). Regenerable via `synth_build/generate_fixtures.py`.
- **allow_internet=false.** The task is self-contained (dependencies baked in the image; no network at run or verify time).
