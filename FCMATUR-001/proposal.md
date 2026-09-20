## FCMATUR-001

**Proposal Title:** Functional connectivity and age across the ABIDE sample (CC200) — a multi-site
case study distinguishing the *marginal* connectivity–age association from the *site-conditioned*
one.

**Scientific Domain:** Life Sciences · **Field:** Neuroscience · **Subfield:** Multi-site
resting-state functional connectivity / aggregation & ecological correlation.

**Recut after maintainer review (PR #195).** This is **not** a reproduction of Dosenbach et al.
2010. It is a self-contained **ABIDE CC200 case study** whose graded scientific judgement is
bounded: the small marginal (pooled) connectivity–age association is **site-conditioned** — it is
carried by between-site differences and **attenuates toward null** within sites. The task does
**not** assert that scanner hardware caused the association, and does **not** claim a true null.
`SITE_ID` conflates scanner, protocol and cohort; the data are cross-sectional (one scan per
participant), so nothing here licenses a within-person developmental claim in either direction.

**Dataset:** ABIDE Preprocessed via `nilearn.datasets.fetch_abide_pcp` (cpac, band-pass, no GSR,
`rois_cc200`), `quality_checked=False`. **1035 participants, 20 sites.** Methodological anchor:
Robinson (1950), *Am. Sociol. Rev.*, "Ecological correlations and the behavior of individuals"
(the foundational aggregation / ecological-fallacy paper) — cited as methodology, not as a
reproduction target.

### How each review point is addressed

**(1) "Not a reproduction of Dosenbach; frame as a new ABIDE case study."** Done. Title, category
(`fMRI connectivity / multi-site case study`), `source_paper`, instruction and findings are all
recut as an ABIDE case study. No paper-reproduction claim remains; the Dosenbach citation is gone.

**(2) "Narrower conclusion; report pooled / within / between with uncertainty; add sensitivity
checks; no scanner causality, no true null."** Done. The task now **requires** the agent to report
all three estimates with 95% CIs, and to output five sensitivity checks (motion/QC, diagnosis,
sex, nonlinear age, site-specific slopes). Over-claims are fixed: "reverses/collapses" →
**"attenuates toward null"**; the "no within-site relationship at any site" language is removed.
The oracle `findings.md` states explicitly that this is a site-conditioning result on
cross-sectional data — *not* a demonstrated scanner effect and *not* a true null (the within-site
CI includes 0, per-site slopes are heterogeneous).

**(3) "The verifier needs strengthening" (it passed on 800 duplicate constant rows + arbitrary
JSON + a sentence).** Rebuilt as a **proof-of-work verifier** (below): it validates the exact
ABIDE subjects and their per-subject values against a held-out reference, recomputes the pooled
statistic from the submitted rows, cross-checks CSV↔JSON↔metadata, and grades the judgement **as
numbers** (within-site attenuation + the within<pooled<between ordering), not by keyword.

**(4) "Distinguish the marginal from the site-conditioned association; then package inputs,
disable internet, calibrate."** The recast is exactly this marginal-vs-site-conditioned
distinction. Packaging status is documented below; calibration is the maintainer's Step-5.

### Estimand and ground truth (validated on real data)

Connectivity strength = mean of the upper-triangular Fisher-z CC200 edges. Measured on the pinned
sample (data SHA-256 below):

| level | connectivity–age r | 95% CI | p |
|---|---|---|---|
| **marginal / pooled** | **+0.077** | [+0.017, +0.138] | 0.013 |
| **within-site (site fixed effects)** | **−0.020** | [−0.081, +0.042] | 0.53 |
| **between-site (site means)** | **+0.391** | [−0.062, +0.711] | 0.088 (n=20) |

The pooled association is small and significant; conditioning on site **attenuates it toward
null** (CI includes 0); the between-site level carries a clearly positive relationship. So the
marginal association is **site-conditioned**. (Spearman pooled ρ=+0.096, p=0.002.)

**Sensitivity checks (oracle, real data).** Motion-adjusted: pooled +0.097 (p=0.002), within +0.010
(p=0.75). Controls only (n=530): pooled +0.055 (p=0.21), within −0.080 (p=0.07). Sex-adjusted:
pooled +0.071, within −0.019. Nonlinear age: added age² term p=0.07 (not material). Site-specific
slopes: 20 sites, per-site r from −0.34 to +0.22, median +0.02, 60% positive — **heterogeneous**,
consistent with "attenuated toward null, not a true null."

### Proof-of-work verifier (`tests/`, modelled on QSMDIPOLE-001 + NETINTEG-001)

Held-out reference `tests/reference.npz` (built from the oracle run; never shipped to the agent):
`ref_ids` (1035 real `FILE_ID`s), `ref_conn`, `ref_age`, `ref_site`, and `ref_stats`
(pooled/within/between r, p, n). Helper `tests/proof_of_work.py`. Three pillars in
`tests/test_outputs.py`:

1. **Exact subjects + per-subject values.** Submitted `connectivity.csv` must cover ≥90% of the
   real ABIDE subjects **by canonical id**; non-constant guard on connectivity **and** age; the
   fabrication teeth = cross-subject `corr(submitted, reference) ≥ 0.95` (impossible without
   computing the real per-subject connectivity) plus ≥80% within 0.05 abs; and the real
   per-subject **age** must match (≥90% within 0.5 yr).
2. **Recompute + cross-check.** Pooled r **recomputed from the submitted rows** must match both the
   reference (±0.03) and the agent's reported JSON (±0.03); reported `n` is cross-checked against
   the row count and `run_metadata.json`.
3. **Judgement as numbers (not keywords).** The agent must report a within-site and a between-site
   r. Graded numerically: within-site near zero (|r|≤0.08) and matching the reference (±0.08);
   **attenuation** (within < pooled, |pooled|−|within| ≥ 0.02); and the **site-conditioning
   ordering** between > pooled ≥ 0.15. A secondary prose check requires site-conditioning language
   and **rejects over-claims** (scanner causality; "no age relationship at any site" / true null),
   but the numbers carry the grade.

### Validation matrix (MEASURED locally, real oracle output + fixtures)

| # | case | expected | result |
|---|---|---|---|
| 1 | **oracle** (`solution/compute.py`) | PASS | **PASS 5/5** |
| 2 | reviewer **fabrication** attack (800 duplicate constant rows, no real ids, arbitrary JSON, one site sentence) | FAIL | **FAIL** (pillar 1 coverage/non-constant; pillar 2 unrecomputable) |
| 3 | **right-number but fake table** (correct headline JSON, real ids but fabricated per-subject values) | FAIL | **FAIL** (pillar 1 cross-subject corr; pillar 2 recompute −0.03≠+0.077) |
| 4 | **naive** (real rows + real pooled, no within/between judgement, flat "increases with age") | FAIL | **FAIL** (pillar 3 missing within-site; prose) |
| 5 | **defensible-correct** (real rows; within-site via a *different* valid method = median of per-site r = +0.02; reports all three + bounded conclusion) | PASS | **PASS 5/5** |

The reviewer's fabrication attack now **FAILS**. The judgement gate has numeric teeth: a real,
correct pooled computation with no site-conditioning judgement (case 4) scores 0.

### Packaging status (maintainer Step-5)

- **Pinned subject list:** `environment/subject_ids.txt` (the exact 1035 `FILE_ID`s, in fetch
  order) is shipped. The pinned selection (cpac / filt_noglobal / rois_cc200 / quality_checked=
  False) is deterministic.
- **Data hash:** SHA-256 of the concatenated float32 CC200 timeseries (FILE_ID order) + id list =
  `fe6d3d795be2b339fb268e0fd6fdb73214fe838c99b8d1f533c58a78be00a368`.
- **Offline bake — deferred, with a concrete path.** The exact float32 CC200 timeseries bake is
  **149.8 MB** compressed (`.npz`), over GitHub's 100 MB/file limit, so a single-file exact bake
  cannot be pushed this pass. A single-file **float16** bake is **74.9 MB** (fits, but lossily
  substitutes the input); an exact bake needs **2 shards** (~75 MB each). `solution/compute.py`
  already prefers a baked snapshot at `$FCMATUR_DATA` / `environment/data/cc200_timeseries.npz`
  (schema: `ts_i` float arrays + `file_id/age/site_id/sex/dx_group/func_mean_fd`) and falls back
  to the runtime fetch when absent. **This pass therefore keeps `allow_internet=true`** (setting it
  false now would break the oracle, since no data is baked yet). Recommended Step-5 packaging:
  drop in the 2-shard float32 bake (or the float16 single file), rebuild `tests/reference.npz` from
  the baked-input oracle run, then set `allow_internet=false` and calibrate.

### Reliability note (fetch)

Data fetches from AWS S3 (`fcp-indi`) via `fetch_abide_pcp` (~390 MB, ~1 s/file, ~11 min cold).
For local dev, mount a host cache (`NILEARN_DATA`) to skip the download. The reference build,
oracle, and full validation matrix above were all run against this real fetch.

### Cost

Compute is light (1035 × CC200 correlation matrices, a few minutes); the download dominates.
Timeouts: agent 7200 s, verifier 3600 s.

### Difficulty — PENDING the frontier gate (maintainer Step-5, harbor + GPT-5.x / Claude, k≥3 each)

Oracle passes; fabrication, fake-table, and naive all fail; a defensible variant passes. Frontier
runs are the maintainer's, to be recorded here:

| agent | runs | reward | what it did |
|---|---|---|---|
| GPT (codex, xhigh) | _k≥3_ | _pending_ | _pending_ |
| Claude Opus | _k≥3_ | _pending_ | _pending_ |
