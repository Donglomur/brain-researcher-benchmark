## VBMAGE-001

**Proposal Title:** Strongest age-related cortical atrophy (OASIS VBM) — an un-cued smoothing-dependent peak (the *over-claim / robustness* axis on a NEW **structural** modality)

**Scientific Domain:** Life Sciences · **Field:** Neuroscience · **Subfield:** Structural MRI / voxel-based morphometry

**Source paper:** Good et al. (2001), *NeuroImage*, https://doi.org/10.1006/nimg.2001.0786 (VBM of ageing — gray-matter loss across the lifespan, and where it is greatest). The un-cued lever is a **researcher-degree-of-freedom** one: spatial smoothing is an arbitrary VBM choice with no single correct value, and the "most-atrophied region" is not stable across defensible kernels (the analytic-flexibility / multiverse critique; **kept out of the instruction**). Data: `nilearn.datasets.fetch_oasis_vbm`.

**Status: FULL runnable task, built with `tb-science-task-authoring`.** Rigor / characterise genre, modelled on GRADIENT-001. **First task on the structural-MRI modality** — the shipped + session suite was fMRI (×7) + EEG (×1); this adds structural, a third measurement type. The failure axis (**over-claim / robustness**) is shipped (GRADIENT, DYNFC), but on a **new modality** with a **new lever** (spatial smoothing) it fills a fresh axis×modality cell.

### Why this exists

"Which cortical region atrophies most with age" reads like a well-posed question, and a single-pipeline analysis returns one confident winner. The un-cued judgement is that the winner is an **artifact of the (arbitrary) spatial-smoothing kernel**: across defensible kernels the top region flips, so a single-region claim is unwarranted. The agent computes the regional gray-matter–age relationship correctly and fails only if it does not *volunteer* the smoothing-robustness check the instruction never mentions.

### The face-value result (Step-0 validated) — a confident single winner

OASIS VBM, Harvard-Oxford cortical, n≈200, regional gray-matter ~ age (Spearman): a single most-atrophied region emerges at any one defensible pipeline (e.g. **precentral gyrus** at heavier smoothing, or **Heschl's gyrus** at native/light smoothing) — a clean, confident-looking answer. A naive analysis stops here and asserts *the* most-atrophied region.

### The trap (Step-0 validated) — the winner flips with the smoothing kernel

The region with the most negative gray-matter–age relationship depends on the smoothing kernel:

| smoothing kernel | top age-atrophy region |
|---|---|
| native / 4 mm | **Heschl's Gyrus** |
| 8 mm / 12 mm | **Precentral Gyrus** |

Across native/4/8/12 mm the top region lands on **2 distinct regions** — the "most-atrophied region" is not stable to the smoothing choice, an arbitrary VBM parameter with no single correct value. The honest, un-cued move is to VOLUNTEER that the top region is not robust to smoothing (report the multiverse, or recognise the non-robustness); a flat "region X atrophies most" over-claims. The instruction is un-cued: it asks plainly to identify the region with the strongest age-related atrophy, but **never mentions smoothing, a kernel/FWHM, a multiverse, or robustness**.

**Honest caveats / open risks.** (1) Moderate flip — 2 distinct top regions across 4 kernels; the smoothing lever is *fair* (no single correct kernel), unlike a "wrong reference," which is why this was preferred over an EEG-reference candidate that had a standard-correct choice (easy-control risk). (2) Over-claim axis reused (3rd, after GRADIENT + DYNFC) — but on a **new modality** (structural) with a **new lever** (smoothing), so it adds an axis×dataset×modality cell.

### Verifier (2 plain checks)

`tests/test_outputs.py`: (1) `test_atrophy_region_computed` — a top age-atrophy region is reported in `*.json`; (2) `test_reports_smoothing_dependence` — the submission either reports a **smoothing multiverse (≥2 kernels with different top regions)** OR `findings.md` recognises the top region is **not robust to the smoothing / analytic choice** — a flat "region X atrophies most" over-claims. Linked-insight guard: the variation words must tie to the region/result (the winner *changes/flips/depends on* the kernel), not merely name the kernel used.

**Discrimination (validated locally, `scratchpad/validate_vbmage.py`):**

| output | region_computed | smoothing_dependence |
|---|---|---|
| **oracle** (multiverse + recognises non-robustness) | PASS | PASS — reward 1.0 |
| prose (recognises non-robustness) | PASS | PASS |
| structured multiverse (≥2 kernels) | PASS | PASS |
| flat "precentral atrophies most" | PASS | **FAIL** |
| broken (no region) | **FAIL** | — |

### Difficulty — PENDING the frontier gate (harbor + GPT-5.5 / Claude, k≥3 each)

Oracle **reward 1.0** (in-container, run by maintainer). Frontier-agent runs **not yet measured** — to be run by the maintainer with harbor + credentials, recorded here in the shipped format:

| agent | runs | reward | what it did |
|---|---|---|---|
| **GPT-5.5 (codex, xhigh)** | _k≥3_ | _pending_ | _pending_ |
| **Claude Opus 4.8** | _k≥3_ | _pending_ | _pending_ |

**Expected failure mode (hypothesis, to be confirmed by the gate):** both families compute the regional gray-matter–age relationship correctly and assert a single most-atrophied region, but — un-cued — do **not** volunteer the smoothing-robustness check (re-run across kernels) that shows the winner flips. GRADIENT-001 already measured this: un-cued, neither frontier family ran the robustness-across-analytic-choices check and both asserted a confident single identity — so on a fresh modality with a smoothing lever it is plausibly hard.

**Verifier-integrity note (the skill's inspect-real-outputs lesson).** The recognition check is negation-aware and downgrade-driven: it requires the smoothing concept COUPLED to a downgrade (the winning region *changes/flips/depends on* the kernel), or an intrinsic "no single robust region" phrase, and rejects a dismissal that name-drops the kernel then affirms a single robust winner ("smoothing does not move the winner"; "precentral wins whichever kernel") without a fragile "genuine"-veto — so a bare kernel mention will not false-pass, and the honest oracle still passes. Harden further against the real GPT/Claude texts at gate calibration.

### Cost

`hard`. cpus 2, mem 8 GB, internet on (OASIS VBM — ~900 MB one-time from NITRC; oracle smooths at 4 kernels, timeout 5400). Deps: nilearn 0.12.1 + numpy/scipy/nibabel (smoothing via `nilearn.image.smooth_img`, regional extraction via `NiftiLabelsMasker` — no extra deps).
