## MAPCORR-001

**Proposal Title:** Spatial correspondence between two cortical maps — an un-cued spatial-autocorrelation / spin-test null (the *wrong-null / spatial-autocorrelation* failure axis — NEW)

**Scientific Domain:** Life Sciences · **Field:** Neuroscience · **Subfield:** Cortical cartography / structure-function correspondence

**Source finding:** Alexander-Bloch et al. (2018), *NeuroImage*, https://doi.org/10.1016/j.neuroimage.2018.05.070 — the correlation between two brain maps must be tested against a **spatial-autocorrelation-preserving null (spin test)**; the parametric test is anticonservative because vertices are not independent. Maps: Margulies et al. (2016), *PNAS* (functional gradients); HCP S1200 cortical thickness. Data via **neuromaps** (fsLR 32k).

**Status: FULL runnable task, built with `tb-science-task-authoring`.** Opens a **NEW failure axis — spatial autocorrelation / wrong spatial null** (statistical-inference family), on a **new data type** (cortical surface maps / structure-function) the suite did not previously cover. The spatial analogue of DYNFC's temporal stationarity null.

**Difficulty vs frontier agents: NOT YET MEASURED** (gate deferred).

### Why this exists
Correlating two brain maps is one of the most common analyses in cortical neuroscience, and the parametric p-value is almost always what gets reported — even though both maps are strongly spatially autocorrelated, which makes that p-value meaningless (Alexander-Bloch 2018). The un-cued judgement is to test the correspondence against a spin test; without it, an analyst reports dramatic false positives.

### The trap (Step-0 validated) — a p ≈ 0 correlation that is pure spatial autocorrelation
fsLR 32k, 59,412 cortical vertices, cortical thickness vs the 2nd functional connectivity gradient:

| test | result |
|---|---|
| Pearson correlation | **r = −0.198** |
| parametric p (vertices treated as independent) | **≈ 0** (`0.0`) |
| **spin test** (Alexander-Bloch, 1000 rotations) | **p = 0.34 — NOT significant** |

The parametric test declares an overwhelmingly significant structure-function correspondence; the spin test — the correct spatial-autocorrelation-preserving null — shows it is indistinguishable from chance. The correspondence is a **spatial-autocorrelation artifact**.

**Step-0 breadth note (no cherry-pick).** This is not a one-off: across HCP thickness/myelin × Margulies gradients 1–3 × the Sydnor S-A axis, the search found **8 clean trap pairs** (parametric p from 1e-11 down to **1e-158**, all spin-n.s.), alongside pairs that correctly *survive* the spin test (myelin–gradient1, gradient1–S-A axis; r up to 0.83) — confirming the spin test discriminates real correspondences from spatial-autocorrelation false positives rather than rejecting everything. The task uses thickness vs gradient-2 (a plausible, moderate r = −0.20 that an analyst would confidently report).

### Verifier (2 plain checks)
`tests/test_outputs.py`: (1) a map-to-map correlation was computed; (2) `findings.md` recognises the correlation does **not** survive a spatial-autocorrelation-preserving null (spin test) — a flat "the maps are significantly correlated (p<...)" over-claims. Strong-token guard: the recognition must name the spatial-autocorrelation / spin-test concept (not merely "noise"), linked to the correspondence. Offline: oracle PASS; flat-significant adversarial FAIL; vague "maps are noisy" hedge FAIL.

### Honest caveats / open risks
1. **Difficulty UNTESTED** — needs the gate. **Telegraphing:** the spin test is well-known in cortical-map work; a strong agent may volunteer it un-cued → possible easy control. The gate decides. (Mitigated by using a moderate, believable r rather than an obvious near-zero.)
2. **Data dependency:** neuromaps fetches maps + the fsLR sphere from **OSF** at runtime (allow_internet). OSF was intermittently down earlier this cycle; maps cache after first fetch. Less reliable than the nilearn/S3 tasks — flagged.
3. **Prose/judgement verifier** (rigor genre) — strong-token + linked-insight guards mitigate false positives; harden against real agent texts at calibration.

### Cost
`hard`. cpus 2, mem 8 GB, internet on (neuromaps annotation maps + fsLR sphere from OSF; ~tens of MB). Deps: neuromaps 0.0.7 + nibabel/nilearn/scipy/numpy/scikit-learn/matplotlib. Oracle runtime dominated by the 1000-rotation spin (~1–2 min).
