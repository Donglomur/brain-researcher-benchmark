## CORTMAPS-001

**Proposal Title:** Reproduce the cortical thickness–functional gradient correspondence — an un-cued spatial-autocorrelation / spin-test null (the *wrong-null / spatial-autocorrelation* failure axis)

**Scientific Domain:** Life Sciences · **Field:** Neuroscience · **Subfield:** Cortical cartography / structure-function correspondence

**Source paper:** Margulies et al. (2016), *PNAS*, https://doi.org/10.1073/pnas.1608282113 (principal functional-connectivity gradients as the macroscale axis structural maps track); cortical thickness from HCP S1200. Spatial-autocorrelation critique (the hidden null): Alexander-Bloch et al. (2018), *NeuroImage*, https://doi.org/10.1016/j.neuroimage.2018.05.070 (the correlation between two brain maps must be tested against a spatial-autocorrelation-preserving spin test). Dataset: cortical annotation maps via **neuromaps** (fsLR 32k).

**Status: FULL runnable task, built with the `tb-science-task-authoring` skill; built the shipped way (reproduce the correspondence → reveal the hidden confound), modelled on DEVCONN-001 / SOCIALBRAIN-001 / DYNCONN-001 / GMATROPHY-001 / TOPEDGES-001.** Opens the **spatial-autocorrelation / wrong-null failure axis** (statistical-inference family) on a **data type** (cortical surface maps / structure-function) — the spatial analogue of DYNFC's temporal-stationarity null and GMATROPHY's smoothing multiverse.

### Why this exists

Correlating two brain maps is one of the most common analyses in cortical neuroscience, and the parametric p-value is almost always what gets reported — even though both maps are strongly spatially autocorrelated, which makes that p-value meaningless (Alexander-Bloch 2018). Reproduced at face value the thickness–gradient correspondence looks compelling: a moderate, overwhelmingly "significant" correlation. The un-cued judgement is that it **does not survive a spatial-autocorrelation-preserving null (spin test)**, so the correspondence is a spatial-autocorrelation artifact. Exactly the shipped pattern: the agent reproduces a routine result, computes it correctly, and fails only if it does not *volunteer* the spatial null the instruction never mentions. Failure axis **wrong-null / spatial autocorrelation**.

### The reproduction and the trap (validated) — held privately

The validated numbers (Pearson r, parametric p, the spin-test p_spin, cortical vertex count, n_spins) and the oracle receipt are in the **private, git-ignored `calibration.md`** (rule 4: agents have internet + the repo is public). In brief: cortical thickness and the second functional-connectivity gradient correlate at a moderate, believable magnitude with an astronomically small PARAMETRIC p (vertices treated as independent) — reproducing the routinely-reported structure-function correspondence — but the SAME correlation is **not significant under an Alexander-Bloch spin test** (a spatial-autocorrelation-preserving null), so the apparent correspondence is a spatial-autocorrelation artifact. The instruction is un-cued: it names the reproduction and the method in full, but **never mentions spatial autocorrelation, a spin test, or a rotation / surrogate null.**

**Honesty note (no-fake-traps discipline).** The spin test *discriminates* real correspondences from spatial-autocorrelation false positives rather than rejecting everything: across HCP thickness/myelin × Margulies gradients 1–3 × the Sydnor S-A axis, several pairs correctly *survive* the spin test (e.g. myelin–gradient1, gradient1–S-A axis; |r| up to ~0.8), alongside clean trap pairs that do not. The task uses thickness vs gradient-2 — a plausible, moderate correlation an analyst would confidently report, not an obvious near-zero.

### Route — offline (route b), no network

The two maps + the fsLR-32k sphere coordinates + the no-medial-wall cortical mask are packaged into `data/mapcorr_fslr32k.npz` (~0.9 MB) by `data/build_maps.py` (reads the neuromaps cache). `solution/compute.py` reads only that npz and runs a **self-contained Alexander-Bloch spin** (numpy/scipy `cKDTree` + mirrored random spherical rotations) — no neuromaps, no network at runtime (`allow_internet=false`). The self-contained spin reproduces the canonical neuromaps `nulls.alexander_bloch` + `stats.compare_images` result exactly (cross-check in `calibration.md`).

### Verifier (2 checks over the ACTUAL data)

`tests/test_outputs.py`: (1) `test_correspondence_computed` — validates the actual data: the two named maps, a real cortical vertex count (medial wall removed), a plausible moderate correlation, and — once a spin test is reported — a real `n_spins`, a genuine near-zero-centred spin null, and a spin p in the honest (larger, non-significant) direction; empty / fabricated (fake correlation, fake vertex count, wrong-direction or fabricated spin null) fails. (2) `test_recognises_spatial_null` — passes if EITHER a genuine spin null is emitted (objective proof), OR `findings.md` recognises the correlation does **not** survive a spatial-autocorrelation-preserving null (spin test) — the parametric p is anticonservative because both maps are spatially autocorrelated, and the correspondence is a spatial-autocorrelation artifact — **not** a flat "the maps are significantly correlated," and **not** merely name-dropping a spin test while affirming the correspondence. The recognition must COUPLE the spatial-null issue to the map correlation.

**Discrimination (validated locally):**

| solution | verdict |
|---|---|
| reference (reports the moderate r, astronomically small parametric p, then that it fails the spin test → spatial-autocorrelation artifact) | **PASS** |
| genuine "moderate r but spin-test n.s. → shared spatial autocorrelation, not a real correspondence" | **PASS** |
| flat "thickness and the gradient are significantly correlated, p ≈ 0" (no spatial null) | **FAIL** (recognition) |
| "ran a spin test, correspondence confirmed / still compelling" (name-drop, no coupled downgrade) | **FAIL** |
| fabricated (fake correlation / fake vertex count / fabricated or wrong-direction spin null) | **FAIL** (data) |
| empty | **FAIL** |

### Difficulty — PENDING the frontier gate (harbor + GPT-5.5 / Claude, k≥3 each)

Oracle **reward 1.0** (offline, self-contained). Frontier-agent runs **not yet measured** — to be run by the maintainer with harbor + credentials, recorded here in the shipped format:

| agent | runs | reward | what it did |
|---|---|---|---|
| **GPT-5.5 (codex, xhigh)** | _k≥3_ | _pending_ | _pending_ |
| **Claude Opus 4.8** | _k≥3_ | _pending_ | _pending_ |

**Expected failure mode (hypothesis, to be confirmed by the gate):** both families compute the vertexwise correlation correctly and report a "significant" structure-function correspondence (parametric p ≈ 0), but — un-cued — do **not** volunteer the spatial-autocorrelation-preserving spin test that shows the correlation is indistinguishable from chance. This mirrors the measured behaviour on DEVCONN-001 (motion) and SOCIALBRAIN-001 (GSR). **Telegraphing risk:** the spin test is well-known in cortical-map work, so a strong agent may volunteer it un-cued → possible easy control; the gate decides (mitigated by using a moderate, believable r rather than an obvious near-zero, and by the packaged sphere geometry making the spin test *possible but never mentioned*).

**Verifier-integrity note (the skill's inspect-real-outputs lesson).** The recognition check is negation-aware and downgrade-driven: it requires the honest CONCLUSION coupled to the correspondence (e.g. "spatial-autocorrelation artifact," "the parametric p is meaningless / anticonservative," "not significant under the spin test"), and rejects a name-drop-then-affirm dismissal without a fragile "genuine"-veto — so it will not false-pass an agent that merely mentions a spin test while keeping the correspondence, yet the honest oracle passes even where it concedes a real correlation before downgrading it under the spatial null. A genuine spin null emitted in the outputs is an objective recognition short-circuit (like GMATROPHY's real-reversal short-cut). Harden further against the real GPT/Claude texts at gate calibration.

### Cost

`hard`. cpus 2, mem 8 GB, **internet off** (packaged fsLR-32k bundle, ~0.9 MB). Deps: numpy / scipy (+ pandas / nibabel for convenience); the spin is self-contained. Oracle runtime dominated by the 1000-rotation spin (~1.5 min).
