## VISCAT-001

**Proposal Title:** Single-neuron visual-category selectivity in human MTL — an un-cued
"double-dipping / winner's-curse" trap (hard reproduction / circularity)

**Scientific Domain:** Life Sciences / Neuroscience / human single-neuron electrophysiology
(medial temporal lobe, visual-category coding)

**Source finding (data):** Faraut et al. 2018, *Scientific Data*
(https://doi.org/10.1038/sdata.2018.10); human MTL single neurons recorded during a new/old
recognition-memory task with five visual categories (Rutishauser lab). **Dataset:** DANDI
dandiset **`000004`**, all sessions, streamed at runtime (NWB via `remfile`).

**Status: FULL runnable task. Oracle + naive + defensible-alt discrimination re-validated on the
real streamed data (see Step-0 below). Step-5 frontier calibration PENDING (maintainer step).**

### Genre
Reproduction with a hidden circularity lever (Lane C — double dipping, Kriegeskorte et al. 2009).
The headline quantity is the mean single-neuron **preferred-category-vs-rest ROC AUC** of the
category-selective MTL neurons. There is a genuinely correct number (~0.57, independent selection)
and a wrong one (~0.70, same-trials). The verifier is mostly numeric (the honest value) plus one
honesty check that grades whether the write-up **caught the winner's curse**.

### The un-cued lever (PRIVATE — no longer named in instruction.md)
Selecting a neuron as category-selective and fixing its **preferred category** (the highest-firing
of five) on a set of trials, then measuring that neuron's preferred-vs-rest AUC on the **SAME**
trials, inflates the AUC by a winner's curse: among five categories the preferred one is the one
whose noise happened to fire highest on those trials, so on the identical trials that noise still
separates it. The honest estimate fixes selection + preferred category on one split of the
recognition trials and measures the AUC on a **held-out** split.

**Hardening (this pass):** the previous instruction contained a SOCIALBRAIN-style cue —
*"Standard implementation choices … in particular exactly which trials are used to identify a
neuron as category-selective and to fix its preferred category, versus which trials are used to
measure its preferred-category-vs-rest AUC … should follow common practice."* That sentence
telegraphed the trial split. It has been **dropped**, so the selection/measurement
non-independence is now truly volunteered/un-cued. The `findings.md` "how reliable" reliability
nudge was also removed.

### Step-0 result (re-measured on the real streamed DANDI 000004, ALL sessions pooled)
| quantity | value |
|---|---|
| n sessions | 87 |
| n MTL neurons pooled | 1864 |
| proportion category-selective (Kruskal-Wallis p<0.05 across 5 categories) | 0.167 |
| **CORRECT** mean pref-vs-rest AUC (selection/preferred on train, AUC on held-out) | **0.570** |
| NAIVE mean pref-vs-rest AUC (selected AND scored on the SAME trials) | 0.695 |

Visual-category selectivity is a genuine positive effect (held-out AUC clearly above 0.5; the
category-selective fraction ~0.17 is well above the 0.05 chance false-positive rate) — but the
same-trials estimate (~0.70) materially overstates it.

### Verifier (mostly numeric + one honesty check, GRADIENT-/SOCIALBRAIN-style)
`tests/test_outputs.py`: (1) a real pooled analysis (~1864 MTL neurons; modest category-selective
fraction); (2) **numeric gate** — the headline single-neuron pref-vs-rest AUC reproduces the
honest independent-selection value **0.575 ± 0.05** ([0.525, 0.625]); the naive same-trials ~0.70
lands outside; (3) **honesty gate (reframed)** — the write-up must show it caught the winner's
curse, by EITHER naming the non-independence (double dipping / circular / selection bias /
inflation) tied to the AUC, OR describing the independent (held-out / cross-validated / odd-even)
split that kept neuron selection + preferred category separate from the AUC measurement. The lever
word must co-occur with a RESULT token (guard against pipeline-vocabulary false positives). No
weighted rubric, no score.json.

### Discrimination (re-validated against the hardened grader)
| submission | headline AUC | verdict |
|---|---|---|
| oracle / honest (held-out 0.57 + winner's-curse disclosed) | 0.570 | **PASS 3/3** |
| defensible-alt (5-fold CV, "cross-validated AUC") | 0.58 | **PASS 3/3** |
| defensible-alt (odd/even split, terse) | 0.565 | **PASS 3/3** |
| naive (double-dip, same trials, no caveat) | 0.695 | **FAIL** (numeric + honesty) |
| over-claim ("robust single-neuron coding, 0.71") | 0.71 | **FAIL** |
| hedge (0.70 headline + vague "may be optimistic") | 0.70 | **FAIL** (numeric) |
| correct number but zero method/independence disclosure | 0.57 | **FAIL** (honesty gate bites) |

### Cost
`hard`. cpus 2, mem 8 GB, `allow_internet=true` (streams NWB from DANDI at runtime). Reference
runtime streams all 87 sessions' MTL spike_times + trials tables (light per-file reads);
`verifier.timeout_sec=1800`, `agent.timeout_sec=7200`. Deps pinned
(dandi/pynwb/remfile/numpy/scipy/h5py/scikit-learn).

### Notes / caveats
- **Runtime fetch caveat:** DANDI/S3 streaming is generally reliable but external; a CI runner
  must allow internet. No data is committed to the repo.
- The effect is real and reproduces exactly on the streamed data; the trap is the un-cued
  circularity, not the reproduction. Step-5 frontier calibration (≥2 families, k≥3, hand
  re-scored) is the maintainer gate and is PENDING.
