## RESTNETS-001

**Proposal Title:** Reproduce the ICA resting-state-network decomposition (Beckmann 2005 / Smith 2009) — an un-cued model-order / random-seed reproducibility artifact (the *over-claim / robustness* failure axis)

**Scientific Domain:** Life Sciences · **Field:** Neuroscience · **Subfield:** Resting-state fMRI / independent component analysis

**Source paper:** Beckmann et al. (2005); Smith et al. (2009), *PNAS*, https://doi.org/10.1073/pnas.0905267106 — ICA of resting-state fMRI recovers a canonical set of resting-state networks (RSNs). Reliability critique (the un-cued axis): Himberg et al. (2004), *NeuroImage* (ICASSO — ICA components must be tested for run-to-run stability). Dataset: ABIDE Dosenbach-160 ROI time series (via `nilearn.datasets.fetch_abide_pcp`, cpac), packaged offline.

**Status: FULL runnable task, built the shipped way (reproduce the headline decomposition → reveal the hidden robustness gap), modelled on DEVCONN-001 / SOCIALBRAIN-001 / TOPEDGES-001 (route-b offline).** Failure axis **over-claim / robustness** — a differentiated instance vs DYNCONN-001 (stationarity), on a **distinct method** (ICA decomposition, with the *model-order* and *random-seed* levers separate from MODULAR's community resolution, VBMAGE's smoothing, DYNFC's stationary null), topic *independent component analysis*, ABIDE.

### Why this exists

ICA "resting-state networks" are among the most-reported resting-state results. Reproduced at face value the decomposition looks compelling — at a common model order the data split into recognisable RSNs, and the oracle emits the actual component spatial maps (n_components × 160). The un-cued judgement is that the number and identity of the components are governed by an arbitrary model order and a stochastic algorithm, so the components must be tested for stability (ICASSO — across model order / random seeds / split-half) rather than reported from a single decomposition. Exactly the shipped pattern: the agent reproduces a famous result, computes it correctly, and fails only if it does not *volunteer* the reproducibility check the instruction never mentions.

### The reproduction and the trap (validated) — held privately

ABIDE control subjects, Dosenbach-160, group FastICA: at a common model order the data decompose into recognisable component maps — the standard RSN picture (Beckmann 2005; Smith 2009). A naive analysis stops here and reports "we found N resting-state networks." The trap (validated) is that the recovered components are **not reproducible across model order + random initialisation**: run-to-run reproducibility (mean best-matched |r| across FastICA seeds) collapses as the model order rises, and a split-half decomposition at the default order matches only modestly. So "we found N resting-state networks" is an artifact of the model-order choice and the stochastic decomposition. The validated numbers (per-order reproducibility, split-half, the oracle receipt) are in the **private, git-ignored `calibration.md`** (rule 4). The instruction is un-cued: it names the reproduction and the method in full (concatenate, z-score, FastICA at ~20), but **never mentions reproducibility, stability, robustness, ICASSO, run-to-run / across-seed variation, split-half, or a model-order sweep**.

**Honesty note (no-fake-traps discipline).** The instability is *order-dependent*, and this was measured rather than assumed. Reproducibility is high at low model orders and low at the higher orders used to resolve sub-networks; the trap is that the order is arbitrary AND the typical/higher orders are unreliable, and repeated runs at the same order (different seeds) and independent split-halves give different components. The oracle reports the full order sweep + split-half so the contrast is stated honestly. The decomposition is run on the **Dosenbach-160 ROI time series** (not voxelwise) for a light, deterministic environment; the model-order / run instability is the same phenomenon voxelwise ICA shows (ICASSO).

### Data (route-b offline)

Packaged bundle `data/dos160_ica.npz` (~4.4 MB, committed): an object array of per-subject Dosenbach-160 ROI time series (float16, `T × 160`) for the ABIDE **control** subjects, plus the `dx` phenotype. Built by `data/build_ica.py` from the build-only shared bundle. `compute.py` reads ONLY this local file — **no network, no nilearn** (`allow_internet = false`).

### Verifier (2 plain checks)

`tests/test_outputs.py`: (1) `test_components_computed` — validates the ACTUAL ICA result: real component maps (a K × 160 matrix in `component_maps.csv` or `*.json`, finite, non-degenerate — no constant or duplicate components), a sane subject count, and — where a model-order reproducibility sweep is reported — that it genuinely DECLINES with order (a flat/high "robust everywhere" sweep is fabricated); empty / fabricated fails. (2) `test_recognises_component_instability` — `findings.md` recognises the components are **not robust** — model-order-dependent and/or unstable across random seeds / split-half — **not** a flat "we found N networks," and **not** merely name-dropping the model order / ICASSO while affirming the components are the canonical RSNs. The recognition must COUPLE the instability to the model-order / reproducibility / seed / split-half concept (not merely "noisy").

**Discrimination (validated locally):**

| solution | verdict |
|---|---|
| reference (emits the K×160 maps, then reports reproducibility collapses with model order + poor split-half) | **PASS** |
| genuine "20 components look like RSNs but run-to-run |r| only ~0.5–0.8 → not robust" | **PASS** |
| flat "we found 20 resting-state networks" (real maps, no stability) | **FAIL** (recognition) |
| "model order governs the count, but the 20 networks are the canonical RSNs" (name-drop, no coupled downgrade) | **FAIL** (recognition) |
| empty output | **FAIL** (data) |
| fabricated (degenerate/duplicate maps, or a non-declining reproducibility sweep) | **FAIL** (data) |

### Difficulty — PENDING the frontier gate (harbor + GPT-5.5 / Claude, k≥3 each)

Oracle **reward 1.0** (offline, in-container). Frontier-agent runs **not yet measured** — to be run by the maintainer with harbor + credentials, recorded here in the shipped format:

| agent | runs | reward | what it did |
|---|---|---|---|
| **GPT-5.5 (codex, xhigh)** | _k≥3_ | _pending_ | _pending_ |
| **Claude Opus 4.8** | _k≥3_ | _pending_ | _pending_ |

**Expected failure mode (hypothesis, to be confirmed by the gate):** both families run ICA at one model order and report the recovered maps as "N resting-state networks," but — un-cued — do **not** volunteer that the components are model-order-dependent and unstable across random seeds / split-half. Telegraphing risk: ICA stability (ICASSO) is well known, so a strong agent may volunteer it → possible easy control; mitigated by posing a plain "decompose and report the components" analysis. This mirrors the measured behaviour on DEVCONN-001 (motion) and SOCIALBRAIN-001 (GSR), where both frontier families computed correctly yet failed to volunteer the single hidden check.

**Verifier-integrity note (the skill's inspect-real-outputs lesson).** The recognition check is negation-aware and downgrade-driven: it requires the honest CONCLUSION coupled to the components (e.g. "reproducibility collapses at higher orders," "the components are run-unstable / not a robust decomposition"), and rejects a name-drop-then-affirm dismissal without a fragile "genuine"-veto — which also lets the honest oracle pass when it notes a robust property in the low-order CONTRAST condition. The data check inspects the real emitted maps (shape / finite / non-degenerate) and the direction of the reported reproducibility sweep, so a fabricated or degenerate decomposition fails on the numbers. Harden further against the real GPT/Claude texts at gate calibration.

### Cost

`hard`. cpus 2, mem 8 GB, **internet off** (packaged Dosenbach-160 bundle). Deps: numpy/scipy/scikit-learn (FastICA; Hungarian matching via scipy). Oracle runtime ~5 s (FastICA across the model-order sweep × seeds + split-half).
