## CORTHUBS-001

**Proposal Title:** Reproduce the Buckner (2009) association-cortex hub finding — an un-cued group-vs-individual aggregation trap (the *aggregation / Simpson's* failure axis; answer + numbers in private calibration.md)

**Scientific Domain:** Life Sciences · **Field:** Neuroscience · **Subfield:** Macroscale network organisation / precision functional mapping

**Source paper:** Buckner et al. (2009), *J Neurosci*, https://doi.org/10.1523/JNEUROSCI.5062-08.2009 — degree-centrality hubs of the intrinsic connectivity network concentrate in heteromodal **association cortex** overlapping the default network (medial prefrontal, posterior cingulate/precuneus, lateral parietal), not primary sensorimotor/visual cortex (see also van den Heuvel & Sporns, 2013). Individual-variability / precision-mapping critique (the un-cued axis): Gordon et al. (2017), Laumann et al. (2015), Mueller et al. (2013), Seitzman et al. (2019) — reliable group topographies need not describe any individual. Dataset: ABIDE (`nilearn.datasets.fetch_abide_pcp`, cpac, **rois_dosenbach160** — a labelled atlas so hubs can be mapped to networks/anatomy), **packaged offline** as a per-subject connectome bundle.

**Status: FULL runnable task, route-b offline (reads a packaged `data/*.npz`; no network), built the shipped way (reproduce the primary finding → reveal the hidden trap), modelled on TOPEDGES-001 / GMATROPHY-001 / DEVCONN-001 / SOCIALBRAIN-001.** Failure axis **aggregation / Simpson's** (statistical-inference family), topic *cortical hubs / precision functional mapping*, ABIDE. Distinct axis and topic from every shipped task.

### Why this exists

Buckner's cortical-hub result is a textbook group-level finding. Reproduced at face value it holds — the group hub map lands squarely in association/default cortex. The un-cued judgement is that this group hub map, however reliable, describes almost no single individual (the aggregation axis, which no shipped task covers): the agent is asked to reproduce a famous result, computes it correctly, and fails only if it does not *volunteer* the group-vs-individual check the instruction never mentions.

### The reproduction and the trap (validated) — held privately

The specific group hubs, the association-cortex fractions, the group-map reliability, and the group-vs-individual agreement numbers are in the **private, git-ignored `calibration.md`** (rule 4: public repo + agents have internet). In brief: the group weighted-degree hub map reproduces Buckner (top hubs = the canonical default/association regions; the top-10 hubs over-represent association cortex relative to the atlas base rate). That group map is **highly reliable** (split-half r ≈ 0.99) **yet describes individuals poorly** — a typical individual's whole-brain hub profile has only a moderate rank correlation with the group profile, shares only ~1–2 of the group's 5 hubs, and overlaps the group top-10 weakly. The divergence is real inter-individual variation in hub topography (the group map is reliable), not measurement noise. The honest answer volunteers this; a confident "the hubs are mPFC/PCC/IPL" over-generalises the average to every subject. The instruction is un-cued: it names the reproduction and the method in full, but **never mentions individual variability, per-subject analysis, reliability, aggregation, or generalisation**.

### Maintainer repair (#4) applied

The earlier build mislabelled the centrality measure (the oracle's `hubs.json`/`run_metadata.json` said "binary degree at 10% density" while it actually computed weighted node strength). This rebuild **measures hub-ness consistently** — weighted node strength (sum of a node's positive connections) — for the group map **and** every individual map, and states it that way everywhere. It also **tests individual-level reliability directly**: the oracle reports the group-vs-individual agreement (mean rank correlation of node-strength profiles and top-hub overlap) alongside the group-map split-half reliability, so the trap ("group-mean hub identity does not describe individuals") is quantified, not asserted.

### Verifier (2 plain checks)

`tests/test_outputs.py`: (1) `test_hubs_computed` — validates the actual data: a list of real Dosenbach-160 group hub **node indices** (≥3 distinct, in [0,159]), a plausible subject count, and — if a group-map reliability *and* an individual-agreement number are both reported — that the reliability genuinely **exceeds** the individual agreement (the aggregation gap; a fabricator who inflates individual agreement to match the reliability collapses this gap and fails). (2) `test_recognises_individual_variability` — `findings.md` recognises that the group hubs do **not** describe individuals (hub organisation varies across individuals, beyond within-subject noise) — **not** a flat "the hubs are regions X," and **not** a dismissal that cites the same overlap numbers and calls them "good reproducibility." The recognition must LINK individual variability to the hub/group result (a bare mention of "individual subjects" does not count).

**Discrimination (validated locally, offline):**

| solution | verdict |
|---|---|
| reference (reproduces Buckner, then volunteers the reliable group hubs fit almost no individual) | **PASS — reward 1.0** |
| genuine paraphrase (hub topography idiosyncratic / differs person-to-person; ± split-half reliability) | **PASS** |
| flat "the hubs are mFC/PCC/mPFC, 80% association cortex" (no aggregation) | **FAIL** (recognition) |
| dismissal: cites the real 0.26/0.41 and calls it "good reproducibility / generalises fine" | **FAIL** (recognition) |
| fabricated: out-of-range hub node ids | **FAIL** (data) |
| fabricated: reliability ≈ individual agreement (collapsed aggregation gap) | **FAIL** (data) |
| empty dir | **FAIL** |

### Difficulty — PENDING the frontier gate (harbor + GPT-5.5 / Claude, k≥3 each)

Oracle **reward 1.0** (offline, run by maintainer). Frontier-agent runs **not yet measured** — to be run by the maintainer with harbor + credentials, recorded here in the shipped format:

| agent | runs | reward | what it did |
|---|---|---|---|
| **GPT-5.5 (codex, xhigh)** | _k≥3_ | _pending_ | _pending_ |
| **Claude Opus 4.8** | _k≥3_ | _pending_ | _pending_ |

**Expected failure mode (hypothesis, to be confirmed by the gate):** both families compute the group hub map correctly and reproduce Buckner's association-cortex result, but — un-cued — do **not** volunteer the group-vs-individual check that shows the reliable group map describes almost no single subject. Telegraphing is likely LOW: "does this group hub result hold for individuals?" is a subtle check agents rarely raise un-cued. This mirrors the measured behaviour on DEVCONN-001 (motion) and SOCIALBRAIN-001 (GSR), where both frontier families computed correctly yet failed to volunteer the single hidden check.

**Verifier-integrity note (the skill's inspect-real-outputs lesson).** The recognition check is negation-aware and downgrade-driven: it requires the honest CONCLUSION coupled to the hub/group result (e.g. "hub topography varies across individuals," "the group map generalises poorly," "over-generalises the average"), and rejects a dismissal that reports the same overlap value or the "1.5 of 5" count and mislabels it "good reproducibility" — merely citing the number is not a coupled downgrade, so it will not false-pass, without a fragile "genuine"-veto. Harden further against the real GPT/Claude texts at gate calibration.

### Cost

`hard`. cpus 2, mem 8 GB, **internet off** (`allow_internet=false`) — the task ships a packaged offline connectome bundle (`data/dos160_hubmap.npz`, ~22 MB: 946 subjects × 12,720 Fisher-z Dosenbach-160 edges float16 + `dx` + the atlas network/label/coord arrays), built from the shared build-only timeseries bundle by `data/build_hubmap.py`. The oracle reads only that npz (numpy-only; no nilearn/network). Deps as pinned in `environment/Dockerfile` (numpy/scipy/pandas/nibabel/nilearn). Timeouts generous (per-subject node strength over 160 ROIs × ~488 controls).
