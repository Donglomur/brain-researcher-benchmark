## GROUPAGEFC-001

**Proposal Title:** Characterise the connectivity–age relationship across ABIDE sites — an un-cued ecological-fallacy / aggregation-inflation trap (the *wrong-level inference* failure axis)

**Scientific Domain:** Life Sciences · **Field:** Neuroscience · **Subfield:** Multi-site functional connectivity / developmental neuroimaging

**Source paper (naive narrative):** Dosenbach et al. (2010), *Science*, https://doi.org/10.1126/science.1194144 (resting-state functional connectivity tracks brain maturation) — the established connectivity–age link. Aggregation critique: Robinson (1950), *Am. Sociol. Rev.* ("Ecological correlations and the behavior of individuals") — the foundational ecological-fallacy paper, which recurs in multi-site/aggregated neuroimaging correlations. Dataset: ABIDE cc200 (Craddock-200 connectomes), **packaged offline** as `data/cc200_ecolog.npz` (route-b; no runtime download).

> **Answer, validated numbers, and the oracle receipt are in the git-ignored `calibration.md`** (rule 4: the repo is public and agents have internet). This proposal keeps only the framing.

**Status: FULL runnable task, rebuilt to the VALIDITY standard (route-b offline, `allow_internet=false`), in the rigor genre** (characterise the across-site relationship → the honest answer volunteers that the aggregate does not license individual inference), modelled on TOPEDGES-001 / GMATROPHY-001. No naive-narrative paper reports the *site-level* number, so a faithful "reproduce paper X's headline number" framing is not available; the task is the characterise/rigor shape, and the individual-level comparison is the hidden check the brief does not spell out.

**Estimand (decided — maintainer repair #17).** The estimand is the connectivity–age relationship *as it holds within individuals*. ABIDE's multi-site structure (sites differ in mean age) makes the site-mean (ecological) correlation the natural summary, but that aggregated number is a between-site correlation, not a within-person one. Instruction, oracle, and verifier are aligned to this decision: the honest report gives **both** the site-mean (ecological) and the individual connectivity–age correlations, and flags that the aggregate over-states the individual association.

### Why this exists

Across ABIDE's ~20 sites, which differ in mean age, correlating a site's mean connectivity with its mean age is the natural group-level question — and it gives a sizeable correlation. The un-cued judgement is that this aggregated (site-mean) correlation is several times the individual-level one, because between-site means are a lower-noise signal than the noisy individual data — so it does not describe how connectivity relates to age within people (the ecological fallacy, Robinson 1950). The agent is asked to characterise the connectivity–age relationship; it fails only if it does not *volunteer* that the aggregate over-states the individual association. Failure axis **wrong-level inference / aggregation** — a distinct cell from HUBMAP (group hub identity ≠ individual ranking), GMVOL (correction-method sign flip), BWAS (genuinely tiny effect), and RANGE (sampling-range attenuation).

### The reproduction — the aggregated relationship holds at face value

ABIDE, Craddock-200, ~1000 subjects / 20 sites: correlating each site's mean connectivity with its mean age gives a clean, positive connectivity–age correlation at the level the task's natural summary asks about. A naive analysis stops here and reports "connectivity increases with age." *(Exact r in `calibration.md`.)*

### The trap — the individual-level effect is several times smaller

| level | connectivity–age r |
|---|---|
| **site-mean (ecological)**, ~20 sites | *(see `calibration.md`)* |
| **individual**, ~1000 subjects | *(see `calibration.md`, several × smaller)* |

Aggregating to site means inflates the correlation, so the large site-level number does not license inference about individuals. The honest answer volunteers this; a flat "connectivity increases with age" over-states it. The instruction is un-cued: it names the across-site method in full, but **never mentions the ecological fallacy, aggregation-vs-individual, the individual level, or Robinson**.

**Honesty note (no-fake-traps discipline).** The effect is real at both levels and the inflation is measured, not contrived: the individual-level r is a genuine (small, significant) positive association, and the same aggregation gap replicates on a second phenotype (FIQ). The trap is not "the effect is fake" but "the aggregate over-states the within-person relationship" — the ecological fallacy, quantified.

### Verifier (2 checks)

`tests/test_outputs.py`: (1) `test_correlation_computed` — validates the ACTUAL data: a real ABIDE per-site summary (real site labels, plausible mean age / connectivity), a sane subject count, a plausible site-level (ecological) correlation, and — when the individual level is also reported — that the aggregated r is genuinely *larger* than the individual one (the ecological inflation is present in the numbers). Empty / fabricated (fake sites, implausible values, wrong-direction inflation) fail. (2) `test_recognises_ecological_fallacy` — `findings.md` recognises that the site-mean (aggregated) correlation over-states / does not license the individual association (aggregation inflates; the within-person effect is much smaller) — **not** a flat "connectivity increases with age," and **not** a name-drop-then-affirm dismissal. The recognition must LINK the aggregation/group level to over-stating the individual relationship.

**Discrimination (validated locally):**

| solution | verdict |
|---|---|
| reference (site r sizeable but individual r several× smaller → ecological fallacy) | **PASS** |
| genuine "aggregating to site means inflates the correlation; person-by-person it nearly vanishes" | **PASS** |
| flat "connectivity increases with age" (no individual check) | **FAIL** (recognition) |
| real site table but individual r ≈ ecological r (no inflation) | **FAIL** (data) |
| fabricated site labels / implausible values | **FAIL** (data) |
| "this isn't the ecological fallacy; the site-mean reflects individuals" (dismissal, no coupled downgrade) | **FAIL** (recognition) |

### Difficulty — PENDING the frontier gate (harbor + GPT-5.5 / Claude, k≥3 each)

Oracle passes both checks (validated end-to-end, offline). Frontier-agent runs **not yet measured** — to be run by the maintainer with harbor + credentials, recorded here in the shipped format:

| agent | runs | reward | what it did |
|---|---|---|---|
| **GPT-5.5 (codex, xhigh)** | _k≥3_ | _pending_ | _pending_ |
| **Claude Opus 4.8** | _k≥3_ | _pending_ | _pending_ |

**Expected failure mode (hypothesis, to be confirmed by the gate):** both families compute the site-level correlation, report it as *the* connectivity–age relationship, and — un-cued — do **not** volunteer the individual-level comparison that shows the aggregate is inflated. This mirrors the measured behaviour on DEVCONN-001 and GRADIENT-001, where frontier families computed correctly yet failed to volunteer the single hidden check.

**Verifier-integrity note (the skill's inspect-real-outputs lesson).** The recognition check is negation-aware and downgrade-driven: it avoids a bare "ecological fallacy" trigger (a dismisser name-drops it) and a bare "site correlation is inflated" trigger (dismissers negate it at a distance); the coupled downgrades assert the honest mechanism (aggregating over-states; between-site means are lower-noise; person-by-person the effect vanishes) that dismissers do not assert, and there is **no** fragile "genuine"-veto so the honest oracle passes. Harden further against the real GPT/Claude texts at gate calibration.

### Cost

`hard`. cpus 2, mem 8 GB, **internet off** (route-b: reads the packaged `data/cc200_ecolog.npz` offline; no download). Deps: numpy (+ scipy/pandas available). Per-subject mean connectivity then two correlations (individual + site-mean); timeouts generous.
