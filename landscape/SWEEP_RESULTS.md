# Step-0 sweep — full coverage of the 87 remaining topics (2026-08-05)

13-agent workflow (`wf_8d925009-4fb`). Every remaining landscape topic Step-0'd on cached data.

**BUILD 5 · DROP 32 · BLOCKED 39 · NO-TASK 11 = 87**

BUILD → built to full spec (BRAINAGE-001 = prediction/brain age/normative-modeling; HARMON-001 = harmonization; DMN-GSR skipped as SOCIALBRAIN dup). BLOCKED = needs data we don't have (diffusion/PET/MRS/genetics/HCP/ABCD/UKB). NO-TASK = infrastructure/dataset/standard.

| topic | verdict | failure axis / reason |
|---|---|---|
| brain age | BUILD | regression-to-the-mean age bias in brain-age gap not corrected (trap b: fails proper handling / c: age confound) |
| default mode network | BUILD | Global signal regression, a defensible/commonly-recommended denoising step, mathematically shifts correlations negative (Murphy 2009, Saad 2012), so the reported DMN vs task-positi |
| harmonization | BUILD | over-correction: ComBat/site-removal WITHOUT preserving the biological covariate destroys real signal when covariate is confounded with batch (method-misuse; opposite of the DROPPE |
| normative modeling | BUILD | Brain-age delta (predicted - chronological age) is corrupted by regression-to-the-mean proportional bias; the UN-CUED check is de Lange & Cole (2020) age-bias correction of the del |
| prediction | BUILD | regression-to-the-mean confound in a DERIVED prediction metric (the 'brain-age gap' pred-true is spuriously correlated with true age; needs bias-correction before interpretation) |
| attention | DROP | CPM neuromarker leakage / effect-size -- but axis dropped and behavioral data absent |
| autism | DROP | duplicate — already-built / already-dropped axes |
| biomarker | DROP | biomarker over-claim: group difference does not enable single-subject prediction / does not generalize |
| brain atlas | DROP | arbitrary-parameter (atlas) determines reported quantity |
| cerebellum | DROP | over-claim / hard winner-take-all assignment instability |
| classification | DROP | Interpreting linear-classifier weight maps as 'the brain regions that drive the class difference' (should apply the Haufe transform A = Cov(X)w to recover the encoding/activation p |
| convolutional neural network | DROP | leakage / confound (CV must respect site grouping) |
| cortical parcellation | DROP | arbitrary-parameter (parcellation/resolution) determines reported quantity |
| deep learning | DROP | CV site-leakage / out-of-site non-generalization (pooled k-fold inflates over leave-one-site-out) |
| explainability | DROP | raw decoder weights interpreted as feature importance instead of forward pattern A = Cov(X)·W |
| external validation | DROP | internal CV optimism vs external generalization |
| frontoparietal network | DROP | Flexible-hub / high global-variable-connectivity claim depends on community-detection resolution and edge threshold (participation-coefficient hub axis) — already covered. |
| functional connectivity | DROP | over-claim / preprocessing artifact -- global signal regression (GSR) FABRICATES the reported anticorrelation between task-positive and task-negative (DMN) networks |
| general linear model | DROP | first-level GLM temporal-autocorrelation / prewhitening; group-level mass-univariate multiple comparisons |
| graph neural network | DROP | confound (scan site / head motion) and CV-leakage — tested; fail, weak, or duplicate |
| gray matter volume | DROP | head-size (TIV/ICV) confound on GM-volume group difference — but conventionally corrected |
| hippocampus | DROP | would duplicate built VBM-smoothing / dropped aging & AD |
| language | DROP | group-vs-individual / arbitrary-threshold laterality index (candidate) |
| motor control | DROP | n/a (finding robustly real) |
| neurodevelopment | DROP | duplicate — motion confound & age-FC specification instability already built |
| perception | DROP | leakage / circularity |
| psychiatric disorders | DROP | single-subject psychiatric-diagnosis prediction pitfalls (confound / CV leakage / effect size) |
| resting-state fMRI | DROP | GSR-induced anticorrelation (same as functional connectivity) -- no distinct uncovered trap |
| salience network | DROP | over-claim / network separability |
| sample size | DROP | Small-N brain-behavior correlations are unstable/inflated (sampling variability + winner's curse) |
| sensorimotor network | DROP | over-claim / robustness |
| social cognition | DROP | confident-refutation / GSR-dependence |
| statistical parametric mapping | DROP | multiple comparisons / cluster-extent false-positive inflation |
| structural MRI | DROP | Smoothing-kernel / preprocessing dependence of morphometric group differences — but this axis is already built. |
| subcortical volume | DROP | brain-size confound / allometric-vs-linear scaling correction determines the group conclusion |
| task fMRI | DROP | circularity / double-dipping (non-independent ROI) |
| visual cortex | DROP | decoding cross-validation validity / distributed-representation robustness |
| MEG | BLOCKED | n/a — no MEG data; method/hardware-only anchors |
| MRS | BLOCKED | n/a — no spectroscopy data available to reproduce any finding. |
| PET | BLOCKED | N/A (data-blocked) |
| arterial spin labeling | BLOCKED | n/a — no perfusion data |
| bipolar disorder | BLOCKED | n/a — blocked on data (no bipolar cohort) |
| brain tumor | BLOCKED | would-be: segmentation-metric / detection-accuracy over-claim, or tumor-mask threshold determines resection modeling |
| cortical thickness | BLOCKED | n/a — blocked on data (no subject-level thickness) |
| diffusion MRI | BLOCKED | n/a — no diffusion data |
| emotion | BLOCKED | n/a — no emotion/affect task-fMRI available to reproduce an emotion-processing finding. |
| enigma | BLOCKED | N/A (data-blocked) |
| epilepsy | BLOCKED | n/a — no epilepsy patient data available |
| episodic memory | BLOCKED | n/a — no episodic-memory paradigm data available |
| executive function | BLOCKED | n/a -- reproducing any primary EF finding requires task-fMRI + an EF behavioral battery not in cached data |
| fractional anisotropy | BLOCKED | N/A (data-blocked) |
| high field MRI | BLOCKED | would-be: resolution/field-strength over-claim, or sub-mm structure effect not surviving null |
| imaging genetics | BLOCKED | n/a — no analysis possible without genotypes |
| individualized parcellation | BLOCKED | would-be: group-average parcellation result does not describe individuals; individualized vs group parcels change connectome result |
| major depression | BLOCKED | clustering imposes spurious subtypes (cluster-validity null) |
| multimodal imaging | BLOCKED | multimodal fusion / spatial-map correlation (would-be) |
| multiple sclerosis | BLOCKED | n/a — no MS patient or diffusion data available |
| pain | BLOCKED | leakage/generalization of a multivariate signature (would-be) |
| parkinson disease | BLOCKED | biomarker/progression modeling (would-be) |
| quantitative MRI | BLOCKED | n/a (data unavailable) |
| reward | BLOCKED | n/a — blocked on data (no reward task fMRI) |
| schizophrenia | BLOCKED | N/A — data-blocked before any trap can be assessed |
| segmentation | BLOCKED | n/a — cannot reproduce on cached data |
| sleep | BLOCKED | n/a — no sleep-staged data to reproduce state-dependent connectivity changes. |
| stroke | BLOCKED | lesion-symptom inference / confounds (would-be) |
| structural connectivity | BLOCKED | n/a — data-blocked |
| surface area | BLOCKED | n/a — no surface data |
| susceptibility weighted imaging | BLOCKED | n/a — data-blocked |
| thalamus | BLOCKED | n/a |
| tractography | BLOCKED | diffusion-model / tractography reliability (would-be) |
| transdiagnostic | BLOCKED | n/a — cannot reproduce shared structural substrate |
| traumatic brain injury | BLOCKED | n/a — no TBI cohort |
| treatment response | BLOCKED | data-driven subtype instability (a) — but requires treatment-outcome cohort |
| uk biobank | BLOCKED | n/a — dataset unavailable + infrastructure topic |
| white matter | BLOCKED | n/a — data-blocked |
| working memory | BLOCKED | n/a — data-blocked |
| abcd study | NO-TASK | n/a — topic is a named dataset/cohort, not an analysis finding |
| bids | NO-TASK | N/A (infrastructure/standard) |
| data sharing | NO-TASK | n/a — infrastructure/meta-science, not an analysis finding |
| fmriprep | NO-TASK | N/A (infrastructure, not a finding) |
| human connectome project | NO-TASK | n/a (infrastructure/dataset) |
| neurovault | NO-TASK | N/A (infrastructure) |
| openneuro | NO-TASK | n/a - data-sharing repository / standard, not an analysis finding |
| preregistration | NO-TASK | N/A (meta-science practice) |
| quality control | NO-TASK | infrastructure/QC topic |
| registration | NO-TASK | n/a - no empirical brain finding; registration is a preprocessing method |
| surface reconstruction | NO-TASK | n/a — topic is a preprocessing method/infrastructure |
