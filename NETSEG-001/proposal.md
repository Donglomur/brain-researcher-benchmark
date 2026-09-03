## NETSEG-001

**Proposal Title:** Quantify functional-network **system segregation** in a developmental movie-watching cohort — an un-cued **anti-correlation (negative-edge) handling** judgement (robustness / reporting-quality axis)

**Scientific Domain:** Life Sciences · **Field:** Neuroscience · **Subfield:** Resting/naturalistic fMRI connectivity / graph analysis

**Source finding:** system segregation of cortical functional networks (Chan et al., 2014, *PNAS*, 10.1073/pnas.1415122111) computed on the nilearn **developmental fMRI** sample (Richardson et al., 2018, *Nat Commun*; children + adults watching a short film), parcellated with **Schaefer-2018 100/7**. Both fetched at runtime by nilearn (open, no credentials).

**Status: FULL runnable task.** New on three axes vs the shipped connectivity suite: **dataset** (`fetch_development_fmri` — the ABIDE-heavy suite and NETINTEG's `fetch_adhd` do not use it), **metric** (**system segregation**, a within-vs-between-network ratio — not global efficiency (NETINTEG), community modularity (NETMODULES), edge strength (NETSTRENGTH) or sliding-window dFC (DYNFC/DYNCONN)), and **un-cued lever** (handling of **anti-correlations / negative edges** — distinct from NETINTEG's absolute-vs-proportional density thresholding). Genre: **reproduction** (report the defined segregation value), distinct from NETINTEG's over-claim/convention-dependence genre. Deliverable option taken: a **static graph metric with a new lever** (the brief permits this).

### Why this exists (new axis: negative-edge handling)

System segregation, S = (mean_within − mean_between) / mean_within, is a **convention-invariant ratio** — no absolute connectivity magnitude survives it — and a canonical developmental measure. It is **defined on the positive edges**: anti-correlations (which sit predominantly *between* networks, e.g. default vs dorsal-attention) are set aside. A naive analyst keeps all edges; the negatives drag `mean_between` negative and **inflate S by ~half**. The choice is genuinely off the critical path — the naive computation "works" and returns a plausible, even more segregated-looking number.

### Step-0 (validated, real — reproduces on obtainable data)

Fetched `fetch_development_fmri(n_subjects=40)` + `fetch_atlas_schaefer_2018(100, 7)`; per participant, extracted 100 parcel series with the provided confounds regressed + detrend + z-score, formed Fisher-z Pearson connectomes, and computed system segregation on the 7-network partition:

- **Cohort-mean segregation = 0.374** (SD 0.09), **children 0.347**, **adults 0.468** — i.e. network segregation is higher in adults, reproducing the maturation of system segregation.

### The un-cued lever (Step-0 measured — LARGE and robust in direction)

Cohort-mean segregation under each analytic choice (40 participants, confounds regressed):

| edge handling | cohort-mean S | vs correct |
|---|---|---|
| **positive edges only** (Chan 2014 — correct) | **0.374** | — |
| **all edges** (anti-correlations kept) | **0.554** | **+48 %** |

The inflation is mechanical (negatives are mostly between-network) and holds across preprocessing: with band-pass, 0.402 (correct) vs 0.646 (naive); no-detrend, 0.352 vs 0.586.

### Well-posedness / preprocessing caveat (no-fake-traps discipline)

The **direction** of the negative-edge lever is robust, but the **absolute** segregation value is preprocessing-sensitive (chiefly whether confounds are regressed: without them the positive-edge value drops to ~0.26 and the all-edges value to ~0.31). So — as NETINTEG pins the atlas — this task **pins the substrate that must be fixed for the quantity to be well-defined**: the dataset (40 subjects), the atlas (Schaefer 100/7), confound regression, detrend, and z-scoring are stated in `instruction.md`. With those fixed, the **only** un-cued analytic judgement is the anti-correlation handling, and it alone moves S from 0.37 to 0.55. The confound-and-atlas pinning is well-posedness, not a hint about the lever (the edge-sign handling is never named).

### Verifier (3 plain checks, human-looking pytest)

`tests/test_outputs.py`: (1) per-participant segregation present for the ~40-participant cohort, plausible range, varies across subjects, and a within-vs-between-network segregation analysis named; (2) **reproduction** — cohort-mean segregation in the validated band **[0.32, 0.47]**; (3) **explicit edge-sign DISCLOSURE** — the write-up must state how the anti-correlations / negative edges were handled (positive edges only / anti-correlations set aside / negatives thresholded to zero / |r|), co-occurring with a reported segregation value.

**Hardening (this pass, per the tb-science audit — "require an explicit edge-sign robustness disclosure graded as the over-claim; else control").** Check 3 previously accepted the *trivial within/between wording that every segregation description contains* (`within-network`, `between-network`, `mean_within`, …) — so a silent all-edges run passed it, leaving the negative-edge lever gated by the numeric band alone. Check 3 now **drops that escape** and requires a genuine edge-sign disclosure (unambiguous handling of the correlation sign). The over-claim — silently keeping the anti-correlations and reporting the inflated ~0.55 as "system segregation" — now fails BOTH the band and the disclosure; a defensible positive-edge answer that names its edge handling passes both. The reference solution already emits this disclosure (findings.md "Edge-sign handling" section + run_metadata `edge_handling` / `metric: …positive-edge`).

**Offline discrimination (re-validated against the hardened grader):**

| output | seg value | band | disclosure | verdict |
|---|---|---|---|---|
| reference / oracle (positive-edge, confounds; real nilearn run) | 0.374 | PASS | PASS | **PASS 3/3** |
| defensible-alt (positive-edge ~0.40, "negatives clipped to zero") | 0.40 | PASS | PASS | **PASS 3/3** |
| naive (all edges kept, no edge-sign disclosure) | 0.55 | **FAIL** | **FAIL** | **FAIL** |
| over-claim ("strongly segregated", 0.56, no disclosure) | 0.56 | **FAIL** | **FAIL** | **FAIL** |
| hedge (all edges 0.55, discloses it kept anti-correlations) | 0.55 | **FAIL** | pass | **FAIL** (band) |
| terse-correct (positive-edge 0.37, no edge-sign disclosure) | 0.37 | PASS | **FAIL** | **FAIL** (disclosure gate bites) |

### Difficulty — NOT yet gated (frontier runs pending)

Oracle passes (reward 1.0; re-run on the real nilearn data this pass, cohort-mean 0.374). The all-edges naive outputs fail as tabulated. The **≥2-frontier-family, k≥3 difficulty gate has not been run** (no Harbor/agent access in this authoring session) — recorded as **untested difficulty**. Honest expectation: an agent that computes segregation with all edges (a very common default) lands ~50% high AND omits the edge-sign disclosure — failing on both the band and the honesty gate; one that applies the positive-edge definition and names it passes. The strengthened disclosure gate means an agent must now *volunteer* the negative-edge handling (the un-cued metacognitive step), not merely land near the right number. If frontier agents pass easily, the ratchet is to move to a signed/weighted segregation variant or add a second (thresholding) lever, not to add rigor.

### Data provenance / reliability caveats

- nilearn `fetch_development_fmri` (Richardson 2018) and `fetch_atlas_schaefer_2018` — open, no credentials; downloaded at runtime and cached. Movie-watching (naturalistic) rather than eyes-closed rest, and used as such (nilearn ships it as the standard connectivity demo cohort).
- 40 participants (31 children, 9 adults). The oracle grades the **cohort mean** (robust); per-participant segregation is reported for the spread and the child/adult contrast.

### Cost

`hard` bracket; light in practice (40 BOLD runs, one labels-masker extraction each; segregation is closed-form). cpus 2, mem 8 GB, internet on, timeouts 1800–3600 s. Deps: numpy 2.1.3 / scipy 1.14.1 / pandas 2.2.3 / nibabel 5.3.2 / scikit-learn 1.5.2 / nilearn 0.12.1.
