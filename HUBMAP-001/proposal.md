## HUBMAP-001

**Proposal Title:** Identifying functional-connectivity hubs (ABIDE) — an un-cued group-vs-individual aggregation (the *aggregation / Simpson's* failure axis)

**Scientific Domain:** Life Sciences · **Field:** Neuroscience · **Subfield:** Precision functional mapping / network organisation

**Source finding:** Buckner et al. (2009), *J Neurosci*, https://doi.org/10.1523/JNEUROSCI.5062-08.2009 (cortical hubs); individual-variability / precision-mapping references: Gordon et al. (2017), Laumann et al. (2015), Seitzman et al. (2019). Data: `nilearn.datasets.fetch_abide_pcp` (cpac, rois_cc200).

**Status: FULL runnable task, built with `tb-science-task-authoring`.** Opens a **new failure axis** — **aggregation / Simpson's** (statistical-inference family) — on topic *precision functional mapping*, ABIDE. Distinct axis and topic from every shipped task.

**Difficulty vs frontier agents: NOT YET MEASURED** (gate deferred).

### Why this exists
No shipped task covers the aggregation axis (a group-level result asserted of individuals). This fills it: the group connectome's "hubs" are an average that describes almost no single subject.

### The trap (Step-0 + reliability validated; `scratchpad/new_pfm.py`, `pfm_reliability.py`)
ABIDE cc200, n~90:

| measure | value |
|---|---|
| group top-5 hubs appearing in an individual's top-10 | **~8%** (mean); ~63% of subjects share 0 |
| within-subject split-half top-10 hub overlap (noise floor) | ~31% |
| split-half node-strength-map reliability r | 0.61 |

Individuals diverge from the group **far more** than from themselves → the group-vs-individual difference is real variation, **not** measurement noise. The group hub map fits nobody.

### Verifier (2 plain checks) + local calibration
`tests/test_outputs.py`: (1) group hubs computed; (2) `findings.md` recognises that the group hubs do **not** describe individuals (hub organisation varies across individuals) — a flat "the hubs are regions X" over-generalises. Linked-insight guard: the recognition must tie individual variability to the hub/group result (a passing mention of "individual subjects" does not count).

Local calibration (`scratchpad/validate_hubmap.py`):

| output | hubs_computed | recognises_individual |
|---|---|---|
| **oracle** | PASS | PASS — reward 1.0 |
| correct-terse (individual variation) | PASS | PASS |
| flat "hubs are X" | PASS | **FAIL** |
| vague "we included 100 individuals" | PASS | **FAIL** (no false positive) |
| broken (no hub list) | **FAIL** | — |

### Honest caveats / open risks
1. **Difficulty UNTESTED** — needs the gate. **Telegraphing:** likely LOW — "does this group result hold for individuals?" is a subtle check agents rarely volunteer un-cued → best hardness shot of the session.
2. **Prose/judgement verifier** (rigor genre): grades a written insight, so it can't be as clean as a numeric match — the linked-insight guard mitigates false positives; harden against real agent texts at calibration.
3. **Individual hub reliability is moderate** (exact top-10 split-half ~0.31), but the strength-map is reliable (r=0.61) and the group gap (8%) far exceeds within-subject noise — so the effect is real, not noise. Documented in the oracle (it reports the split-half noise floor).

### Cost
`hard`. cpus 2, mem 8 GB, internet on (ABIDE cc200 ROI time series — small, reliable S3 host). Deps: nilearn 0.12.1 + numpy/scipy/pandas/nibabel.
