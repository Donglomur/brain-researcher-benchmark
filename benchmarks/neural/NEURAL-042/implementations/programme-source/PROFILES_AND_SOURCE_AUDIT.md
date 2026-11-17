# Primary-source audit and native/prospective profiles

This is a text, source-code and metadata audit. No authentic signal, NWB header, trial/clinical mask, identity key, fitted model, numerical reference or scientific score was opened or executed. Source code describes intended operations; it does not prove the released array's provenance, a historical execution or numerical parity.

## Primary sources and exact provenance

Daume et al., *Control of working memory maintenance by theta–gamma phase–amplitude coupling of human hippocampal neurons*, Nature (2024), DOI [10.1038/s41586-024-07309-z](https://doi.org/10.1038/s41586-024-07309-z). The bounded full-text source captured here is the Caltech-hosted in-press author deposit, not a claimed exact copy of the final publisher PDF: [Caltech PDF](https://authors.library.caltech.edu/records/es8hd-ftd63/files/s41586-024-07309-z.pdf). Its 6,779,756 bytes have SHA256 `8a84d527d42cebbe63bfcca9d2d04204eb21fb83a906d76ab057921cd59063c1` and MD5 `1b465b15adddcea5429d66e49b4726ff`, matching the repository metadata's MD5. It contains in-press placeholders. The PDF was held transiently in RAM, piped to installed pdftotext, and not saved as a local body. PAPER_PDF_EXTRACT.txt is its attributed layout-text transformation; typography, figures and layout were not exhaustively visually validated. The paper's CC BY 4.0 statement appears in the source. Deposited text is scientific evidence, not benchmark gold or permission to disclose patient data.

The publisher's [Supplementary Information](https://static-content.springer.com/esm/art:10.1038%2Fs41586-024-07309-z/MediaObjects/41586_2024_7309_MOESM1_ESM.pdf) is retained locally at primary-source/SUPPLEMENT.pdf, 598,313 bytes, SHA256 `8a59b8cbbcc4be022ff879414d912a4d68b2c8ff1fbc07d97fb867f2fc03fe81`; SUPPLEMENT_EXTRACT.txt is a pdftotext transformation. No screenshot result is counted as a visual inspection: the attempted web screenshots returned links, not inspected page images. Tables were read as text and used only for source-method interpretation, not reconstructed numerical result claims.

Author code is [rutishauserlab/SBCAT-release-NWB](https://github.com/rutishauserlab/SBCAT-release-NWB), pinned at `a25e8cc3f61630a428f190381745257d4506f148`. Its held paths/hashes are in SOURCE_BINDINGS.json. The source dataset is [DANDI 000673, version 0.240118.2135](https://dandiarchive.org/dandiset/000673/0.240118.2135). Exact asset UUID/path/size/digest metadata comes from held SOURCE_ASSETS.json, not a new array download. The root source license is BSD-3-Clause; embedded EEGLAB filtering helpers have GPL-2-or-later notices. The dataset's recorded license is CC BY 4.0. Dependency/runtime redistribution and clinical-use conditions require separate actual review; none is inferred from a top-level code license.

## What the original study establishes as source context

Main text and Methods describe 36 clinical participants, 44 recording sessions and 140 trials per session, with 70 trials at each load (1 or3). Memoranda are novel pictures, and the task's response mapping changes after the first70 trials. Maintenance durations are roughly2.5–2.8 seconds; the Methods give2.55–2.85 seconds and analyze the first2.5 seconds. The prospective half-open interval must be qualified from actual time axes rather than rounding these prose descriptions into invented timestamps.

The paper describes local bundle reference; interpolation of spike-related samples from−1 to+2 ms around detected spikes across the wires in a bundle; low-pass175 Hz; resampling to400 Hz; line-noise removal near60 and120 Hz. These operations can have full-record and cross-wire dependencies. A preparation algorithm cannot establish that the deposited LFP underwent them simply by obtaining a400-Hz array. Future lineage must identify what preprocessing is already present, its exact producer and excluded intervals. Reapplying preprocessing blindly is not acceptable.

Artifact handling in the paper includes across-trial amplitude standardization, extreme-sample clipping/restandardization, amplitude and jump thresholds, visual inspection, and regional/wire rejection for excess noise or epileptic activity. The paper reports roughly14.6% of trials removed on average, but that is not a usable trial mask. The current package's four Boolean clinical checks and free-text evidence schema are only a request for evidence; they do not constitute independent clinical adjudication or show equivalence to the original paper's masks.

The paper lists586 hippocampal LFP channels and describes137 channels significant for PAC, with a23-person patient-level sensitivity analysis restricted to significant channels. Those are printed historical analysis counts. They do not establish the number of channels eligible for this task's independent hippocampal anatomy + co-located sorted-unit + clinical-mask criterion. All36 source people and44 sessions remain in this design; no137-channel or23-person substitute is permitted.

The published behavioral PAC association includes reaction-time mixed models (Supplementary Table S2), not this task's exact correct-minus-incorrect PAC contrast. The latter is a prospective investigation. Category-neuron selectivity, PAC-neuron Poisson model interactions, inter-regional spike/field coherence and population noise geometry are other paper branches, not completed by this benchmark. Its success cannot be called reproduction of the complete Nature paper.

## Native profile N, as written

NWB_SBCAT_analysis_main.m permits importing1:44 files but calls NWB_samplePAC_LFP as an **example figure**, and the README explicitly identifies the example import. Full data import does not transform a one-channel helper into full-cohort reference computation. The main source is preserved byte-for-byte; its CP1252 smart-quote byte causes UTF-8 decoding failure, so the audit used a labeled CP1252 view without modifying the file.

NWB_samplePAC_LFP.m selects a specific source example (subject4/session1, channel49) and a historical stratified-trial MAT mask. The authentic mask was not read. Its submitted value n_surrogates=0 intentionally bypasses normalized inference; a comment names200 as the paper setting. call_cfc.m separately hard-codes a Windows example path and200 surrogates. Neither source proves complete original mask availability or historical full-cohort gold. NWB_samplePAC_SU.m has a distinct neuron example and timing; it cannot stand in for the LFP panel.

cfc_tort_comodulogram.m filters each long trial, computes analytic phase/amplitude, trims0.5 seconds at each edge and concatenates the retained trials. Its example extracts approximately[−0.5,3] seconds with inclusive logical indexing. The exact400-Hz grid/endpoints can yield a different sample count from the prospective1000; authentic source-grid/native-runtime parity remains required. The native grid is low centers2:2:14 Hz and high centers30:5:150 Hz, with low bandwidth2 Hz and high bandwidth twice the low center. The paper's primary high-gamma/theta interpretation does not make the whole broad grid equal to this task's30 selected pairs.

Native MI uses18 phase bins and amplitude-bin means. MATLAB histc's final endpoint bin can treat exact+180° differently from the prospective wrap-to−π convention. Undefined/empty bins and zero surrogate variance need their own explicit native disposition. The code's random trial permutations can retain fixed points; rng('shuffle') does not provide a deterministic seed lineage. The surrogate distribution is fit using normfit and converted to `(MI−estimated null mean)/estimated null SD`; the exact normfit/version conventions remain an actual native dependency gate. A missing or zero surrogate SD is not replaced by an invented epsilon.

## Prospective profile P, as frozen

P deliberately uses400-Hz1000-sample half-open[0,2.5) waveforms, without preceding/following samples; endpoint-value padding; per-trial convolution/Hilbert; low centers4 and6; high centers70:5:140; trial-count/nuisance matching; 200 nonzero cyclic trial rotations and200 within-trial amplitude shifts; and mean-subtracted corrected MI. This is a fixed, fully specified retrospective estimator. Its 144/four rows,11 metrics, hierarchy and RNG rules are in MATHEMATICS.md.

| Decision | Native history N | Canonical prospective P |
|---|---|---|
| Cohort for available PAC code | A selected example and unavailable historical MAT selection | All44/36 source roster, explicit channel/trial dispositions |
| Wire eligibility | Published PAC-significant selection for several analyses | Hippocampal anatomical/clinical/co-located-unit criterion, never effect/PAC significance |
| Epoch/filter edges | Longer real-data epoch then trim; exact endpoints need qualification |1000 samples, endpoint replication, no observed extra epoch samples |
| Grid |2:2:14 by30:5:150 |(4,6) by70:5:140,30 pairs |
| Trial selection | Historical correct-trial load subsampling/masks | Both load and within-load accuracy, count-only and nuisance-matched |
| Trial null | Full randperm including possible fixed points | Nonzero cyclic rotation, only n−1 possible shifts |
| Correction | Native estimated-null z-score when surrogates exist | MI−mean trial-null MI; no SD normalization |
| Temporal/shape checks | Native/supplement waveform and phase-coupling analyses | Fixed time-shift mean, early/late MI, harmonic PLV and slope-energy proxy |
| Subject summaries | Printed selected-channel subsets | Supported wires→sessions→people, all36 rows retained |

These are estimand changes. Agreement of filter coefficient formulas where inputs coincide does not validate whole-pipeline parity. No scalar conversion can generally turn P's matched mean subtraction into N's z-scored, differently selected/truncated analysis. Completing P measures numerical/scientific investigation under declared inputs; an optional native example anchor must be reported separately and cannot satisfy the full P reference requirement.

## Support and biological limits that can block scoring

A supported accuracy channel requires at least10 retained matched incorrect trials at **each** load. A necessary pre-matching condition is at least20 incorrect trials among the140 original trials: raw session accuracy at most120/140 (about85.71%). This is necessary, not sufficient: incorrect trials must be divided across both loads and survive clinical masks, strata and power/rate calipers. The paper's reported mean accuracy93.66% makes widespread unsupported accuracy estimates plausible, but neither its mean nor SD proves how many current sessions pass. No original labels were inspected. If no person supports either canonical endpoint, the primary score is null; complete reports can still contain genuine unsupported rows.

This is a decisive feasibility gate, not permission to lower the floor, pool loads, pool trials across sessions or replace accuracy by reaction time. A future lower-support hierarchical estimator or RT task would need a separately accepted change and cannot inflate the canonical benchmark count. Current source count/mask/property qualifications must be resolved before promising a scored study.

Published waveform controls distinguish oscillatory gamma from sharp-wave/harmonic artifacts using cycle and nesting analyses. P's scalar raw-slope proxy and harmonic PLV are weaker diagnostics; they must not be described as an implementation of bycycle or proof against every waveform confound. Trial matching on signal-derived power/rate and conditioning on correctness can induce selection/collider effects. None of these analyses identifies a causal mechanism. Printed positive load findings are prior scientific knowledge, not a required benchmark answer.

## Source-family and rights boundary

NEURAL-041 and042 draw from the same SBCAT source family; this proposal creates no new ID and does not call their datasets independent. Future benchmark partitioning should group source-family exposure and disclose cross-task reuse; it cannot claim unseen-source transfer after a model has solved the other task. The recorded44 asset bytes total23,447,043,476. That is source metadata, not authenticated local storage, intermediate-memory demand, qualified download availability or observed disk consumption.

The copied text extracts are attributed transformations of their cited primary PDFs, maintained as private research-source evidence in this design directory. The supplement PDF remains an explicitly pinned local external evidence body outside the proposed source-only Git payload; the full paper PDF is an external remote evidence body with a capture receipt. This document does not select public publication of the extracts or raw clinical material. Future packaging must preserve these distinctions and exact source-byte/transformation pins.
