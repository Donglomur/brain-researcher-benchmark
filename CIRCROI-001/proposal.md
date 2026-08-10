## CIRCROI-001

**Proposal Title:** Characterise a localized gray-matter sex difference (OASIS VBM) — an un-cued circular-inference / double-dipping trap (the *circularity / non-independence* failure axis)

**Scientific Domain:** Life Sciences · **Field:** Neuroscience · **Subfield:** Structural neuroimaging / VBM

**Source paper (landscape):** the standard VBM "localize where gray matter differs most, report the strength there" analysis; dataset from the OASIS cross-sectional cohort (Marcus et al., 2007, *J. Cognitive Neuroscience*, https://doi.org/10.1162/jocn.2007.19.9.1498) via `nilearn.datasets.fetch_oasis_vbm`. Circularity critique: Kriegeskorte et al. (2009), *Nature Neuroscience*, https://doi.org/10.1038/nn.2303 ("Circular analysis in systems neuroscience: the dangers of double dipping"); Vul et al. (2009) (non-independence / "voodoo correlations").

**Status: FULL runnable task, built with the `tb-science-task-authoring` skill.** Rigor genre (characterise the localized difference → the honest answer volunteers the estimate is circular — GRADIENT-style), on the **circularity / non-independence** axis (the statistical-inference family), on a structural VBM cohort.

### Why this exists

Localizing the region with the largest group difference and then testing that same difference on the **same** subjects is non-independent ("circular" / "double dipping"): the selection guarantees an inflated, often "significant" effect even when there is none. Reproduced at face value the analysis returns a "significant" localized sex difference in gray matter after head-size control. The un-cued judgement is that the select-then-test-on-the-same-data step is circular, so the effect must be estimated on independent data (split-half / cross-validation) or against a permutation null. The honest answer volunteers the circularity; a confident "significant localized sex difference (p≈4e-4)" over-states the evidence.

### The face-value finding (Step-0 validated) — a "significant" localized sex difference

OASIS VBM, 150 subjects, gray matter residualized on eTIV (head size): localizing the peak sex-difference region and testing it returns **p ≈ 4e-4** — apparently a significant, regionally specific sex difference beyond overall head size. This is the finding as usually reported.

### The trap (Step-0 validated) — the "significance" is circular

OASIS VBM, 150 subjects, eTIV-residualized:

| test | result | verdict |
|---|---|---|
| **circular** (localize peak sex-difference region, test on **same** subjects) | **p ≈ 4e-4** | apparently significant |
| **honest** split-half (localize on one half, test on the other) | median **p ≈ 0.5** | not significant |
| **permuted-grouping null** (labels shuffled, no true difference) | circular procedure returns p<0.05 in **≈ 89%** of runs | nominal should be 5% |

After controlling for head size the overall sex difference is ~null, yet the circular procedure manufactures a "significant" regional effect because the region was chosen *because* it differed and then tested on the same data — under a shuffled-label null it fabricates significance ~89% of the time (nominal 5%). The honest split-half shows no reliable localized sex difference. The instruction is un-cued: it asks plainly to localize the peak sex-difference region and report its significance, but **never mentions circularity, double dipping, non-independence, selection bias, split-half, cross-validation, or a permutation null**.

**Honesty note (no-fake-traps discipline, from Step-0).** This is distinct from a whole-brain / aggregation-method effect: here the inflation is purely a *selection* artifact, and it persists even after correcting the selection step's multiple comparisons — because the *inference* reuses the *selection* data. The trap was validated three ways (circular p, honest split-half p, permuted-null false-positive rate), not asserted, so the honest conclusion ("no reliable localized sex difference; the circular estimate over-states the evidence") is grounded.

### Verifier (2 plain checks)

`tests/test_outputs.py`: (1) `test_roi_computed` — a region / significance result is present in `*.json`; (2) `test_recognises_circularity` — `findings.md` recognises that selecting the region by the effect and testing it on the **same** subjects is circular / double dipping / non-independent, and that independent data (split-half / cross-validation) or a permutation null is required — NOT a flat "significant localized sex difference (p=4e-4)", and NOT conceding "circular selection can inflate in principle" then reporting the inflated estimate as real. The recognition must name the circularity / non-independence / selection-bias issue, coupled to the honest conclusion.

**Discrimination (validated locally):**

| solution | computed | recognises_circularity | verdict |
|---|---|---|---|
| **oracle** (circular p vs honest split-half vs permuted null) | PASS | PASS | **PASS** — reward 1.0 |
| correct (names double-dipping, needs independent selection) | PASS | PASS | **PASS** |
| flat "significant localized sex difference (p=4e-4)" | PASS | **FAIL** | **FAIL** |
| "circular can inflate in principle, but the effect is real" (concede-then-affirm) | PASS | **FAIL** | **FAIL** |
| broken (no result) | **FAIL** | — | **FAIL** |

### Difficulty — PENDING the frontier gate (harbor + GPT-5.5 / Claude, k≥3 each)

Oracle **reward 1.0** (in-container, run by maintainer). Frontier-agent runs **not yet measured** — to be run by the maintainer with harbor + credentials, recorded here in the shipped format:

| agent | runs | reward | what it did |
|---|---|---|---|
| **GPT-5.5 (codex, xhigh)** | _k≥3_ | _pending_ | _pending_ |
| **Claude Opus 4.8** | _k≥3_ | _pending_ | _pending_ |

**Expected failure mode (hypothesis, to be confirmed by the gate):** an agent localizes the peak sex-difference region, tests it on the same subjects, and reports the circular p≈4e-4 as a significant localized sex difference — without volunteering that select-then-test-on-the-same-data is circular and that the honest split-half is null. **Telegraphing risk:** double dipping is a famous pitfall a strong agent may flag reflexively → possible easy control. The gate decides.

**Verifier-integrity note (the skill's inspect-real-outputs lesson).** The recognition check is negation-aware and downgrade-driven: it requires the honest CONCLUSION (the estimate is an artifact of the selection / biased upward / the clean out-of-sample estimate is much weaker / no reliable effect), and the mild concession vocabulary ("can inflate in principle", "tends to exaggerate", "could overstate") is deliberately NOT treated as a downgrade — so a concede-then-affirm dismissal ("circular selection can inflate estimates, but here the effect is strong and real") fails WITHOUT a fragile "genuine"-veto, and merely naming a moderate correlation does not pass. Harden further against the real GPT/Claude texts at gate calibration.

### Cost

`hard`. cpus 2, mem 8 GB, internet on (downloads OASIS VBM gray-matter maps at runtime; cached afterwards). Deps: nilearn 0.12.1 + numpy/scipy/pandas/nibabel.
