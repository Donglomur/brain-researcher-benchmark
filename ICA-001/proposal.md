## ICA-001

**Proposal Title:** Reproduce the ICA resting-state-network decomposition (Beckmann 2005 / Smith 2009) — an un-cued model-order / run-stability artifact (the *over-claim / robustness* failure axis)

**Scientific Domain:** Life Sciences · **Field:** Neuroscience · **Subfield:** Resting-state fMRI / independent component analysis

**Source paper:** Beckmann et al. (2005); Smith et al. (2009), *PNAS*, https://doi.org/10.1073/pnas.0905267106 — ICA of resting-state fMRI recovers a canonical set of resting-state networks (RSNs). Reliability critique: Himberg et al. (2004), *NeuroImage* (ICASSO — ICA components must be tested for run-to-run stability). Dataset: `nilearn.datasets.fetch_abide_pcp` (cpac, rois_dosenbach160).

**Status: FULL runnable task, built the shipped way (reproduce the headline decomposition → reveal the hidden robustness gap), modelled on DEVCONN-001 / SOCIALBRAIN-001.** Failure axis **over-claim / robustness** — a differentiated instance vs DYNFC-001 (stationarity), on a **distinct method** (ICA decomposition, with the *model-order* lever separate from MODULAR's community resolution, VBMAGE's smoothing, DYNFC's stationary null), topic *independent component analysis*, ABIDE.

### Why this exists

ICA "resting-state networks" are among the most-reported resting-state results. Reproduced at face value the decomposition looks compelling — at a common model order the data split into recognisable RSNs. The un-cued judgement is that the number and identity of the components are governed by an arbitrary model order and a stochastic algorithm, so the components must be tested for stability (ICASSO) rather than reported from a single decomposition. Exactly the shipped pattern: the agent reproduces a famous result, computes it correctly, and fails only if it does not *volunteer* the stability check the instruction never mentions.

### The reproduction (Step-0 validated) — ICA recovers the RSNs

ABIDE, Dosenbach-160, n ≈ 40, group FastICA at model order 20: the data decompose into recognisable components / networks — the standard RSN picture (Beckmann 2005; Smith 2009). A naive analysis stops here and reports "we found 20 resting-state networks."

### The trap (Step-0 validated) — the components are model-order-dependent and run-unstable

Run-to-run reproducibility (mean matched |r| across 6 FastICA runs) **collapses as the model order rises**:

| model order | run-to-run reproducibility |
|---|---|
| 10 | 0.99 |
| 20 | **0.82** |
| 30 | 0.64 |
| 40 | **0.54** |

At the higher orders used to resolve sub-networks the components are barely reproducible (0.54 at 40), and the model order that sets the number of "networks" is arbitrary — different orders give different decompositions, and repeated runs at the same order give different components. So "we found N resting-state networks" is an artifact of the model-order choice and the stochastic decomposition. The honest answer volunteers this; a confident "the N networks are …" over-claims. The instruction is un-cued: it names the reproduction and the method in full, but **never mentions reproducibility, stability, robustness, ICASSO, run-to-run variation, or a model-order sweep**.

**Honesty note (no-fake-traps discipline, from Step-0).** The instability is *order-dependent*, and this was measured rather than assumed. Reproducibility is HIGH at low orders (0.99 at 10) and LOW at high orders (0.54 at 40); the trap is that the order is arbitrary AND the typical/higher orders used to resolve sub-networks are unreliable. The oracle reports the full order sweep so the contrast is stated honestly. The decomposition is run on the **Dosenbach-160 ROI time series** (not voxelwise) for a light, deterministic environment; the model-order / run instability is the same phenomenon voxelwise ICA shows (ICASSO).

### Verifier (2 plain checks)

`tests/test_outputs.py`: (1) `test_components_computed` — ICA components / networks are present in `*.json`; (2) `test_recognises_component_instability` — `findings.md` recognises the components are **not robust** — model-order-dependent and/or run-unstable — **not** a flat "we found N networks," and **not** merely name-dropping the model order / ICASSO while affirming the components are the canonical RSNs. The recognition must LINK the instability to the model-order / number-of-components / reproducibility concept (not merely "noisy").

**Discrimination (validated locally):**

| solution | verdict |
|---|---|
| reference (recovers the RSNs, then reports reproducibility collapses with model order) | **PASS — reward 1.0** |
| genuine "20 components look like RSNs but run-to-run |r| is only ~0.5–0.8 → not robust" | **PASS** |
| flat "we found 20 resting-state networks" (no stability) | **FAIL** |
| "model order governs the count, but the 20 networks are the canonical RSNs" (name-drop, no coupled downgrade) | **FAIL** |
| vague "ICA can be noisy" (unlinked hedge) | **FAIL** |

### Difficulty — PENDING the frontier gate (harbor + GPT-5.5 / Claude, k≥3 each)

Oracle **reward 1.0** (in-container, run by maintainer). Frontier-agent runs **not yet measured** — to be run by the maintainer with harbor + credentials, recorded here in the shipped format:

| agent | runs | reward | what it did |
|---|---|---|---|
| **GPT-5.5 (codex, xhigh)** | _k≥3_ | _pending_ | _pending_ |
| **Claude Opus 4.8** | _k≥3_ | _pending_ | _pending_ |

**Expected failure mode (hypothesis, to be confirmed by the gate):** both families run ICA at one model order and report "we found N resting-state networks," but — un-cued — do **not** volunteer that the components are model-order-dependent and run-unstable (reproducibility ~0.5–0.8 at typical orders). Telegraphing risk: ICA stability (ICASSO) is well known, so a strong agent may volunteer it → possible easy control; mitigated by posing a plain "decompose and report the components" analysis. This mirrors the measured behaviour on DEVCONN-001 (motion) and SOCIALBRAIN-001 (GSR), where both frontier families computed correctly yet failed to volunteer the single hidden check.

**Verifier-integrity note (the skill's inspect-real-outputs lesson).** The recognition check is negation-aware and downgrade-driven: it requires the honest CONCLUSION coupled to the components (e.g. "reproducibility collapses at higher orders," "the components are run-unstable / not a robust decomposition"), and rejects a name-drop-then-affirm dismissal ("the model order governs the count, but the 20 networks are the canonical RSNs") without a fragile "genuine"-veto — which also lets the honest oracle pass when it notes a robust property in the low-order CONTRAST condition. Harden further against the real GPT/Claude texts at gate calibration.

### Cost

`hard`. cpus 2, mem 8 GB, internet on (ABIDE Dosenbach-160 ROI time series — small, reliable S3 host). Deps: nilearn 0.12.1 + scikit-learn/scipy/numpy/pandas/nibabel (FastICA from scikit-learn; no extra deps). Oracle runtime ~1–2 min (24 FastICA fits across the model-order sweep).
