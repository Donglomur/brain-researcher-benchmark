## MAPREL-001

**Proposal Title:** Is the second functional connectivity gradient spatially correlated with cortical thickness? — an un-cued spatial-autocorrelation / spin-test non-independence trap

**Scientific Domain:** Life Sciences · **Field:** Neuroscience · **Subfield:** Cortical cartography / brain-map statistics

**Source finding / method:** Alexander-Bloch et al. (2018), *NeuroImage*, https://doi.org/10.1016/j.neuroimage.2018.05.070 ("On testing for spatial correspondence between maps of human brain structure and function"); Markello & Misic (2021), *NeuroImage*, https://doi.org/10.1016/j.neuroimage.2021.118052 ("Comparing spatial null models for brain maps"). Data: `neuromaps` annotations `margulies2016 fcgradient02` and `hcps1200 thickness` (fsLR 32k); Schaefer-2018 400-parcel/7-network `fsLR` parcellation (ThomasYeoLab/CBIG). All fetched at runtime, no credentials.

**Status: FULL runnable task, built with the `tb-science-task-authoring` skill.** Opens a failure axis not present in the three shipped recognition-tier tasks (GRADIENT / SOCIALBRAIN / DEVCONN): **spatial autocorrelation / statistical non-independence when correlating two brain maps** — the single most common inference error in comparative brain-map studies.

### Why this exists

GRADIENT-001 (over-claim), SOCIALBRAIN-001 (confident-refutation) and DEVCONN-001 (wrong-cause) all probe un-cued judgement, but none probes the **statistical-inference** axis of Step 2's design space (skill: "the statistical inference — significance of a spatial correlation between two autocorrelated maps"). Comparing two cortical maps with a parcel-wise Pearson r and its parametric p is the field's default reflex, and it is anti-conservative: neighbouring parcels carry near-duplicate values, so the ~400 parcels are nowhere near 400 independent observations. The honest analyst compares r against a **spatial null** that preserves each map's autocorrelation (a spin permutation, Alexander-Bloch 2018; or an autocorrelation-preserving surrogate, e.g. BrainSMASH/Burt 2020, Moran spectral randomization). The task never mentions autocorrelation, spin tests, nulls, or non-independence — the agent must volunteer the check.

### The trap (Step-0 validated, real, robust)

`fcgradient02` (2nd FC gradient) vs `thickness`, parcel-wise Pearson across Schaefer parcels (fsLR 32k):

| parcellation | Pearson r | parametric p | naive label-shuffle p | **spin p** | BrainSMASH surrogate p |
|---|---|---|---|---|---|
| Schaefer-100 | -0.365 | 1.9e-04 | ~2e-04 | 0.21-0.28 | — |
| Schaefer-200 | -0.251 | 3.4e-04 | ~2e-04 | 0.39-0.45 | — |
| **Schaefer-400** | **-0.222** | **7.1e-06** | **~1e-03** | **0.43-0.47** | **0.23** |

- **Naive default is WRONG:** the parametric p (7e-6) and a naive random parcel-label shuffle (~1e-3) both say "highly significant negative correlation." That is the anti-conservative error.
- **Honest answer flips it:** under a spatial-autocorrelation-preserving null the observed r sits comfortably inside the null (spin p ~ 0.45; null mean r ~ +0.02, sd ~ 0.26), so the maps are **not** significantly spatially correlated. The apparent correlation is explained by the shared spatial smoothness of the two maps.
- **Robust across every defensible variant:** parcellation resolution (Schaefer 100/200/400), spin method (`original`, `vasa`, `hungarian` — all give p ≥ 0.2), and **two independent null families** (rotation-based spin *and* variogram-matched BrainSMASH surrogate). The naive-vs-honest gap (p ≈ 1e-4…1e-6 → p ≈ 0.2…0.47) is ~4-5 orders of magnitude and the conclusion flips decisively in all of them.
- **Not always-null (fairness check):** genuine pairs correctly *survive* the same spin — `fcgradient01`–myelin (spin p 0.002), `fcgradient01`–thickness (0.028), myelin–thickness (0.002), `fcgradient01`–`SAaxis` (0.001). So the spin null is not trivially rejecting everything; `fcgradient02`–thickness is a real, specific spurious pair, not an artifact of the method.

Ground truth is a **reproducible measurement on fixed, obtainable public artifacts** (frozen neuromaps annotations + a standard published parcellation) — it passes the skill's ground-truth-substrate rule (nothing fabricated, no open-corpus aggregation). The gradient map is used as a *fixed published input*, so the eigenvector sign/rotation ambiguity that makes gradient *reconstruction* ungradeable is irrelevant here (the significance judgement is sign-invariant).

### Un-cued / off-critical-path

`instruction.md` names the two maps, the space, the parcellation, and asks for the correlation and "whether the two maps are significantly spatially correlated" — the natural deliverable. It never says spin test, spatial null, surrogate, autocorrelation, effective degrees of freedom, or non-independence. An agent can compute r and a p-value (parametric or shuffle) and answer the question in full **without ever performing a spatial null** — the null is a volunteered judgement, off the critical path.

### Verifier (2 plain checks, v2 recognition grader)

`tests/test_outputs.py`: (1) `test_maps_parcellated_and_correlated` — a parcel-level correlation was actually computed (parcels.csv ~400 rows, ≥2 numeric map columns; a between-map |r| in [0.10, 0.55] reported); schema-robust (finds the map columns and the r generically). (2) `test_recognises_spatial_autocorrelation_nonsignificance` — the negation-aware, downgrade-driven recognition grader (identical helper to the shipped tasks): `findings.md` must couple a **spatial-null / autocorrelation** concept to a **non-significance / spurious** conclusion (spin/surrogate → not significant; or the correlation is spurious / attributable to shared spatial autocorrelation), un-negated. A bare parametric "significantly correlated", a naive label-shuffle "significant", a name-drop-then-dismiss ("a spin test is unnecessary"), a negated mention ("no spin test was run; it wouldn't change anything"), a vague hedge, and a scientifically-wrong "spin p = 0.02, significant" all fail; spin- and surrogate-based honest write-ups (including numeric-only "p_spin = 0.45, autocorrelation accounted for") pass.

**Offline discrimination (locked, `tests/` verified against the real reference + 9 adversarials):** reference PASS; naive-parametric FAIL; naive-shuffle FAIL; dismisser FAIL; negated-namedrop FAIL; vague-hedge FAIL; spin-but-called-significant FAIL; honest-spin PASS; honest-surrogate(BrainSMASH) PASS; honest-numeric-only PASS. (10/10.)

### Difficulty — construction bar met; live frontier gate is the maintainer's Step-5

Oracle **reward 1.0** in-container (reference `solution/compute.py` computes r, parametric/shuffle p, and the spin p, and writes the honest `findings.md`). Adversarial gates bite as tabulated above. Per the skill and the brief, the live ≥2-frontier-family gate (GPT-5.x, Claude-Opus, k≥3) is the maintainer's to run; it is **not** confirmed here. Honest caveat specific to this axis: the skill's difficulty ladder notes procedural rigor (spin nulls) is often within frontier priors *when cued or framed as a rigor task* — the wager here is the **un-cued** framing ("are these two maps correlated?"), the field-default reflex to reach for Pearson + parametric p, and the fact that map-comparison significance is exactly where the published literature most often errs. The construction bar (un-cued, off-critical-path, naive-default-wrong, big robust gap, guarded fair grader, oracle 1.0) is met; the frontier gap is the maintainer's to measure.

### Lineage / de-duplication (honest note for the maintainer)

This axis was attempted twice before and **both attempts are closed, unmerged** (branches deleted; master carries only GRADIENT/SOCIALBRAIN/DEVCONN on any axis): PR #29 `MAPCORR-001` (superseded) and PR #57 `CORTMAPS-001`, closed with "Parked … can be reopened anytime" during the pivot to the hard-reconstruction set — **not** a validity rejection. #57 used the *principal* gradient (`fcgradient01`) vs thickness, whose correlation is r ≈ +0.41 and **remains significant under the spin (p ≈ 0.028)** — a weak/ambiguous lever whose honest answer is "significant". MAPREL-001 instead pins `fcgradient02`, a **decisively spurious** pair (spin p ≈ 0.45, robust across resolutions × spin methods × null families), and fetches everything at runtime (`allow_internet=true`) rather than committing data. This is the current replacement wave bringing focus back to the recognition tier, so a strong version of this axis is in-scope.

### Cost / engineering

`hard`. cpus 2, mem 8 GB, `allow_internet=true`. Runtime fetch: two neuromaps annotations + the fsLR sphere atlas (OSF) and the Schaefer dlabel (raw.githubusercontent). Compute is light (400-parcel spin, 1000 rotations, < 1 min). **Reliability caveat (skill's osf note):** neuromaps pulls from OSF, which throttles/times-out under repeated fresh pulls; external CI runners may hit this. During dev/agent runs the host `~/neuromaps-data` cache removes the download. Deps pinned to a verified-together set (neuromaps 0.0.7 + brainsmash 0.11.0 + numpy 2.2.6 / scipy 1.17.0 / nibabel 5.4.2 / nilearn 0.13.1); brainsmash is installed so the honest surrogate route is available as well as the spin. `source_paper` DOIs are the two canonical spin-null method papers (verified).
