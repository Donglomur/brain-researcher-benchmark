## HUBMAP-001

**Proposal Title:** Reproduce the Buckner (2009) association-cortex hub finding — an un-cued group-vs-individual aggregation trap (the *aggregation / Simpson's* failure axis)

**Scientific Domain:** Life Sciences · **Field:** Neuroscience · **Subfield:** Macroscale network organisation / precision functional mapping

**Source paper:** Buckner et al. (2009), *J Neurosci*, https://doi.org/10.1523/JNEUROSCI.5062-08.2009 — degree-centrality hubs of the intrinsic connectivity network concentrate in heteromodal **association cortex** overlapping the default network (medial prefrontal, posterior cingulate/precuneus, lateral parietal), not primary sensorimotor/visual cortex (see also van den Heuvel & Sporns, 2013). Individual-variability / precision-mapping critique: Gordon et al. (2017), Laumann et al. (2015), Mueller et al. (2013), Seitzman et al. (2019). Dataset: `nilearn.datasets.fetch_abide_pcp` (cpac, **rois_dosenbach160** — a labelled atlas so hubs can be mapped to networks/anatomy).

**Status: FULL runnable task, built the shipped way (reproduce the primary finding → reveal the hidden trap), modelled on DEVCONN-001 / SOCIALBRAIN-001.** Failure axis **aggregation / Simpson's** (statistical-inference family), topic *cortical hubs / precision functional mapping*, ABIDE. Distinct axis and topic from every shipped task.

### Why this exists

Buckner's cortical-hub result is a textbook group-level finding. Reproduced at face value it holds — the group hub map lands squarely in association/default cortex. The un-cued judgement is that this group hub map, however reliable, describes almost no single individual (the aggregation axis, which no shipped task covers): the agent is asked to reproduce a famous result, computes it correctly, and fails only if it does not *volunteer* the group-vs-individual check the instruction never mentions.

### The reproduction (Step-0 validated) — Buckner's finding holds here

ABIDE controls, Dosenbach-160, weighted degree (node strength), n ≈ 70:

| group hub (rank) | region | network |
|---|---|---|
| 1 | medial prefrontal cortex | default |
| 2 | posterior cingulate | default |
| 3 | inferior parietal lobule | fronto-parietal |
| 4 | medial frontal cortex | cingulo-opercular |
| 5 | lateral temporal | cingulo-opercular |

**90%** of the top-10 hubs fall in **association cortex** (atlas base rate 54%); primary sensorimotor/visual cortex is under-represented (**10%** vs 34% base rate). The two top hubs are mPFC and posterior cingulate — the canonical default-network hubs. This reproduces Buckner (2009). A naive analysis stops here and reports these as *the* brain's hubs.

**Honesty note (no-fake-traps discipline, from Step-0).** The reproduction is *measure-dependent*, and this was checked rather than assumed. **Binary degree centrality at a 10% edge-density threshold does NOT reproduce Buckner** on these data — it is dominated by tightly-correlated sensorimotor/cingulo-opercular clusters (top-10 = 3 association / 3 primary; default-network mean degree is actually *negative*). The association-cortex hub concentration appears with **weighted degree (node strength)** and with eigenvector centrality (top-10 = 9/10 association). Node strength is the standard hub measure (and what a competent analyst uses), so the task uses it — the oracle records that the network-wide *mean* does not separate; the reproduction lives in the *top hubs*, exactly Buckner's claim.

### The trap (Step-0 validated) — the group hubs do not describe individuals

Same pipeline, per-subject:

| measure | value |
|---|---|
| group hub-map split-half reliability (r) | **0.78** (group map is stable) |
| group top-5 hubs appearing in a typical individual's top-10 | **~1.2 of 5 (≈25%)** |
| individual-vs-group top-10 hub overlap | **~0.22** |

The group map is highly reliable, yet a typical individual shares only ~1 of the 5 group hubs — the divergence is real individual variation in hub topography, not measurement noise (the map is reliable). The group hub map is an aggregate that fits almost nobody. The honest answer volunteers this; a confident "the hubs are mPFC/PCC/IPL" over-generalises the average to every subject. The instruction is un-cued: it names the reproduction and the method in full, but **never mentions individual variability, per-subject analysis, split-half reliability, aggregation, or generalisation**.

### Verifier (2 plain checks)

`tests/test_outputs.py`: (1) `test_hubs_computed` — a list of group hub nodes is present in `hubs.json`; (2) `test_recognises_individual_variability` — `findings.md` recognises that the group hubs do **not** describe individuals (hub organisation varies across individuals, beyond within-subject noise) — **not** a flat "the hubs are regions X," and **not** a dismissal that cites the same overlap numbers and calls them "good reproducibility." The recognition must LINK individual variability to the hub/group result (a bare mention of "individual subjects" does not count).

**Discrimination (validated locally):**

| solution | verdict |
|---|---|
| reference (reproduces Buckner, then volunteers the group hubs fit almost no individual) | **PASS — reward 1.0** |
| correct-terse (individual variation in hub topography) | **PASS** |
| flat "the hubs are mPFC/PCC/IPL" (no aggregation) | **FAIL** |
| vague "we included 70 individuals" (no coupled downgrade) | **FAIL** |
| "the group hubs generalise fine to individuals; hub topography is not idiosyncratic" (dismissal) | **FAIL** |
| broken (no hub list) | **FAIL** on check 1 |

### Difficulty — PENDING the frontier gate (harbor + GPT-5.5 / Claude, k≥3 each)

Oracle **reward 1.0** (in-container, run by maintainer). Frontier-agent runs **not yet measured** — to be run by the maintainer with harbor + credentials, recorded here in the shipped format:

| agent | runs | reward | what it did |
|---|---|---|---|
| **GPT-5.5 (codex, xhigh)** | _k≥3_ | _pending_ | _pending_ |
| **Claude Opus 4.8** | _k≥3_ | _pending_ | _pending_ |

**Expected failure mode (hypothesis, to be confirmed by the gate):** both families compute the group hub map correctly and reproduce Buckner's association-cortex result, but — un-cued — do **not** volunteer the group-vs-individual check that shows the reliable group map describes almost no single subject. Telegraphing is likely LOW: "does this group hub result hold for individuals?" is a subtle check agents rarely raise un-cued. This mirrors the measured behaviour on DEVCONN-001 (motion) and SOCIALBRAIN-001 (GSR), where both frontier families computed correctly yet failed to volunteer the single hidden check.

**Verifier-integrity note (the skill's inspect-real-outputs lesson).** The recognition check is negation-aware and downgrade-driven: it requires the honest CONCLUSION coupled to the hub/group result (e.g. "hub topography varies across individuals," "the group map generalises poorly," "over-generalises the average"), and rejects a dismissal that reports the same overlap value (0.22) or the "1 of 5" count and mislabels it "good reproducibility" — merely citing the number is not a coupled downgrade, so it will not false-pass. Harden further against the real GPT/Claude texts at gate calibration.

### Cost

`hard`. cpus 2, mem 8 GB, internet on (ABIDE Dosenbach-160 ROI time series + the Dosenbach coord/label atlas — small, reliable S3 host). Deps: nilearn 0.12.1 + numpy/scipy/pandas/nibabel.
