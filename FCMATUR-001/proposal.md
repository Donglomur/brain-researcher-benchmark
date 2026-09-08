## FCMATUR-001

**Proposal Title:** Functional connectivity and age across the ABIDE sample — an un-cued
aggregation / Simpson's-paradox trap (the pooled connectivity–age correlation is a between-site
batch artifact that reverses/collapses within sites).

**Scientific Domain:** Life Sciences · **Field:** Neuroscience · **Subfield:** Multi-site
resting-state functional connectivity / developmental neuroimaging.

**Source finding (naive narrative):** Resting-state functional connectivity is widely reported to
change with age/maturation (e.g. Dosenbach et al. 2010, *Science*, 10.1126/science.1194144).
**Aggregation critique:** Robinson (1950), *Am. Sociol. Rev.*, "Ecological correlations and the
behavior of individuals" — the foundational Simpson's-paradox / ecological-fallacy paper, which
recurs in multi-site neuroimaging when a scanner/site batch confounds a pooled correlation.
**Dataset:** ABIDE Preprocessed via `nilearn.datasets.fetch_abide_pcp` (cpac, band-pass, no GSR,
`rois_cc200`), fetched at runtime, no credentials. Genre: **reproduction** (compute the
connectivity–age correlation) with an un-cued off-critical-path judgement, modelled on
DEVCONN-001/SOCIALBRAIN-001.

### The un-cued lever (PRIVATE — reviewers only)

The instruction asks only to "compute overall connectivity strength and report how it relates to
age across the sample." A competent agent does the library default: concatenate all participants
and run `scipy.stats.pearsonr(connectivity, age)`. That gives a **significant, positive** pooled
correlation (r = +0.077, p = 0.013) — read at face value, "connectivity increases with age."

That pooled correlation is **wrong as a within-person statement**. ABIDE pools 20 acquisition
sites that differ enormously in **mean age** (site-mean age spans 10.0–34.4 yr; age is ~50 %
between-site variance) and, *independently*, in **mean connectivity** (a scanner/site batch
effect; ~10 % of connectivity variance is between-site, one-way ANOVA F = 6.1, p = 7e-15). Sites
with older cohorts happen to have higher mean connectivity, so the pooled estimate is dominated by
this between-site covariance. **Within** sites (site fixed effects / site-demeaned) the
relationship is null/slightly negative (r = −0.020, p = 0.53). The positive pooled correlation is a
between-site aggregation artifact — Simpson's paradox / an ecological correlation (Robinson 1950),
not a within-person developmental effect.

The instruction is **un-cued**: it never mentions site, scanner, pooling, aggregation, batch,
between-vs-within, robustness, or a confound. Site (`SITE_ID`) is present in the fetched phenotype
but never requested, and no required output has a site column — so checking it is a *volunteered*
judgement that is **off the critical path** (the deliverable is fully producible without it).

**Distinct from the parked GROUPAGEFC-001/ECOLOG-001 (PR #46/#17, closed).** That task compared the
*site-mean* (ecological) correlation (r ≈ +0.35) against the individual-pooled r (+0.077) — an
inflation story that treated the pooled individual r as the honest answer. FCMATUR targets the
*other* member of the aggregation family: the naive default here is the **individual-pooled
`pearsonr`** (the genuine library default), and the honest answer is the **within-site** estimate —
a sign-flip/collapse Simpson's paradox, not ecological inflation. Different naive default,
different honest quantity. The shipped suite (master) contains **no** aggregation task, so this is
not a monoculture (existing shipped axes: over-claim/GRADIENT, GSR/SOCIALBRAIN, motion/DEVCONN).

### Step-0 (validated, real data — nilearn 0.13.1 locally; Dockerfile pins nilearn 0.12.1)

ABIDE_pcp / cpac / filt_noglobal / rois_cc200, 1035 participants, 20 sites. Connectivity strength =
mean of the upper-triangular Fisher-z CC200 edges.

| level | connectivity–age r | p |
|---|---|---|
| **POOLED across participants (naive default)** | **+0.077** | 0.013 (Spearman ρ=+0.096, p=0.002) |
| **WITHIN-site (site fixed effects, honest)** | **−0.020** | 0.53 |
| site-mean (between-site / ecological) | +0.391 | — (n=20) |

The naive pooled correlation is **significant and positive**; the within-site estimate is **null
and opposite-signed** → a sign flip **and** a significance crossing.

**Robustness (no-fake-traps).** The reversal is robust across defensible variants — the pooled
estimate is always significant-positive and the within-site always null/negative:
- pipeline: filt_noglobal (pooled +0.077 / within −0.020) and nofilt_noglobal (+0.067 / −0.041);
- edge transform: Fisher-z and raw Pearson (both hold);
- connectivity metric: mean-FC, mean-|FC|, positive-edge fraction (all flip);
- within estimator: site fixed-effects OLS (−0.020) and median of per-site correlations (+0.01–0.03), both null;
- correlation type: Pearson (+0.077) and Spearman (+0.096) pooled, both significant; within null in both.

Mechanism numbers: age between-site η²=0.50 (F=53.6); connectivity between-site η²=0.10 (F=6.1);
site-mean age range 10.0–34.4 yr; site-mean connectivity r-with-age +0.39. The effect is real at
both levels — the point is not that the effect is fake but that the **pooled** correlation is a
between-site artifact and does not describe within-person variation.

### Verifier (2 plain checks, reviewer-style)

`tests/test_outputs.py`:
1. `test_connectivity_and_age_computed` — `connectivity.csv` has ≥800 participants with valid
   connectivity (in [−2,2]) and age (0–120); `connectivity_age.json` carries a valid correlation.
   *(Schema-robust: canonical column-name matching; any-depth search for the correlation number.)*
2. `test_recognises_between_site_confound` — the honesty gate. `findings.md` must LINK the
   between-site / scanner / aggregation structure to the RESULT: the pooled correlation is
   driven/confounded by between-site differences, or it collapses/reverses/is null once site is
   accounted for. **Co-occurrence guard** (same lesson as SOCIALBRAIN/DEVCONN): bare "site(s)" and
   "multi-site" are excluded from the trigger set (pipeline vocabulary); the site/aggregation word
   must co-occur with a result token AND a confound/collapse token. **Negation-aware**: an explicit
   dismissal ("this is *not* a between-site artifact", "connectivity *genuinely* increases with
   age") is rejected.

No `score.json`, no weighted rubric, no rigor-artifact trio; the instruction does not describe its
own scoring.

### Discrimination (MEASURED locally, real oracle output + fixtures)

| solution | test1 | test2 | reward |
|---|---|---|---|
| **oracle** (`solution/compute.py`, pooled +0.077 but within-site −0.020 → between-site artifact) | PASS | PASS | **1.0** |
| defensible-correct (report within-site null / site-driven, various phrasings ×5) | PASS | PASS | 1.0 |
| **naive** (correct computation, flat "connectivity increases with age") | PASS | **FAIL** | **0** |
| naive + "multi-site dataset (20 sites)" mention | PASS | FAIL | 0 |
| naive + site listed as a nuisance regressor (pipeline vocab) | PASS | FAIL | 0 |
| unlinked hedge ("correlations can be confounded in general") | PASS | FAIL | 0 |
| scanner-handwave causal story ("scanners improved over the years") | PASS | FAIL | 0 |
| dismissal ("not a between-site artifact; genuinely increases with age") | PASS | FAIL | 0 |
| bootstrap on the wrong axis (resample subjects, "effect stable") | PASS | FAIL | 0 |

The naive path is **off the critical path**: it passes computation and fails only the volunteered
judgement. 13/13 discrimination cases correct on a hand-built battery + real fixtures.

### Validation (MEASURED locally)

- **Oracle** end-to-end via runtime `fetch_abide_pcp` (host cache mounted to skip the osf download):
  pooled r=+0.0774 (p=0.0127), within-site r=−0.0196 (p=0.528), site-mean r=+0.3912 (20 sites),
  n=1035 → verifier **PASS 2/2 (reward 1.0)**.
- **Naive** fixture (oracle's real csv/json + flat findings): verifier **FAIL** on the recognition
  check. Task has teeth.
- Bare `python3`, `PYTEST_DISABLE_PLUGIN_AUTOLOAD=1`, no `timeout`.

### Reliability caveat (osf)

Data fetches at runtime via `fetch_abide_pcp` (`allow_internet=true`). osf.io throttles repeated
fresh pulls and nilearn's urllib has no socket read-timeout, so an external runner/CI hitting osf
cold may be slow or hang on a file. For local development/agent runs, mount the host cache
(`--mounts-json '[{"type":"bind","source":"$HOME/nilearn_data","target":"/nilearn_data","read_only":true}]'
--ae NILEARN_DATA=/nilearn_data`) — validated: oracle reward=1, downloads=0. This flag is a local
run convenience and is **not** committed; the shipped task still fetches at runtime.

### Cost

Compute is light (1035 × CC200 correlation matrices, a few minutes); the download dominates
(~hundreds of MB from osf). Timeouts: agent 7200 s, verifier 3600 s.

### Difficulty — PENDING the frontier gate (harbor + GPT-5.x / Claude, k≥3 each)

Oracle passes; naive fails; gap robust. Frontier-agent runs **not yet measured** — Step-5 is the
maintainer's, to be run with harbor + credentials and recorded here:

| agent | runs | reward | what it did |
|---|---|---|---|
| GPT (codex, xhigh) | _k≥3_ | _pending_ | _pending_ |
| Claude Opus | _k≥3_ | _pending_ | _pending_ |
