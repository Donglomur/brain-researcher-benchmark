# Topic roadmap — 111 landscape topics → tasks (toward ~50 hard)

Generated 2026-08-04 from `landscape/results/{landscape_topic_summary, topic_paper_map}.csv` (111 topics, 845 topic→paper links).

**Legend:** ✅ built · ❌ dropped at Step-0 · ⭐ promising open (new/differentiated axis) · 🔵 candidate open (buildable, often axis-redundant) · ⚪ likely easy / infrastructure / dataset.

**Caveat:** the *anchor* shown is the landscape rank-1 (often a review/canonical — pick a *primary* empirical paper from the topic's lower ranks for Step-0). The *hard read* is a HEURISTIC prior (category + axis fit + this session's Step-0 experience) — **Step-0 is the real decider.**


**Status tally:** ✅ 16 built · ❌ 12 dropped · ⭐ 2 promising-new · 🔵 25 candidate · ⚪ 56 likely-easy/infra.


## inference (42)

| topic | | status / hard read | anchor (rank-1) |
|---|---|---|---|
| network neuroscience | ✅ | BUILT → CAUSAL | Rubinov & Sporns (2010) — *Complex network measures of brain connectivity: uses and interpretatio* [graph theory / network metrics] |
| deep learning | 🔵 | DL leakage / shortcut learning — overlaps DECODE | Haxby et al. (2001) — *Distributed and overlapping representations of faces and objects in ve* [MVPA / perception] |
| prediction | ✅ | BUILT → BRAINAGE | Shen et al. (2017) — *Using connectome-based predictive modeling to predict individual behav* [predictive modeling protocol] |
| machine learning | ✅ | BUILT → DECODE | Abraham et al. (2014) — *Machine learning for neuroimaging with scikit-learn* [software / ML pipeline] |
| biomarker | 🔵 | biomarker over-claim / tiny effect — overlaps BWAS | Woo et al. (2017) — *Building better biomarkers: brain models in translational neuroimaging* [biomarker validation framework] |
| classification | 🔵 | classifier leakage / accuracy inflation — overlaps DECODE | Abraham et al. (2014) — *Machine learning for neuroimaging with scikit-learn* [software / ML pipeline] |
| convolutional neural network | 🔵 | CNN shortcut/leakage — overlaps DECODE | Haxby et al. (2001) — *Distributed and overlapping representations of faces and objects in ve* [MVPA / perception] |
| human connectome project | ⚪ | DATASET (enabler for structure-function / BWAS axes) | Van Essen et al. (2013) — *The WU-Minn Human Connectome Project: an overview* [dataset / consortium] |
| external validation | 🔵 | in-sample vs out-of-sample gap — leakage variant | Varoquaux (2018) — *Cross-validation failure: small sample sizes lead to large error bars* [ML validation / sample size] |
| graph theory | ❌ | dropped — small-world verdict robust (σ>1 at all thresholds); no trap | Rubinov & Sporns (2010) — *Complex network measures of brain connectivity: uses and interpretatio* [graph theory / network metrics] |
| explainability | ⭐ | saliency maps fail sanity checks (Adebayo 2018) — NEW axis (interpretability illusion) | Haufe et al. (2014) — *On the interpretation of weight vectors of linear models in multivaria* [model interpretability] |
| dynamic functional connectivity | ✅ | BUILT → DYNFC | Allen et al. (2014) — *Tracking whole-brain connectivity dynamics in the resting state* [dynamic FC pipeline] |
| quality control | ⚪ | infrastructure, not an analysis trap | Esteban et al. (2017) — *MRIQC: Advancing the automatic prediction of image quality in MRI from* [quality control pipeline] |
| treatment response | ⚪ | clinical prediction; leakage — needs trial data | Woo et al. (2017) — *Building better biomarkers: brain models in translational neuroimaging* [biomarker validation framework] |
| site effects | ❌ | dropped — easy-control (existing AGE-SITE task) | Johnson et al. (2007) — *Adjusting batch effects in microarray expression data using empirical * [ComBat / batch effects] |
| harmonization | ✅ | BUILT → HARMON | Johnson et al. (2007) — *Adjusting batch effects in microarray expression data using empirical * [ComBat / batch effects] |
| abcd study | ⚪ | DATASET (enabler for BWAS / developmental axes) | Casey et al. (2018) — *The Adolescent Brain Cognitive Development (ABCD) study: Imaging acqui* [dataset / cohort acquisition] |
| graph neural network | 🔵 | GNN leakage on connectomes — overlaps DECODE | Rubinov & Sporns (2010) — *Complex network measures of brain connectivity: uses and interpretatio* [graph theory / network metrics] |
| connectome-based predictive modeling | ❌ | dropped — CPM leakage weak (+0.065 at n=455); DECODE covers | Finn et al. (2015) — *Functional connectome fingerprinting: identifying individuals using pa* [connectome fingerprinting] |
| multiple comparisons | ✅ | BUILT → AUTCONN | Friston et al. (1994) — *Statistical parametric maps in functional imaging: A general linear ap* [statistical modeling / GLM] |
| sample size | 🔵 | power/winner's-curse — effect-size (BWAS covers) | Marek et al. (2022) — *Reproducible brain-wide association studies require thousands of indiv* [sample size / BWAS] |
| uk biobank | ⚪ | DATASET (enabler for BWAS / imaging-genetics) | Miller et al. (2016) — *Multimodal population brain imaging in the UK Biobank prospective epid* [dataset / cohort pipeline] |
| normative modeling | ✅ | BUILT → BRAINAGE | Marquand et al. (2016) — *Understanding heterogeneity in clinical cohorts using normative models* [normative modeling] |
| effect size | ❌ | dropped — one-directional; BWAS covers | Marek et al. (2022) — *Reproducible brain-wide association studies require thousands of indiv* [sample size / BWAS] |
| statistical power | ❌ | dropped — BWAS covers | Marek et al. (2022) — *Reproducible brain-wide association studies require thousands of indiv* [sample size / BWAS] |
| precision functional mapping | ❌ | dropped — HUBMAP covers (aggregation) | Finn et al. (2015) — *Functional connectome fingerprinting: identifying individuals using pa* [connectome fingerprinting] |
| general linear model | 🔵 | cluster/threshold inflation — mult-comp (AUTCONN covers) | Friston et al. (1994) — *Statistical parametric maps in functional imaging: A general linear ap* [statistical modeling / GLM] |
| head motion | ❌ | dropped — DEVCONN covers; ABIDE/ADHD premise fails | Esteban et al. (2017) — *MRIQC: Advancing the automatic prediction of image quality in MRI from* [quality control pipeline] |
| brain-wide association | ✅ | BUILT → BWAS | Marek et al. (2022) — *Reproducible brain-wide association studies require thousands of indiv* [sample size / BWAS] |
| openneuro | ⚪ | dataset infrastructure — enabler, not a trap | Markiewicz et al. (2021) — *The OpenNeuro resource for sharing of neuroscience data* [data repository / BIDS] |
| individualized parcellation | 🔵 | parcellation-dependence of results — robustness | Finn et al. (2015) — *Functional connectome fingerprinting: identifying individuals using pa* [connectome fingerprinting] |
| fmriprep | ⚪ | pipeline infrastructure — enabler | Esteban et al. (2019) — *fMRIPrep: a robust preprocessing pipeline for functional MRI* [preprocessing pipeline] |
| preregistration | ⚪ | meta-science — not a data trap | Poldrack et al. (2017) — *Scanning the horizon: towards transparent and reproducible neuroimagin* [reproducibility / open science] |
| cluster inference | ❌ | dropped — task activation robust (891-2034 survive FWE); no trap | Eklund et al. (2016) — *Cluster failure: Why fMRI inferences for spatial extent have inflated * [statistical inference / cluster correction] |
| neurovault | ⚪ | repository infrastructure | Gorgolewski et al. (2015) — *NeuroVault.org: a web-based repository for collecting and sharing unth* [data repository / statistical maps] |
| bids | ⚪ | standard/infrastructure | Gorgolewski et al. (2016) — *The Brain Imaging Data Structure, a format for organizing and describi* [standard / data organization] |
| enigma | ⚪ | consortium/DATASET (enabler) | Thompson et al. (2014) — *The ENIGMA Consortium: large-scale collaborative analyses of neuroimag* [consortium / harmonized analysis] |
| imaging genetics | 🔵 | genome-scale multiple comparisons — mult-comp variant | Thompson et al. (2014) — *The ENIGMA Consortium: large-scale collaborative analyses of neuroimag* [consortium / harmonized analysis] |
| data sharing | ⚪ | meta-science/infrastructure | Markiewicz et al. (2021) — *The OpenNeuro resource for sharing of neuroscience data* [data repository / BIDS] |
| independent component analysis | ✅ | BUILT → ICA | Beckmann & Smith (2004) — *Probabilistic independent component analysis for functional magnetic r* [ICA / fMRI decomposition] |
| statistical parametric mapping | 🔵 | SPM cluster inference — mult-comp (AUTCONN covers) | Friston et al. (1994) — *Statistical parametric maps in functional imaging: A general linear ap* [statistical modeling / GLM] |
| reproducibility | ✅ | BUILT → MULTIVERSE | Poldrack et al. (2017) — *Scanning the horizon: towards transparent and reproducible neuroimagin* [reproducibility / open science] |

## organization (25)

| topic | | status / hard read | anchor (rank-1) |
|---|---|---|---|
| default mode network | ⚪ | descriptive/organization — likely easy unless a robustness lever exists | Raichle et al. (2001) — *A default mode of brain function* [default mode network] |
| frontoparietal network | ⚪ | descriptive/organization — likely easy unless a robustness lever exists | Dosenbach et al. (2008) — *A dual-networks architecture of top-down control* [control networks / frontoparietal] |
| salience network | ⚪ | descriptive/organization — likely easy unless a robustness lever exists | Seeley et al. (2007) — *Dissociable intrinsic connectivity networks for salience processing an* [salience / control networks] |
| thalamus | ⚪ | descriptive/organization — likely easy unless a robustness lever exists | Behrens et al. (2003) — *Non-invasive mapping of connections between human thalamus and cortex * [probabilistic tractography / thalamus] |
| cerebellum | ⚪ | descriptive/organization — likely easy unless a robustness lever exists | Buckner et al. (2011) — *The organization of the human cerebellum estimated by intrinsic functi* [cerebellar networks / fcMRI] |
| sensorimotor network | ⚪ | descriptive/organization — likely easy unless a robustness lever exists | Biswal et al. (1995) — *Functional connectivity in the motor cortex of resting human brain usi* [resting-state FC method] |
| brain atlas | ⚪ | descriptive/organization — likely easy unless a robustness lever exists | Yeo et al. (2011) — *The organization of the human cerebral cortex estimated by intrinsic f* [network atlas / parcellation] |
| hubs | ✅ | BUILT → HUBMAP | Cole et al. (2013) — *Multi-task connectivity reveals flexible hubs for adaptive task contro* [task connectivity / hubs] |
| cortical parcellation | 🔵 | parcellation-granularity dependence — robustness/multiverse | Yeo et al. (2011) — *The organization of the human cerebral cortex estimated by intrinsic f* [network atlas / parcellation] |
| structural connectivity | ⚪ | descriptive/organization — likely easy unless a robustness lever exists | Basser et al. (1994) — *MR diffusion tensor spectroscopy and imaging* [diffusion tensor method] |
| hippocampus | ⚪ | descriptive/organization — likely easy unless a robustness lever exists | Yushkevich et al. (2015) — *Automated segmentation of hippocampal subfields from high-resolution s* [hippocampal subfield segmentation] |
| gray matter volume | ⚪ | descriptive/organization — likely easy unless a robustness lever exists | Ashburner & Friston (2000) — *Voxel-based morphometry—the methods* [VBM / morphometry] |
| white matter | ⚪ | descriptive/organization — likely easy unless a robustness lever exists | Basser et al. (1994) — *MR diffusion tensor spectroscopy and imaging* [diffusion tensor method] |
| tractography | ⭐ | diffusion false positives (Maier-Hein 2017) — NEW modality; needs dipy | Behrens et al. (2003) — *Non-invasive mapping of connections between human thalamus and cortex * [probabilistic tractography / thalamus] |
| segmentation | ⚪ | descriptive/organization — likely easy unless a robustness lever exists | Fischl et al. (2002) — *Whole brain segmentation: automated labeling of neuroanatomical struct* [segmentation / subcortical labels] |
| structure-function coupling | ✅ | BUILT → MAPCORR | Rubinov & Sporns (2010) — *Complex network measures of brain connectivity: uses and interpretatio* [graph theory / network metrics] |
| modularity | ✅ | BUILT → MODULAR | Rubinov & Sporns (2010) — *Complex network measures of brain connectivity: uses and interpretatio* [graph theory / network metrics] |
| cortical thickness | 🔵 | smoothing/software dependence — over-claim (VBMAGE-like) | Dale et al. (1999) — *Cortical surface-based analysis I: Segmentation and surface reconstruc* [surface reconstruction] |
| surface reconstruction | ⚪ | descriptive/organization — likely easy unless a robustness lever exists | Dale et al. (1999) — *Cortical surface-based analysis I: Segmentation and surface reconstruc* [surface reconstruction] |
| surface area | ⚪ | descriptive/organization — likely easy unless a robustness lever exists | Dale et al. (1999) — *Cortical surface-based analysis I: Segmentation and surface reconstruc* [surface reconstruction] |
| registration | ⚪ | descriptive/organization — likely easy unless a robustness lever exists | Avants et al. (2011) — *A reproducible evaluation of ANTs similarity metric performance in bra* [registration / ANTs] |
| voxel-based morphometry | ✅ | BUILT → VBMAGE | Ashburner & Friston (2000) — *Voxel-based morphometry—the methods* [VBM / morphometry] |
| subcortical volume | ⚪ | descriptive/organization — likely easy unless a robustness lever exists | Fischl et al. (2002) — *Whole brain segmentation: automated labeling of neuroanatomical struct* [segmentation / subcortical labels] |
| fractional anisotropy | ⚪ | descriptive/organization — likely easy unless a robustness lever exists | Basser et al. (1994) — *MR diffusion tensor spectroscopy and imaging* [diffusion tensor method] |
| visual cortex | ⚪ | descriptive/organization — likely easy unless a robustness lever exists | Haxby et al. (2001) — *Distributed and overlapping representations of faces and objects in ve* [MVPA / perception] |

## measurement (14)

| topic | | status / hard read | anchor (rank-1) |
|---|---|---|---|
| functional connectivity | 🔵 | method-robustness candidate (modality-specific trap) | Biswal et al. (1995) — *Functional connectivity in the motor cortex of resting human brain usi* [resting-state FC method] |
| EEG | ✅ | BUILT → EEGVC | Delorme & Makeig (2004) — *EEGLAB: an open source toolbox for analysis of single-trial EEG dynami* [EEG pipeline / toolbox] |
| resting-state fMRI | 🔵 | method-robustness candidate (modality-specific trap) | Biswal et al. (1995) — *Functional connectivity in the motor cortex of resting human brain usi* [resting-state FC method] |
| structural MRI | 🔵 | method-robustness candidate (modality-specific trap) | Dale et al. (1999) — *Cortical surface-based analysis I: Segmentation and surface reconstruc* [surface reconstruction] |
| MRS | 🔵 | method-robustness candidate (modality-specific trap) | Provencher (2001) — *Automatic quantitation of localized in vivo 1H spectra with LCModel* [MRS quantification pipeline] |
| quantitative MRI | 🔵 | method-robustness candidate (modality-specific trap) | Tabelow et al. (2019) — *hMRI – A toolbox for quantitative MRI in neuroscience and clinical res* [qMRI toolbox] |
| susceptibility weighted imaging | 🔵 | method-robustness candidate (modality-specific trap) | Haacke et al. (2004) — *Susceptibility weighted imaging (SWI)* [SWI acquisition / processing] |
| task fMRI | 🔵 | method-robustness candidate (modality-specific trap) | Friston et al. (1994) — *Statistical parametric maps in functional imaging: A general linear ap* [statistical modeling / GLM] |
| multimodal imaging | 🔵 | method-robustness candidate (modality-specific trap) | Glasser et al. (2016) — *A multi-modal parcellation of human cerebral cortex* [multimodal atlas / parcellation] |
| diffusion MRI | 🔵 | tensor model fails at crossing fibers (Jeurissen 2013) — method trap | Basser et al. (1994) — *MR diffusion tensor spectroscopy and imaging* [diffusion tensor method] |
| MEG | ⚪ | source leakage — volume-conduction (EEGVC-like); MEG source data heavy | Oostenveld et al. (2011) — *FieldTrip: Open source software for advanced analysis of MEG, EEG, and* [M/EEG pipeline / toolbox] |
| arterial spin labeling | 🔵 | method-robustness candidate (modality-specific trap) | Alsop et al. (2015) — *Recommended implementation of arterial spin-labeled perfusion MRI for * [ASL consensus / pipeline] |
| high field MRI | 🔵 | method-robustness candidate (modality-specific trap) | Uğurbil et al. (2013) — *Pushing spatial and temporal resolution for functional and diffusion M* [high-field MRI / HCP methods] |
| PET | 🔵 | method-robustness candidate (modality-specific trap) | Logan et al. (1990) — *Graphical analysis of reversible radioligand binding from time-activit* [PET kinetic modeling] |

## phenotype (30)

| topic | | status / hard read | anchor (rank-1) |
|---|---|---|---|
| attention | ⚪ | phenotype — likely easy (reproduction agents can solve) unless a confound lever exists | Rosenberg et al. (2016) — *A neuromarker of sustained attention from whole-brain functional conne* [predictive connectomics / attention] |
| executive function | ⚪ | phenotype — likely easy (reproduction agents can solve) unless a confound lever exists | Barch et al. (2013) — *Function in the human connectome: task-fMRI and individual differences* [task fMRI battery / HCP] |
| sleep | ⚪ | phenotype — likely easy (reproduction agents can solve) unless a confound lever exists | Tagliazucchi et al. (2014) — *Large-scale brain functional modularity is reflected in slow electroen* [sleep / fMRI-EEG connectivity] |
| emotion | ⚪ | phenotype — likely easy (reproduction agents can solve) unless a confound lever exists | Barch et al. (2013) — *Function in the human connectome: task-fMRI and individual differences* [task fMRI battery / HCP] |
| aging | ❌ | dropped — GM atrophy robust in healthy (wrong-cause falsified) | Bethlehem et al. (2022) — *Brain charts for the human lifespan* [normative lifespan modeling] |
| alzheimer disease | ❌ | dropped — AD atrophy robust, no trap | Jack et al. (2010) — *Hypothetical model of dynamic biomarkers of the Alzheimer's pathologic* [disease biomarker model] |
| motor control | ⚪ | phenotype — likely easy (reproduction agents can solve) unless a confound lever exists | Biswal et al. (1995) — *Functional connectivity in the motor cortex of resting human brain usi* [resting-state FC method] |
| perception | ⚪ | phenotype — likely easy (reproduction agents can solve) unless a confound lever exists | Haxby et al. (2001) — *Distributed and overlapping representations of faces and objects in ve* [MVPA / perception] |
| social cognition | ⚪ | phenotype — likely easy (reproduction agents can solve) unless a confound lever exists | Barch et al. (2013) — *Function in the human connectome: task-fMRI and individual differences* [task fMRI battery / HCP] |
| major depression | ⚪ | phenotype — likely easy (reproduction agents can solve) unless a confound lever exists | Drysdale et al. (2017) — *Resting-state connectivity biomarkers define neurophysiological subtyp* [biomarker / depression subtypes] |
| working memory | ⚪ | phenotype — likely easy (reproduction agents can solve) unless a confound lever exists | Barch et al. (2013) — *Function in the human connectome: task-fMRI and individual differences* [task fMRI battery / HCP] |
| autism | ⚪ | phenotype — likely easy (reproduction agents can solve) unless a confound lever exists | Di Martino et al. (2014) — *The autism brain imaging data exchange: towards a large-scale evaluati* [dataset / autism FC] |
| pain | ⚪ | phenotype — likely easy (reproduction agents can solve) unless a confound lever exists | Wager et al. (2013) — *An fMRI-based neurologic signature of physical pain* [biomarker / pain signature] |
| stroke | ⚪ | phenotype — likely easy (reproduction agents can solve) unless a confound lever exists | Bates et al. (2003) — *Voxel-based lesion-symptom mapping* [lesion-symptom mapping pipeline] |
| parkinson disease | ⚪ | phenotype — likely easy (reproduction agents can solve) unless a confound lever exists | Marek et al. (2011) — *The Parkinson Progression Marker Initiative (PPMI)* [dataset / Parkinson cohort] |
| neurodevelopment | ⚪ | phenotype — likely easy (reproduction agents can solve) unless a confound lever exists | Dosenbach et al. (2010) — *Prediction of individual brain maturity using fMRI* [predictive modeling / development] |
| brain age | ✅ | BUILT → BRAINAGE | Marquand et al. (2016) — *Understanding heterogeneity in clinical cohorts using normative models* [normative modeling] |
| mild cognitive impairment | ❌ | dropped — MMSE~GM absent on OASIS (COGVBM) | Jack et al. (2010) — *Hypothetical model of dynamic biomarkers of the Alzheimer's pathologic* [disease biomarker model] |
| reward | ⚪ | phenotype — likely easy (reproduction agents can solve) unless a confound lever exists | Knutson et al. (2001) — *Anticipation of increasing monetary reward selectively recruits nucleu* [reward task fMRI] |
| bipolar disorder | ⚪ | phenotype — likely easy (reproduction agents can solve) unless a confound lever exists | Hibar et al. (2016) — *Subcortical volumetric abnormalities in bipolar disorder* [ENIGMA / bipolar disorder] |
| transdiagnostic | ⚪ | phenotype — likely easy (reproduction agents can solve) unless a confound lever exists | Goodkind et al. (2015) — *Identification of a common neurobiological substrate for mental illnes* [transdiagnostic meta-analysis] |
| adhd | ❌ | dropped — ADHD don't move more in nilearn subset | ADHD-200 Consortium (2012) — *The ADHD-200 Consortium: a model to advance the translational potentia* [dataset / ADHD] |
| traumatic brain injury | ⚪ | phenotype — likely easy (reproduction agents can solve) unless a confound lever exists | Bates et al. (2003) — *Voxel-based lesion-symptom mapping* [lesion-symptom mapping pipeline] |
| brain tumor | ⚪ | phenotype — likely easy (reproduction agents can solve) unless a confound lever exists | Menze et al. (2015) — *The Multimodal Brain Tumor Image Segmentation Benchmark (BRATS)* [benchmark / segmentation] |
| episodic memory | ⚪ | phenotype — likely easy (reproduction agents can solve) unless a confound lever exists | Yushkevich et al. (2015) — *Automated segmentation of hippocampal subfields from high-resolution s* [hippocampal subfield segmentation] |
| multiple sclerosis | ⚪ | phenotype — likely easy (reproduction agents can solve) unless a confound lever exists | Smith et al. (2006) — *Tract-based spatial statistics: voxelwise analysis of multi-subject di* [TBSS / group diffusion pipeline] |
| epilepsy | ⚪ | phenotype — likely easy (reproduction agents can solve) unless a confound lever exists | Delorme & Makeig (2004) — *EEGLAB: an open source toolbox for analysis of single-trial EEG dynami* [EEG pipeline / toolbox] |
| language | ⚪ | phenotype — likely easy (reproduction agents can solve) unless a confound lever exists | Binder et al. (2009) — *Where is the semantic system? A critical review and meta-analysis of 1* [meta-analysis / language] |
| schizophrenia | ⚪ | phenotype — likely easy (reproduction agents can solve) unless a confound lever exists | van Erp et al. (2016) — *Subcortical brain volume abnormalities in 2028 individuals with schizo* [ENIGMA / schizophrenia] |
| psychiatric disorders | ⚪ | phenotype — likely easy (reproduction agents can solve) unless a confound lever exists | Woo et al. (2017) — *Building better biomarkers: brain models in translational neuroimaging* [biomarker validation framework] |
