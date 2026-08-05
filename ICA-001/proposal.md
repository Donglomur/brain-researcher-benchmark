## ICA-001

**Proposal Title:** Resting-state networks from ICA — an un-cued model-order / run-reproducibility failure (the *over-claim / robustness* axis)

**Scientific Domain:** Life Sciences · **Field:** Neuroscience · **Subfield:** Resting-state fMRI / independent component analysis

**Source finding:** Beckmann et al. (2005); Smith et al. (2009), *PNAS*, https://doi.org/10.1073/pnas.0905267106 — ICA of resting-state fMRI recovers a set of reproducible resting-state networks (RSNs). Reliability critique: Himberg et al. (2004), *NeuroImage* (ICASSO — ICA components must be tested for stability). Data: `nilearn.datasets.fetch_abide_pcp` (cpac, rois_dosenbach160).

**Status: FULL runnable task, built with `tb-science-task-authoring`.** Failure axis **over-claim / robustness** (differentiated instance — a **distinct method**, ICA decomposition, with the *model-order* lever, separate from MODULAR's graph community resolution, VBMAGE's smoothing, DYNFC's stationarity), topic *independent component analysis*, ABIDE.

**Difficulty vs frontier agents: NOT YET MEASURED** (gate deferred).

### Why this exists
ICA "resting-state networks" are among the most-reported resting-state results, but the number and identity of components are governed by the arbitrary model order and a stochastic algorithm. The un-cued judgement is to test component stability (ICASSO), not report a single decomposition.

### The reproduction (Step-0 validated) — ICA recovers components
ABIDE, Dosenbach-160, n≈40, group FastICA: at a common model order (20) the data decompose into recognisable components / networks — the standard RSN picture (Beckmann 2005, Smith 2009).

### The trap (Step-0 validated) — the components are model-order-dependent and run-unstable
Run-to-run reproducibility (mean matched |r| across 6 FastICA runs) **collapses as the model order rises**:

| model order | run-to-run reproducibility |
|---|---|
| 10 | 0.99 |
| 20 | **0.82** |
| 30 | 0.64 |
| 40 | **0.54** |

At the higher orders used to resolve sub-networks the components are barely reproducible (0.54 at 40), and the model order that sets the number of "networks" is arbitrary — different orders give different decompositions, and repeated runs at the same order give different components. So "we found N resting-state networks" is an artifact of the model-order choice and the stochastic decomposition.

### Verifier (2 plain checks)
`tests/test_outputs.py`: (1) ICA components / networks were computed; (2) `findings.md` recognises the components are **not robust** — model-order-dependent and/or run-unstable — a flat "we found N networks" over-claims. Strong-token guard: the recognition must name the model-order / number-of-components / reproducibility concept (not merely "noisy"), linked to the components. Offline: oracle PASS; flat "20 networks" adversarial FAIL; vague "ICA can be noisy" adversarial FAIL.

### Honest caveats / open risks
1. **Difficulty UNTESTED** — needs the gate. **Telegraphing:** ICA stability (ICASSO) is known; a strong agent may volunteer it → possible easy control. Mitigated by posing a plain "decompose and report the components" analysis.
2. **Prose/judgement verifier** (rigor genre) — strong-token + linked-insight guards mitigate false positives; harden against real agent texts at calibration.
3. **Order-dependent trap** — reproducibility is high at low orders (0.99 at 10) and low at high orders (0.54 at 40); the trap is that the order is arbitrary AND typical/higher orders are unreliable. The oracle reports the full sweep, so this is stated honestly.
4. **ROI-space ICA** — run on the Dosenbach-160 ROI time series (not voxelwise) for a light, deterministic environment; the model-order / run instability is the same phenomenon voxelwise ICA shows (ICASSO).

### Cost
`hard`. cpus 2, mem 8 GB, internet on (ABIDE Dosenbach-160 ROI time series — small, reliable S3 host). Deps: nilearn 0.12.1 + scikit-learn/scipy/numpy/pandas/nibabel (no extra deps; FastICA from scikit-learn). Oracle runtime ~1-2 min (24 FastICA fits across the model-order sweep).
