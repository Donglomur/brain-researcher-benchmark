## NETSTRENGTH-001

**Proposal Title:** Strongest *direct* connections in the HCP group network matrix — an un-cued full-vs-partial-correlation trap

**Scientific Domain:** Life Sciences · **Field:** Neuroscience · **Subfield:** Resting-state functional connectivity / network modelling

**Source paper:** Smith et al. (2011), *NeuroImage* 54:875, "Network modelling methods for FMRI", https://doi.org/10.1016/j.neuroimage.2010.08.063 (methodology); data: HCP "MegaTrawls" group netmats (Smith et al. 2013, *Nat Neurosci* 16:1852) via `nilearn.datasets.fetch_megatrawls_netmats`, cached under `~/nilearn_data`; ships to fetch at runtime.

**Status: FULL runnable task, oracle + naive + adversarials validated locally. Step-5 frontier calibration PENDING (maintainer).**

### What this task is

A **reproduction**: identify the strongest **direct** functional connections in the HCP MegaTrawls d25 group network matrix and report the node pairs. The dataset ships two group-average netmats over the same 25 group-ICA nodes — `Znet1` (full/Pearson correlation) and `Znet2` (partial correlation). The instruction names both matrices neutrally; which one you rank is the whole task.

### The un-cued lever (PRIVATE — never named in `instruction.md`)

**Full (marginal) vs partial (precision) correlation.** A full correlation between two nodes sums their direct link together with every indirect path through the rest of the network (shared/global signal, common input, A–C–B chains). So the strongest *full*-correlation edges are dominated by indirect, globally-confounded structure — they are not, in general, *direct* connections. Partial correlation regresses out all other nodes and leaves (up to regularisation) the direct edge — the central methodological point of Smith et al. (2011). The instruction never says "use partial correlation", never says full-correlation strongest edges are indirect, and the ID is neutral (NETSTRENGTH, not PARTIALCORR).

### Step-0 result (validated on the nilearn-pinned MegaTrawls d25 group netmats)

25 nodes, 300 upper-triangle edges. Ranking by absolute Z:

| rank | strongest DIRECT (partial, CORRECT) | strongest FULL-corr (naive) |
|---|---|---|
| 1 | (0,12) Z=33.3 | (0,3) Z=35.5 |
| 2 | (8,9)  Z=31.8 | (0,2) Z=32.4 |
| 3 | (0,1)  Z=−31.6 | (2,3) Z=32.2 |
| 4 | (10,14) Z=30.5 | (0,12) Z=30.3 |
| 5 | (10,15) Z=−29.8 | (2,4) Z=−29.7 |

- corr(full, partial) over edges = **0.69**; only **43%** of the top-decile full edges are top-decile partial edges.
- Top-3 full ∩ top-3 partial = **∅**. The naive full top-3 (0-3, 0-2, 2-3) have partial ranks 15–20 (indirect).
- Signature case: **(0,4)** is a top-7 *full* edge (Z=−29.3) but its partial Z is **+0.08 — rank 300/300**, i.e. essentially a zero direct connection; a pure indirect/globally-confounded path.
- Hub: **node 0** under full correlation, but the direct-connection hub is **node 10**.

So a full-correlation ranking and a partial-correlation ranking give almost disjoint "strongest connections", and only the partial one answers "direct".

### Verifier (2 plain checks; `tests/test_outputs.py`)

Short reviewer-style pytest, schema-robust, no rubric:
1. **strongest connections are direct, not marginal** (primary, objective). Parses reported node pairs from any JSON structure (`{"nodes":[i,j]}`, `{"i":..,"j":..}`, 2-int lists) and from prose, under both 0-based and 1-based numbering. Requires the reported set to be dominated by the **direct-only** edges `{(0,1),(0,8),(1,8),(6,14),(8,9),(10,14),(10,15),(10,23)}` and to contain more of them than the **full-only** (indirect) edges `{(0,2),(0,3),(0,4),(2,3),(2,4),(2,14),(4,7),(19,23)}` (`p_only ≥ 2 and p_only > f_only + 1`). This rejects a full-correlation ranking AND a dump of the whole matrix.
2. **write-up distinguishes direct from indirect** (honesty). `findings`/`run_metadata` must justify the connections via partial correlation / removing the influence of other nodes, or flag that full-correlation strongest edges are indirect.

### Discrimination (validated locally)

| submission | check 1 (edges) | check 2 (honesty) | verdict |
|---|---|---|---|
| reference oracle (partial correlation, top-10) | pass | pass | **PASS** |
| correct answer with **1-based** node numbering | pass | pass | **PASS** (indexing-robust) |
| naive full-correlation ranking (top-10) | **fail** | fail | **FAIL** |
| dump of all 300 partial edges | **fail** | pass | **FAIL** (dominance guard rejects dumps) |
| full-correlation edges but prose that *names* "partial" | **fail** | pass | **FAIL** (objective edge check can't be word-gamed) |

### Step 5 — frontier calibration: PENDING (maintainer)

Oracle-passes and naive-fails are validated locally, including indexing-robustness and anti-gaming adversarials. The ≥2-frontier-family (k≥3, hand-rescored) gate — whether un-cued frontier agents actually reach for the full-correlation matrix (or recompute Pearson) and report indirect hubs — is a maintainer step. Note the fetcher default is `matrices="partial_correlation"`, so an agent that blindly takes fetcher defaults may land on the correct matrix; the trap targets agents that equate "connection strength" with the full/Pearson correlation matrix (`Znet1`), which is the intuitive but wrong choice for *direct* connectivity.

### Cost / data caveat

`hard`. cpus 2, mem 4 GB, internet on (fetches MegaTrawls netmats, ~8.8 MB, at runtime; timeouts 1800 s). Deps pinned in the Dockerfile (nilearn 0.13.1). Compute is trivial (two 25×25 matrices); the difficulty is entirely the un-cued full-vs-partial choice. Data caveat: `fetch_megatrawls_netmats` pulls from a public mirror; on rare hiccups the fetch should be retried (an infra artifact, not a task FAIL).
