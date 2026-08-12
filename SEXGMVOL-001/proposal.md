## SEXGMVOL-001

**Proposal Title:** Sex difference in gray-matter volume (OASIS VBM) — wrong-cause / head-size-confound axis, structural modality (answer + numbers in private calibration.md)

**Scientific Domain:** Life Sciences · **Field:** Neuroscience · **Subfield:** Structural MRI / voxel-based morphometry

**Source paper:** Ruigrok et al. (2014), *Neuroscience & Biobehavioral Reviews*, https://doi.org/10.1016/j.neubiorev.2013.12.004 (meta-analysis: males have larger absolute brain volumes, including total gray matter — the finding being reproduced). The un-cued lever is a **head-size confound**: men have systematically larger intracranial volume (eTIV), so a raw gray-matter sex difference is confounded by head size, and it does not survive a principled head-size adjustment (Barnes et al. 2010, *NeuroImage*, argue the covariate/ANCOVA adjustment is the appropriate correction). Data: `nilearn.datasets.fetch_oasis_vbm`.

**Status: FULL runnable task, built with `tb-science-task-authoring`.** Reproduce-the-headline → reveal-the-hidden-confound genre, modelled on GMATROPHY-001 / DEVCONN-001 / SOCIALBRAIN-001. Structural-MRI modality. The failure axis (**wrong-cause / confound**) is shipped (DEVCONN motion, SOCIALBRAIN GSR); here on the structural modality with a **head-size (eTIV)** lever.

### Why this exists

"Men have more gray matter" reads like a settled structural finding, and the most natural analysis — sum each subject's modulated GM map and compare sexes — returns a confident male advantage. The un-cued judgement is that men have larger heads, so the raw difference is a **head-size confound**: after adjusting for intracranial volume the male advantage does not survive (it reverses), so there is no robust male GM advantage independent of head size. The agent computes the raw sex difference correctly and fails only if it does not *volunteer* the head-size confound the instruction never mentions.

### The face-value result and the trap (validated) — held privately

The specific sample, the reproduced direction, the eTIV-adjusted estimand, the reversal, and the validated numbers (n, Cohen d, t, p) are in the **private, git-ignored `calibration.md`** (rule 4: public repo + agents have internet). In brief: the raw "men have more gray matter" result reproduces, but it is confounded by head size and **does not survive the head-size adjustment** — a single raw claim over-states. The instruction is un-cued: it names the reproduction and the method in full, but **never mentions head size, intracranial volume / eTIV, proportions, or ANCOVA.**

**Maintainer repair (#20) applied.** (1) Missing CDR is **not** coerced to healthy controls — in OASIS-1 the missing-CDR subjects are un-assessed young adults; the oracle **excludes** them and analyses the confirmed-healthy CDR==0 cohort. (2) ONE consistent eTIV-adjusted estimand is defined and used throughout (the **sex coefficient in ANCOVA `GM ~ sex + eTIV`**); proportion GM/eTIV is reported only as a same-direction corroboration, not as a co-equal "third method." The trap is now cleanly: the raw male advantage **reverses/nulls after head-size (eTIV) adjustment.**

**Honest caveats / open risks.** (1) The head-size confound is well known in morphometry, so a strong agent may adjust for it un-cued → possible easy control; the gate decides. (2) Confound axis reused (after DEVCONN + SOCIALBRAIN) — but on a **new modality** (structural) with a **new lever** (head size / eTIV), a fresh axis×modality cell. (3) Elderly-skewed sample after the CDR==0 restriction (age 33–94) — a defensible "confirmed-healthy" cohort; the reversal is robust within it.

### Verifier (2 plain checks, validate the actual data)

`tests/test_outputs.py`: (1) `test_sex_difference_computed` — validates the **actual data**: real M/F sex labels, a sane subject count, a plausible RAW male advantage, no absurd magnitudes, and — where a head-size-adjusted effect is reported — that it is **reversed (F>M / null)**, not a fabricated still-male-after-adjustment; the per-subject `gm_subjects.csv`, if present, must show mean GM larger in men (raw reproduction) **and** mean eTIV larger in men (the confound). (2) `test_recognises_headsize_dependence` — passes on a genuine **raw-M>F + adjusted-F>M** reversal in the structured data, else requires `findings.md` to couple **head size / eTIV** to a downgrade (confounded by head size / does not survive adjustment / reverses / no robust male advantage / over-states). A flat single-method "men have more GM," a bare "results varied," or a dismissal that concedes the flip then picks a winner does not pass.

**Discrimination (validated locally):**

| output | data test | recognition |
|---|---|---|
| **oracle** (raw M>F + eTIV-adjusted F>M + confound prose) | PASS | PASS — reward 1.0 |
| empty | **FAIL** | FAIL |
| naive (real raw M>F numbers, no head-size recognition) | PASS | **FAIL** |
| fabricated — adjusted claimed still M>F (hidden-check wrong direction) | **FAIL** | (prose passes) |
| fabricated — fake labels / implausible values | **FAIL** | (prose passes) |
| concedes the flip then picks a winner ("raw is correct → men have more") | PASS | **FAIL** |

### Difficulty — PENDING the frontier gate (harbor + GPT-5.5 / Claude, k≥3 each)

Oracle **reward 1.0** (local, cached OASIS; in-container run by maintainer). Frontier-agent runs **not yet measured** — to be run by the maintainer with harbor + credentials, recorded here in the shipped format:

| agent | runs | reward | what it did |
|---|---|---|---|
| **GPT-5.5 (codex, xhigh)** | _k≥3_ | _pending_ | _pending_ |
| **Claude Opus 4.8** | _k≥3_ | _pending_ | _pending_ |

**Expected failure mode (hypothesis, to be confirmed by the gate):** both families compute the raw sex difference correctly and report "men have more gray matter," but — un-cued — do **not** volunteer that men have larger heads, that the effect does not survive head-size (eTIV) adjustment (it reverses to F>M), and that there is therefore no robust male GM advantage independent of head size. This mirrors the measured behaviour on DEVCONN-001 (motion) and SOCIALBRAIN-001 (GSR).

**Verifier-integrity note (the skill's inspect-real-outputs lesson).** The recognition check is negation-aware and downgrade-driven: it requires the head-size concept coupled to a non-robustness downgrade (confounded / does-not-survive / reverses / no-robust-male-advantage / over-states), or an intrinsic "no robust male advantage independent of head size" phrase, and rejects a dismissal that name-drops eTIV then affirms a single robust winner — so a bare mention will not false-pass, and the honest oracle still passes. The data check independently fails empty/naive-structured/fabricated by validating the emitted per-subject and per-estimand numbers. Harden further against the real GPT/Claude texts at gate calibration.

### Cost

`hard`. cpus 2, mem 8 GB, internet on (OASIS VBM via nilearn `fetch_oasis_vbm` — downloads then cached). Deps: nilearn 0.12.1 + nibabel/scipy/pandas/numpy (Welch t-tests / lstsq ANCOVA — no extra deps). Oracle runtime a few min (reads 403 modulated GM maps).
