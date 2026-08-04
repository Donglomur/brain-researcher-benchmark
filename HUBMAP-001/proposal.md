## HUBMAP-001

**Proposal Title:** Reproduce the Buckner (2009) cortical-hub finding — an un-cued group-vs-individual aggregation trap (the *aggregation / Simpson's* failure axis)

**Scientific Domain:** Life Sciences · **Field:** Neuroscience · **Subfield:** Macroscale network organisation / precision functional mapping

**Source finding:** Buckner et al. (2009), *J Neurosci*, https://doi.org/10.1523/JNEUROSCI.5062-08.2009 — degree-centrality hubs of the intrinsic connectivity network concentrate in heteromodal **association cortex** overlapping the default network (medial prefrontal, posterior cingulate/precuneus, lateral parietal), not primary sensorimotor/visual cortex. Individual-variability / precision-mapping critique: Gordon et al. (2017), Laumann et al. (2015), Mueller et al. (2013), Seitzman et al. (2019). Data: `nilearn.datasets.fetch_abide_pcp` (cpac, **rois_dosenbach160** — a labelled atlas so hubs can be mapped to networks/anatomy).

**Status: FULL runnable task, built with `tb-science-task-authoring`.** Failure axis **aggregation / Simpson's** (statistical-inference family), topic *cortical hubs / precision functional mapping*, ABIDE. Distinct axis and topic from every shipped task.

**Difficulty vs frontier agents: NOT YET MEASURED** (gate deferred).

### Why this exists
Anchored the shipped way — **reproduce a specific primary finding, then reveal its hidden trap.** Buckner's cortical-hub result is a textbook group-level finding; the un-cued judgement is that this group hub map, however reliable, describes almost no single individual (the aggregation axis, which no shipped task covers).

### The reproduction (Step-0 validated) — Buckner's finding holds here
ABIDE controls, Dosenbach-160, weighted degree (node strength), n≈70:

| group hub (rank) | region | network |
|---|---|---|
| 1 | medial prefrontal cortex | default |
| 2 | posterior cingulate | default |
| 3 | inferior parietal lobule | fronto-parietal |
| 4 | medial frontal cortex | cingulo-opercular |
| 5 | lateral temporal | cingulo-opercular |

**90%** of the top-10 hubs fall in **association cortex** (atlas base rate 54%); primary sensorimotor/visual cortex is under-represented (**10%** vs 34% base rate). The two top hubs are mPFC and posterior cingulate — the canonical default-network hubs. This reproduces Buckner (2009).

**Honesty note (no-fake-traps discipline, from Step-0).** The reproduction is *measure-dependent*, and I checked this rather than assuming it. **Binary degree centrality at a 10% edge-density threshold does NOT reproduce Buckner** on these data — it is dominated by tightly-correlated sensorimotor/cingulo-opercular clusters (top-10 = 3 association / 3 primary; default-network mean degree is actually *negative*). The association-cortex hub concentration appears with **weighted degree (node strength)** and with eigenvector centrality (top-10 = 9/10 association). Node strength is the standard hub measure (and what a competent analyst uses), so the task uses it — but the oracle records that the network-wide *mean* does not separate; the reproduction lives in the *top hubs*, exactly Buckner's claim.

### The trap (Step-0 validated) — the group hubs do not describe individuals
Same pipeline, per-subject:

| measure | value |
|---|---|
| group hub-map split-half reliability (r) | **0.78** (group map is stable) |
| group top-5 hubs appearing in a typical individual's top-10 | **~1.2 of 5 (≈25%)** |
| individual-vs-group top-10 hub overlap | **~0.22** |

The group map is highly reliable, yet a typical individual shares only ~1 of the 5 group hubs — the divergence is real individual variation in hub topography, not measurement noise (the map is reliable). The group hub map is an aggregate that fits almost nobody.

### Verifier (2 plain checks) + local calibration
`tests/test_outputs.py`: (1) group hubs computed; (2) `findings.md` recognises that the group hubs do **not** describe individuals (hub organisation varies across individuals) — a flat "the hubs are regions X" over-generalises. Linked-insight guard: the recognition must tie individual variability to the hub/group result (a bare mention of "individual subjects" does not count).

| output | hubs_computed | recognises_individual |
|---|---|---|
| **oracle** (reproduces Buckner + volunteers aggregation) | PASS | PASS — reward 1.0 |
| correct-terse (individual variation) | PASS | PASS |
| flat "hubs are mPFC/PCC/IPL" | PASS | **FAIL** |
| vague "we included 70 individuals" | PASS | **FAIL** (no false positive) |
| broken (no hub list) | **FAIL** | — |

### Honest caveats / open risks
1. **Difficulty UNTESTED** — needs the gate. **Telegraphing:** likely LOW — "does this group hub result hold for individuals?" is a subtle check agents rarely volunteer un-cued.
2. **Prose/judgement verifier** (rigor genre): grades a written insight; the linked-insight guard mitigates false positives; harden against real agent texts at calibration.
3. **Reproduction is measure-dependent** (documented above): binary degree does not reproduce Buckner; weighted degree does. The oracle uses the standard measure and records the caveat, so the reproduction is honest, not cherry-picked.

### Cost
`hard`. cpus 2, mem 8 GB, internet on (ABIDE Dosenbach-160 ROI time series + the Dosenbach coord/label atlas — small, reliable S3 host). Deps: nilearn 0.12.1 + numpy/scipy/pandas/nibabel.
