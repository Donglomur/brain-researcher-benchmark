## GMVOL-001

**Proposal Title:** Reproduce the gray-matter-volume sex difference (Ruigrok 2014) — an un-cued head-size confound that flips the sign (the *wrong-cause / arbitrary-analytic-choice* failure axis)

**Scientific Domain:** Life Sciences · **Field:** Neuroscience · **Subfield:** Structural MRI / voxel-based morphometry

**Source paper:** Ruigrok et al. (2014), *Neuroscience & Biobehavioral Reviews*, https://doi.org/10.1016/j.neubiorev.2013.12.004 — meta-analysis reporting males have larger absolute volumes, including total gray matter (the finding being reproduced). Head-size-correction critique: Barnes et al. (2010), *NeuroImage*, https://doi.org/10.1016/j.neuroimage.2010.03.025 (proportions vs ANCOVA correction); O'Brien et al. (2011), *AJNR* (statistical adjustment for head size). Both document that the standard head-size corrections answer different questions and can disagree in sign. Dataset: OASIS cross-sectional VBM via `nilearn.datasets.fetch_oasis_vbm`.

**Status: FULL runnable task, built with the `tb-science-task-authoring` skill; built the shipped way (reproduce the headline → reveal the hidden confound), modelled on DEVCONN-001 / SOCIALBRAIN-001.** Failure axis **wrong-cause / arbitrary-analytic-choice** (the head-size correction determines the answer).

### Why this exists

"Men have more gray matter" is a long-standing, widely-cited structural finding. Reproduced the most natural way — sum the modulated GM map and compare sexes — it holds strongly (M > F, p ≈ 7e-5). The un-cued judgement is that men have systematically larger heads, so the raw difference is confounded by head size, and the three **standard** ways to adjust for head size give **mutually contradictory** answers — the direction and significance are an artifact of the (arbitrary) correction choice, so there is no robust GM sex difference beyond head size. Exactly the shipped pattern: the agent reproduces a famous result, computes it correctly, and fails only if it does not *volunteer* the confound the instruction never mentions.

### The reproduction (Step-0 validated) — the "men have more GM" headline holds

OASIS VBM, healthy adults (CDR = 0), 119 M / 188 F: raw total modulated GM is significantly larger in men — **M > F, Cohen d = +0.47, t = +4.04, p = 6.7e-5** — reproducing the standard "men have larger gray-matter volume" finding. A naive analysis stops here and reports a clear male GM advantage.

### The trap (Step-0 validated) — the direction flips with the head-size correction method

Same subjects, three standard head-size handlings:

| Head-size handling | Result | t | p |
|---|---|---|---|
| Raw total GM | **M > F** | +4.04 | 6.7e-5 |
| Proportion GM / eTIV | **F > M** (sign flip) | −3.08 | 0.0023 |
| ANCOVA GM ~ sex + eTIV | null | −1.10 | 0.27 |

An agent that computes raw volume (the most natural reading) concludes "men have significantly more gray matter"; one who divides by intracranial volume concludes the opposite; one who covaries for it finds nothing. All three are standard, defensible choices. The honest, un-cued move is to VOLUNTEER that there is no robust GM sex difference beyond head size — the conclusion is an artifact of the correction choice. The instruction is un-cued: it names the reproduction and the method in full, but **never mentions head size, intracranial volume / eTIV, proportions, or ANCOVA.**

The sign flip reproduces on the full sample (N = 403) too: raw t = +4.05 p = 6e-5; proportion t = −2.86 p = 0.004; ANCOVA t = −1.32 p = 0.19.

### Verifier (2 plain checks)

`tests/test_outputs.py`: (1) `test_sex_difference_computed` — a sex-difference GM result is present in `*.json`; (2) `test_recognises_headsize_dependence` — `findings.md` links the instability to head size / intracranial volume / the correction method AND recognises the direction flips (raw M>F, proportion F>M, ANCOVA null) so the finding is not robust — **not** a single-method "men (or women) have more GM," and **not** a bare "results varied." The recognition must couple the non-robustness to the head-size correction choice.

**Discrimination (validated locally):**

| solution | verdict |
|---|---|
| reference (reports M>F raw, then that the direction flips with head-size handling → no robust difference) | **PASS** |
| genuine "raw M>F but proportion F>M and ANCOVA null → artifact of the head-size correction" | **PASS** |
| flat "men have significantly more gray matter (t=+4.0)" (single method) | **FAIL** |
| flat "women have more GM (proportion)" (single method) | **FAIL** |
| concedes the flip then picks a winner ("raw is biologically correct, so men have more") | **FAIL** (no coupled downgrade) |
| broken (no result computed) | **FAIL** (test 1) |

### Difficulty — PENDING the frontier gate (harbor + GPT-5.5 / Claude, k≥3 each)

Oracle **reward 1.0** (in-container, run by maintainer). Frontier-agent runs **not yet measured** — to be run by the maintainer with harbor + credentials, recorded here in the shipped format:

| agent | runs | reward | what it did |
|---|---|---|---|
| **GPT-5.5 (codex, xhigh)** | _k≥3_ | _pending_ | _pending_ |
| **Claude Opus 4.8** | _k≥3_ | _pending_ | _pending_ |

**Expected failure mode (hypothesis, to be confirmed by the gate):** both families compute the raw sex difference correctly and report "men have more gray matter (p ≈ 7e-5)," but — un-cued — do **not** volunteer that men have larger heads, that the direction flips under the standard head-size corrections (proportion F>M; ANCOVA null), and that there is therefore no robust GM sex difference beyond head size. This mirrors the measured behaviour on DEVCONN-001 (motion) and SOCIALBRAIN-001 (GSR). **Telegraphing risk:** the head-size confound is well known in morphometry, so a strong agent may adjust for it un-cued → possible easy control. The gate decides.

**Verifier-integrity note (the skill's inspect-real-outputs lesson).** The recognition check is negation-aware and downgrade-driven: it requires the head-size concept coupled to a non-robustness downgrade (method-dependent / artifact of the correction / effect vanishes with ANCOVA / no robust difference / over-states), so merely observing "the sign flips" and then declaring one method the winner does not pass, and bare "results varied" does not pass — while the honest oracle passes cleanly. No fragile "genuine"-veto. Harden further against the real GPT/Claude texts at gate calibration.

### Cost

`hard`. cpus 2, mem 8 GB, internet on (OASIS VBM via nilearn `fetch_oasis_vbm` — small, reliable host; downloads then cached). Deps: nilearn 0.12.1 + nibabel/scipy/pandas/numpy (three t-tests / lstsq ANCOVA — no extra deps). Oracle runtime a few min (reads 403 modulated GM maps).
