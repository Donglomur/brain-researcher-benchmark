## FCSTAB-001

**Proposal Title:** Within-run change of the strongest resting-state functional connections — separating the selection artefact from a genuine early-to-late effect

**Scientific Domain:** Life Sciences · **Field:** Neuroscience · **Subfield:** Resting-state functional connectivity / statistical rigor

**Methodological basis:** Galton (1886); Barnett, van der Pols & Dobson (2005), *Int J Epidemiol*, https://doi.org/10.1093/ije/dyh299 ("Regression to the mean"). Within-scan FC reliability: Laumann et al. (2015), *Neuron*; Noble et al. (2019), *NeuroImage*. Dataset: **ABIDE Preprocessed** via `nilearn.datasets.fetch_abide_pcp` (pipeline `cpac`, band-pass, no GSR, `quality_checked=True`), **Craddock-200 (CC200)** pre-extracted ROI time series, **first 40 quality-checked subjects**.

**Status: FULL runnable task (rigor genre).** Reworked from the reviewed version (PR #196) to the maintainer's (@zjc062) spec: the graded conclusion is now the correctly-bounded one, the design requires forward / reverse / independent / random selection with subject-level signed Δz and uncertainty, the acquisition description is corrected and the cohort pinned, and the verifier is a **proof-of-work** grader.

### The recut science (what the review required)

Selecting the top-decile edges on the **first half** makes the naive `second − first`
contrast **selection-contaminated**: the first-half mean of the selected set is inflated by
first-half noise, so the difference carries a **negative selection component** on top of any
genuine early-to-late change. The observed decline therefore **cannot by itself establish
that the strongest connections genuinely weaken** — it is not an estimate of the true
early-to-late effect, and the earlier "pure RTM / rules out genuine weakening / stable"
framing overclaimed. To separate selection from a genuine effect, the task requires four
per-subject signed Fisher-z changes of the top-decile set (first 40 ABIDE cpac/CC200
subjects, equal contiguous halves, 198 common ROIs → 19 503 edges):

| selection scheme | how the strong set is chosen | group Δz (mean, 95% CI) | reads as |
|---|---|---|---|
| **forward** | top decile on the **first** half | **−0.212** [−0.252, −0.171], 37/40 neg | the naive "decline" |
| **reverse** | top decile on the **second** half | **+0.235** [+0.188, +0.282], 0/40 neg | sign **flips** with the selected half |
| **independent (LOSO)** | strong set from the **other 39 subjects** | **−0.000** [−0.042, +0.042] | selection-free ≈ 0 |
| **random** | size-matched random edges | **+0.005** [−0.037, +0.047] | selection-free control ≈ 0 |

Forward and reverse are opposite-signed and of similar magnitude — the sign of the "effect"
is set by **which half you select on**, which a genuine temporal process could not do; their
average is +0.012 (selection bias cancels). The selection-free (independent/random) estimate
is statistically **equivalent to zero within a prespecified ±0.05 z margin** (TOST p = 0.011).
The honest within-run reliability of the strong edges is **moderate**: top-decile edge-set
overlap ≈ 0.42, edge rank Spearman ≈ 0.48, edge ICC ≈ 0.53. Paired separations: forward vs
random t = −26.6; forward vs independent t = −39.8; forward vs reverse t = −47.3.

**Graded conclusion:** *the naive top-decile decline is selection-contaminated and cannot by
itself establish weakening* — not "pure RTM", not "rules out genuine weakening", not "stable"
(stability only against the prespecified equivalence margin).

### Cohort correction + pinning (review point 3)

The first 40 quality-checked records are **not** a long eyes-open cohort. They are **all from
a single site (PITT), scanned eyes closed**, each a **single ~4.9-minute run (196 volumes,
TR = 1.5 s)**. The instruction now states this correctly and pins the exact 40 `file_ids`
(`Pitt_0050003 … Pitt_0050048`) and content hashes. Data hashes (baked float32 npz):
`data_sha256 = 37c4f5e901962978d1d00ce503af590971edc3a1fec484f964fb02e86addedac`;
cohort file hash `4d7e20b779fa0895fbefe6fd73766de57c429b6c744ec93de216ff3a857b2ee4`;
float64 numeric hash `8280a1b9ba62bc60ca9508f2c000d3cb0b536f9c5ea134be473bba75b4be345b`
(per-file SHA-256 in `environment/data/MANIFEST.json`).

### Packaging (review point 4)

The 40 CC200 ROI time series are **baked into the image** (`environment/data/abide_cc200_pitt40.npz`,
5.8 MB, copied to `/app/data`), and `task.toml` sets **`allow_internet = false`** — the task
and verifier run fully offline. Verifier dependencies (`pytest`, `pytest-json-ctrf`, `numpy`)
are baked into the image; `tests/test.sh` uses the baked `python3 -m pytest` (no `uvx`
network fetch). The held-out reference `tests/reference.npz` is built by running
`solution/compute.py` on the baked data and never ships to the agent (only `environment/` +
`instruction.md` do).

### Proof-of-work verifier (review point 4)

`tests/test_outputs.py` + `tests/proof_of_work.py` — three pillars, all required:

1. **Exact subjects + real per-subject values.** `stability.csv` must cover the pinned 40
   subject ids (≥90 %, ≥85 % of submitted ids real), and the per-subject **forward**
   (`first_half`, `second_half`, `delta`) and **reverse** `delta` must match the held-out
   reference within ±0.06 for ≥90 % of subjects, with a non-constant guard (`pstdev > 1e-4`).
   This kills fabricated / duplicated / constant rows and a right-number-but-fake table.
2. **Recompute the summaries from the rows.** The group means recomputed from the submitted
   rows must equal both the reference (forward/reverse/random within ±0.03; independent/random
   |mean| ≤ 0.06) **and** the reported `summary.json` values (within ±0.02) — an inconsistent
   summary fails.
3. **Grade the conclusion as numbers.** The reported scheme means must jointly show the
   contamination: forward ≈ −0.21 (real decline), reverse opposite-signed and > +0.10 (sign
   flip), independent |mean| ≤ 0.06 **and** < ½·|forward| (selection-free ≈ 0), random ≈ 0.
   A secondary negation-aware `findings.md` guard requires the selection-contamination reading
   and vetoes an un-negated "genuine within-run weakening" conclusion — but the numbers carry
   the grade.

An agent that only ran the naive forward analysis cannot produce the reverse per-subject
column or the near-zero independent mean, so it cannot pass by keywords.

### Validation matrix (SPEC protocol; real grader vs rendered submissions)

| submission | reward |
|---|---|
| **ORACLE** (`solution/solve.sh`) — all four schemes, correct conclusion | **PASS (1.0)** |
| reviewer **fabrication** attack — constant/dup rows + in-band JSON + keyword sentence | **FAIL** |
| **right-number, fabricated per-subject table** — correct group JSON, fake rows | **FAIL** (per-subject match 28 %) |
| **naive-only** — real forward, no reverse/independent, "connections weaken" conclusion | **FAIL** (missing schemes + genuine-weakening veto) |
| **defensible-correct** variant — different valid independent scheme (others' first-half LOSO) | **PASS** |

Fabrication now FAILS; the earlier grader accepted fabricated duplicate rows and inconsistent
summaries, this one does not.

### Difficulty status

Oracle **reward 1.0** validated offline (in-container path: baked npz → `compute.py` → all
deliverables → grader passes 7/7). The construction bar is met: a required, off-the-naive-path
rigor step (reverse/independent selection), a large robust gap (forward −0.21 vs selection-free
≈ 0; paired t up to −47), and a fabrication-proof grader. **The live ≥2-family frontier gate
(k≥3) is the maintainer's Step-5 and has not been run here.**

### Cost & reliability

`hard`. cpus 2, mem 8 GB, **`allow_internet = false`** (offline). Runtime is trivial
(per-subject 198-ROI correlations × 4 selections + LOSO). Deps pinned as for the sibling tasks,
plus baked `pytest`/`pytest-json-ctrf` for the offline verifier. Reference build data hash
recorded above; `tests/reference.npz` regenerates deterministically from the baked data
(`FRAC=0.10`, `SEED=0`, `EQUIV_MARGIN=0.05`).
