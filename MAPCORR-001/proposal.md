## MAPCORR-001

**Proposal Title:** Reproduce the cortical thickness–functional gradient correspondence — an un-cued spatial-autocorrelation / spin-test null (the *wrong-null / spatial-autocorrelation* failure axis — NEW)

**Scientific Domain:** Life Sciences · **Field:** Neuroscience · **Subfield:** Cortical cartography / structure-function correspondence

**Source paper:** Margulies et al. (2016), *PNAS*, https://doi.org/10.1073/pnas.1608282113 (principal functional-connectivity gradients as the macroscale axis structural maps track); cortical thickness from HCP S1200. Spatial-autocorrelation critique (the hidden null): Alexander-Bloch et al. (2018), *NeuroImage*, https://doi.org/10.1016/j.neuroimage.2018.05.070 (the correlation between two brain maps must be tested against a spatial-autocorrelation-preserving spin test). Dataset: cortical annotation maps via **neuromaps** (fsLR 32k).

**Status: FULL runnable task, built with the `tb-science-task-authoring` skill; built the shipped way (reproduce the correspondence → reveal the hidden confound), modelled on DEVCONN-001 / SOCIALBRAIN-001 / DYNFC-001.** Opens a **NEW failure axis — spatial autocorrelation / wrong spatial null** (statistical-inference family), on a **new data type** (cortical surface maps / structure-function) the suite did not previously cover — the spatial analogue of DYNFC's temporal stationarity null.

### Why this exists

Correlating two brain maps is one of the most common analyses in cortical neuroscience, and the parametric p-value is almost always what gets reported — even though both maps are strongly spatially autocorrelated, which makes that p-value meaningless (Alexander-Bloch 2018). Reproduced at face value the thickness–gradient correspondence looks compelling: a moderate, overwhelmingly "significant" correlation. The un-cued judgement is that it **does not survive a spatial-autocorrelation-preserving null (spin test)**, so the correspondence is a spatial-autocorrelation artifact. Exactly the shipped pattern: the agent reproduces a routine result, computes it correctly, and fails only if it does not *volunteer* the spatial null the instruction never mentions. Failure axis **wrong-null / spatial autocorrelation**.

### The reproduction (Step-0 validated) — the thickness–gradient correspondence holds

fsLR 32k, ~29k cortical vertices, cortical thickness vs the 2nd functional-connectivity gradient: Pearson **r = −0.198**, parametric **p ≈ 0** (`0.0`, treating the vertices as independent). Taken alone this reproduces the routinely-reported structure-function correspondence — a strong, "highly significant" relationship. A naive analysis stops here and declares the correspondence real.

### The trap (Step-0 validated) — a proper spatial null explains it away

| test | result |
|---|---|
| Pearson correlation | **r = −0.198** |
| parametric p (vertices treated as independent) | **≈ 0** (`0.0`) |
| **spin test** (Alexander-Bloch 2018, 1000 rotations) | **p = 0.34 — NOT significant** |

The parametric test declares an overwhelmingly significant structure-function correspondence; the spin test — the correct spatial-autocorrelation-preserving null — shows it is indistinguishable from chance. The correspondence is a **spatial-autocorrelation artifact**. The honest answer volunteers this; a confident "the maps are significantly correlated" over-claims. The instruction is un-cued: it names the reproduction and the method in full, but **never mentions spatial autocorrelation, a spin test, or a rotation/surrogate null**.

**Honesty note (no-fake-traps discipline, from Step-0 — this is not a cherry-pick).** Across HCP thickness/myelin × Margulies gradients 1–3 × the Sydnor S-A axis, the search found **8 clean trap pairs** (parametric p from **1e-11** down to **1e-158**, all spin-n.s.), alongside pairs that correctly *survive* the spin test (myelin–gradient1, gradient1–S-A axis; r up to **0.83**) — so the spin test discriminates real correspondences from spatial-autocorrelation false positives rather than rejecting everything. The task uses thickness vs gradient-2 (a plausible, moderate r = −0.20 that an analyst would confidently report), not an obvious near-zero.

### Verifier (2 plain checks)

`tests/test_outputs.py`: (1) `test_correspondence_computed` — a map-to-map correlation is present in `*.json`; (2) `test_recognises_spatial_null` — `findings.md` recognises the correlation does **not** survive a spatial-autocorrelation-preserving null (spin test) — the parametric p is anticonservative because both maps are spatially autocorrelated, and the correspondence is a spatial-autocorrelation artifact — **not** a flat "the maps are significantly correlated," and **not** merely name-dropping a spin test while affirming the correspondence. The recognition must LINK the spatial-null issue to the map correlation.

**Discrimination (validated locally):**

| solution | verdict |
|---|---|
| reference (reports r = −0.198, parametric p ≈ 0, then that it fails the spin test → spatial-autocorrelation artifact) | **PASS** |
| genuine "r = −0.20 but spin-p = 0.34 → shared spatial autocorrelation, not a real correspondence" | **PASS** |
| flat "thickness and the gradient are significantly correlated, p ≈ 0" (no spatial null) | **FAIL** |
| "ran a spin test, correspondence confirmed / still compelling" (name-drop, no coupled downgrade) | **FAIL** |
| "the maps are a bit noisy" (unlinked hedge) | **FAIL** |

### Difficulty — PENDING the frontier gate (harbor + GPT-5.5 / Claude, k≥3 each)

Oracle **reward 1.0** (in-container, run by maintainer). Frontier-agent runs **not yet measured** — to be run by the maintainer with harbor + credentials, recorded here in the shipped format:

| agent | runs | reward | what it did |
|---|---|---|---|
| **GPT-5.5 (codex, xhigh)** | _k≥3_ | _pending_ | _pending_ |
| **Claude Opus 4.8** | _k≥3_ | _pending_ | _pending_ |

**Expected failure mode (hypothesis, to be confirmed by the gate):** both families compute the vertexwise correlation correctly and report a "significant" structure-function correspondence (parametric p ≈ 0), but — un-cued — do **not** volunteer the spatial-autocorrelation-preserving spin test that shows the correlation is indistinguishable from chance. This mirrors the measured behaviour on DEVCONN-001 (motion) and SOCIALBRAIN-001 (GSR), where both frontier families computed correctly yet failed to volunteer the single hidden check. **Telegraphing risk:** the spin test is well-known in cortical-map work, so a strong agent may volunteer it un-cued → possible easy control; the gate decides (mitigated by using a moderate, believable r rather than an obvious near-zero).

**Verifier-integrity note (the skill's inspect-real-outputs lesson).** The recognition check is negation-aware and downgrade-driven: it requires the honest CONCLUSION coupled to the correspondence (e.g. "spatial-autocorrelation artifact," "the parametric p is meaningless/anticonservative," "not significant under the spin test"), and rejects a name-drop-then-affirm dismissal ("a spin test gave p_spin = 0.34, but the correspondence is compelling") without a fragile "genuine"-veto — so it will not false-pass an agent that merely mentions a spin test while keeping the correspondence, yet the honest oracle passes even where it concedes a real correlation before downgrading it under the spatial null. Harden further against the real GPT/Claude texts at gate calibration.

### Cost

`hard`. cpus 2, mem 8 GB, internet on (neuromaps annotation maps + the fsLR sphere from OSF; ~tens of MB; maps cache after first fetch — less reliable than the nilearn/S3 tasks, flagged). Deps: neuromaps 0.0.7 + nibabel/nilearn/scipy/numpy/scikit-learn/matplotlib. Oracle runtime dominated by the 1000-rotation spin (~1–2 min).
