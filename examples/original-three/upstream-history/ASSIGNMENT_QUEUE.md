> **Upstream history.** This document records the original three-task programme.
> For this fork's current neuroscience work, use the [task catalog](../../../benchmarks/README.md)
> and [development workflow](../../../docs/DEVELOPMENT.md). Historical claims are retained, not revalidated here.

# Assignable task queue

Pulled from the landscape backlog (`landscape/results/topic_paper_map.csv`, 555 ranked
anchor papers over 111 rising topics). **Organised into data/modality lanes so two authors
work different lanes and the suite doesn't become a monoculture** (see INTERN_GUIDE →
anti-monoculture).

**Honest caveat — the anchor papers are *citation*-ranked, so rank-1 is often a review.**
A task needs a **primary empirical paper whose headline reproduces on obtainable open data**.
Within a lane, pick a primary paper (lower ranks in `topic_paper_map.csv`, or your own search)
and run **Step-0 first** — it will kill many candidates, and that's fine.

The two shipped tasks both sit in **Lane A / ds000228** — so *start in a different lane*.

---

## Lane A — resting-state connectivity (break the ds000228 monoculture)
- **Data**: ABIDE, ADHD-200 (both via `nilearn.datasets.fetch_abide_pcp` / `fetch_adhd`), or
  another OpenNeuro rest cohort — **not** `fetch_development_fmri` (already used ×2).
- **Levers**: GSR (used in SOCIALBRAIN — pick a *different* lever), **temporal band-pass**,
  **atlas/parcellation granularity** (Schaefer-100 vs 400 vs AAL), **motion/QC-FC scrubbing**.
- **Failure axes open here**: **wrong-cause** (motion), confident-refutation (band-pass/atlas).
- Seed candidates:
  - **Motion/QC-FC** — "children have weaker long-range connectivity": does the effect survive
    FD-scrubbing? (Power 2012 confound.) *Wrong-cause axis, our proposed CANDIDATE-motion.*
  - **Atlas-dependence** — a graph metric (hub identity / modularity) that flips Schaefer-100↔400.
  - salience/DMN switching — Goulden et al. 2014 (doi 10.1016/j.neuroimage.2014.05.052).

## Lane B — task-fMRI GLM / activation (highest novelty; breaks connectivity monoculture)
- **Data**: OpenNeuro fMRIPrep derivatives on the public S3 — use the `neuroprogram-real-fmri`
  skill's fetch path. Real task-GLM, not connectivity.
- **Levers**: **HRF basis**, motion/confound regressor set, **smoothing kernel**, cluster-forming
  threshold, first-level vs fixed-effects. This is a natural **multiverse / point-estimate-vs-distribution** task.
- **Failure axes open here**: confident-refutation, point-estimate-without-distribution.
- Seed candidates:
  - **Attention Network Task (ANT)** — Fan et al. 2002 (doi 10.1162/089892902317361886); heavily
    replicated, many OpenNeuro ANT datasets; does a contrast survive HRF/threshold choices?
  - any classic emotion/executive contrast (emotional faces, n-back, Stroop) with an OpenNeuro dataset.

## Lane C — structural MRI (VBM / cortical thickness)
- **Data**: OpenNeuro T1 cohorts, OASIS (`nilearn.datasets.fetch_oasis_vbm`).
- **Levers**: **smoothing kernel**, **software** (FSL-VBM vs FreeSurfer vs CAT12), atlas, modulation on/off.
- **Failure axes**: confident-refutation, wrong-cause.
- Seed candidates:
  - aging grey-matter decline — Park et al. 2008 (review; find a primary VBM aging paper) — does a
    regional effect depend on smoothing/software?
  - structural biomarker of a disorder (Alzheimer, MS) — Frisoni et al. 2010 as an entry point.

## Lane D — prediction / ML on connectomes (the leakage lane)
- **Data**: ABIDE / ADHD-200 / any OpenNeuro cohort with phenotype.
- **Levers**: **cross-validation scheme** (subject/site leakage), **site harmonization** (ComBat),
  feature-selection **circularity** (double-dipping), train/test split.
- **Failure axes**: **wrong-cause** (leakage inflates accuracy) — a strong, under-covered axis.
- Seed candidates:
  - brain-age / maturity prediction — **Dosenbach et al. 2010** (doi 10.1126/science.1194144); classic,
    open-ish data; does reported accuracy survive site-aware CV?
  - a diagnosis classifier whose accuracy collapses under leakage-free CV.

## Lane E — EEG
- **Data**: OpenNeuro EEG, MNE sample datasets (`mne.datasets`).
- **Levers**: **reference montage**, **filter band**, ICA artifact removal, epoch window.
- **Failure axes**: confident-refutation, wrong-cause.
- Seed candidates:
  - an ERP or band-power effect (e.g. alpha, P300) whose significance depends on the reference/filter.

---

## How to pull more candidates
```bash
cd landscape/results
# topics rising fastest (good task material):
tail -n +2 landscape_topic_summary.csv | sort -t, -k5 -rn | head -30
# ranked anchor papers for a topic:
awk -F, -v t="attention" '$1==t' topic_paper_map.csv
```
Full backlog: `topic_paper_map.csv` (555 rows) · `topic_papers_library.csv` (524) ·
open problems per topic: `landscape/docs/OPEN_PROBLEMS.md`.
