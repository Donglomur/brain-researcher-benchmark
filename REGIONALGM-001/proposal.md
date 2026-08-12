## REGIONALGM-001

**Proposal Title:** Characterise a localized gray-matter sex difference (OASIS VBM) — un-cued circular-inference / double-dipping trap, structural modality (answer + numbers in private calibration.md)

**Scientific Domain:** Life Sciences · **Field:** Neuroscience · **Subfield:** Structural neuroimaging / VBM

**Source paper (landscape):** the standard VBM "localize where gray matter differs most, report the strength there" analysis; dataset from the OASIS cross-sectional cohort (Marcus et al., 2007, *J. Cognitive Neuroscience*, https://doi.org/10.1162/jocn.2007.19.9.1498) via `nilearn.datasets.fetch_oasis_vbm`. The un-cued lever is a **non-independence / circularity** one (Kriegeskorte et al. 2009, *Nat. Neuroscience*, "Circular analysis / double dipping"; Vul et al. 2009, "voodoo correlations"): selecting a region by the very contrast you then test — on the **same** subjects — guarantees an inflated, often "significant" effect even when there is none. **Kept out of the instruction.**

**Status: FULL runnable task, built with the `tb-science-task-authoring` skill.** Rigor / characterise genre (modelled on GMATROPHY-001 / GRADIENT-001), on the **circularity / non-independence** failure axis (the statistical-inference family), on a structural VBM cohort. Route-a: voxel data too big to package, so `allow_internet=true` and the loader fetches OASIS VBM at runtime (cached afterwards → fast reruns).

### Why this exists

"Is there a localized sex difference in gray matter beyond head size?" reads like a well-posed question, and a single-pipeline analysis returns a confident, "significant" localized effect. The un-cued judgement is that the significance is an **artifact of selecting and testing on the same subjects** (circular / double dipping): estimated honestly on independent data (split-half / cross-validation) or against a permutation null, the localized sex difference collapses. The agent computes the localized difference correctly and fails only if it does not *volunteer* the non-independence check the instruction never mentions.

### The face-value result and the trap (validated) — held privately

The circular p-value / effect size, the honest split-half estimate, the permuted-null false-positive rate, and the subject/voxel counts are in the **private, git-ignored `calibration.md`** (rule 4: public repo + agents have internet). In brief: reproduced at face value the analysis returns a "significant" localized sex difference after head-size control; but the same-data selection-then-test step is circular, so an honest split-half is non-significant and a shuffled-label null shows the procedure manufactures significance the large majority of the time. The instruction is un-cued (it never says circularity, double dipping, non-independence, selection bias, split-half, cross-validation, or permutation null).

**Honesty note (no-fake-traps discipline).** This is a pure *selection* artifact, not a whole-brain / aggregation-method effect: it persists even after correcting the selection step's multiple comparisons, because the *inference* reuses the *selection* data. The trap was validated three ways (circular p, honest split-half p, permuted-null false-positive rate), not asserted, so the honest conclusion ("no reliable localized sex difference; the circular estimate over-states the evidence") is grounded.

### Verifier (2 plain checks, data-validating)

`tests/test_outputs.py`: (1) `test_roi_computed` — validates the **actual data**: a significance (p-value) result is present, `n_subjects` is sane, and — where the oracle's per-subject / per-split tables or the honest/null numbers are present — the sex labels are real (M/F), eTIV is plausible, the honest/split-half estimate goes in the **collapse** direction (larger, non-significant vs the circular p) and any reported null false-positive rate is elevated above nominal. Empty / fabricated (fake labels, implausible values, hidden-check in the wrong direction) fails. (2) `test_recognises_circularity` — `findings.md` recognises that selecting the region by the sex difference and testing it on the **same** subjects is circular / double dipping / non-independent and that independent data (split-half / cross-validation) or a permutation null is required — NOT a flat "significant localized sex difference", and NOT a concede-then-affirm ("circular can inflate in principle, but the effect is real").

**Discrimination (validated locally):**

| output | roi_computed (data) | recognises_circularity | verdict |
|---|---|---|---|
| **oracle** (circular vs honest split-half vs permuted null) | PASS | PASS | **PASS** — reward 1.0 |
| correct (names double-dipping, needs independent selection) | PASS | PASS | **PASS** |
| flat "significant localized sex difference" (real numbers) | PASS | **FAIL** | **FAIL** |
| concede-then-affirm ("can inflate in principle, but real") | PASS | **FAIL** | **FAIL** |
| fabricated (fake labels / implausible eTIV / honest p wrong direction) | **FAIL** | — | **FAIL** |
| broken (no result) | **FAIL** | — | **FAIL** |

### Difficulty — PENDING the frontier gate (harbor + GPT-5.5 / Claude, k≥3 each)

Oracle **reward 1.0** (local, cached OASIS). Frontier-agent runs **not yet measured** — to be run by the maintainer with harbor + credentials, recorded here in the shipped format:

| agent | runs | reward | what it did |
|---|---|---|---|
| **GPT-5.5 (codex, xhigh)** | _k≥3_ | _pending_ | _pending_ |
| **Claude Opus 4.8** | _k≥3_ | _pending_ | _pending_ |

**Expected failure mode (hypothesis, to be confirmed by the gate):** an agent localizes the peak sex-difference region, tests it on the same subjects, and reports the circular result as a significant localized sex difference — without volunteering that select-then-test-on-the-same-data is circular and that the honest split-half is null. **Telegraphing risk:** double dipping is a famous pitfall a strong agent may flag reflexively → possible easy control. The gate decides.

**Verifier-integrity note (the skill's inspect-real-outputs lesson).** The recognition check is negation-aware and downgrade-driven: it requires the circularity / non-independence concept COUPLED to the honest conclusion (the estimate is an artifact of the selection / biased upward / the clean out-of-sample estimate collapses / the null fabricates significance / no reliable effect), and the mild concession vocabulary ("can inflate in principle", "tends to exaggerate", "could overstate") is deliberately NOT treated as a downgrade — so a concede-then-affirm dismissal fails WITHOUT a fragile "genuine"-veto, and merely naming a moderate effect does not pass. The data check independently rejects fabricated labels / implausible values / a wrong-direction hidden check. Harden further against the real GPT/Claude texts at gate calibration.

### Cost

`hard`. cpus 2, mem 8 GB, internet on (route-a: downloads OASIS VBM gray-matter maps at runtime — ~900 MB one-time from NITRC; cached afterwards, so reruns are fast; oracle ~20 s cached). Deps: nilearn 0.12.1 + numpy/scipy/pandas/nibabel.
