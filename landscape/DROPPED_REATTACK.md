# DROPPED topics — re-attack record (2026-08-05)

All 32 topics that the first-pass Step-0 sweep marked **DROPPED** were re-examined by a 5-agent
workflow: each read *why* the topic was dropped, then tried a **different** failure axis to see if a
different clean trap exists (rescue false-drops). Every rescued candidate was then **re-verified by
re-running the probe** before any build. Outcome: **3 rescued and built**, 2 verified-real but not
built (Step-0 grading/redundancy drop), 27 confirmed drops.

## RESCUED → BUILT (3)

### gray matter volume → **GMVOL-001**
New axis vs the recorded drop (TIV confound but conventionally corrected): the **choice of head-size
correction method flips the sign** of the sex difference. OASIS VBM, healthy CDR=0 (119 M / 188 F),
re-verified: RAW total GM → M>F, d=+0.47, t=+4.04, **p=6.7e-5**; PROPORTION GM/eTIV → F>M, d=−0.36,
t=−3.08, **p=0.0023** (sign flip); ANCOVA GM~sex+eTIV → null, t=−1.10, **p=0.27**. Three contradictory
conclusions from one dataset by correction choice (Barnes 2010; O'Brien 2011). Oracle + adversarials pass.

### statistical parametric mapping → **SPMAR-001**
New axis vs the recorded drop (spatial cluster-extent / multiple comparisons): **temporal**
autocorrelation inflates first-level OLS-GLM false positives. ABIDE cc200 unfiltered, re-verified:
mean AR(1)=0.41; OLS GLM on a synthetic task regressor flags **20.1%** of region tests at p<0.05
(**4.0× nominal**); AR(1) prewhitening restores it to **7.1%** (Friston 2000; Woolrich 2001). Oracle
+ adversarials pass (including a partial "it's just noise" answer that omits autocorrelation → fails).

### graph neural network / explainability → **INTERP-001**
New axis vs the recorded drop (site/motion confound + CV-leakage): **classifier weights are not the
affected connections** (Haufe 2014 forward-vs-backward). ABIDE cc200 (956 subjects, 19900 edges),
re-verified: Spearman(|weight|, |group effect|)=**0.15** vs forward pattern Cov(X)·w=**0.88**; 9/50
top-weighted edges have no group difference; the 50 truly-most-affected edges rank at median
**17884/19900** by weight. Fills the roadmap's promising-open "interpretability illusion" slot.

## VERIFIED-REAL but NOT built — Step-0 drop (2)

- **convolutional neural network** — deep/nonlinear does NOT beat linear on ABIDE. Re-verified under
  leave-site-out CV: linear-logreg **0.671** > rbf-SVM 0.636 > MLP(100) 0.602 ≈ MLP(256,64) 0.603.
  Real and reproducible (Schulz 2020; He 2020), BUT the trap is *absence-of-benefit*, which grades
  softly (a competent agent who simply uses logistic regression neither over-claims nor demonstrates
  the insight — no clean separation), and the ML-pitfall cluster (DECODE/BWAS/HARMON/INTERP) is
  already dense. Dropped at Step-0 for grading-softness + redundancy, not for being false.
- **neurodevelopment** — FC→age prediction r=0.64 across a wide age range collapses to ~0.10 within
  any single developmental band (range restriction / between-group artifact). Real, but the agent
  itself flagged it as over-clustering with the already-built BRAINAGE (regression-to-the-mean) +
  BWAS (effect-size) predictive-modelling cluster. Dropped to avoid a third near-sibling.

## CONFIRMED DROP (27)
functional connectivity, resting-state fMRI, attention, deep learning, biomarker, classification,
structural MRI, frontoparietal network, salience network, motor control, perception, social
cognition, cerebellum, sensorimotor network, brain atlas, external validation, cortical parcellation,
hippocampus, explainability (as a stand-alone; its live axis is built as INTERP-001), autism, task
fMRI, sample size, general linear model, subcortical volume, language, visual cortex, psychiatric
disorders. In each case the different-axis probe either reproduced a robust/real effect (no trap),
was non-dramatic on cached data, or collapsed onto an already-built task (GSR→SOCIALBRAIN,
motion→DEVCONN/ADHD, site→HARMON, effect-size→BWAS, CV-leakage→DECODE, resolution→MODULAR/ICA). Full
per-topic evidence is in the workflow journal.

## Tally
32 DROPPED re-attacked = **3 rescued+built** (GMVOL, SPMAR, INTERP) + 2 verified-real-but-dropped
(grading/redundancy) + 27 confirmed drops. The re-attack was worth it: 3 clean new hard tasks, each
surfacing a real methodological failure the first-pass angle had missed.
