# ToM–pain network GSR/motion sensitivity (SOCIALBRAIN-001)

Richardson et al. (2018, https://doi.org/10.1038/s41467-018-03399-2) reported increasing
ToM–pain network segregation with age during *Partly Cloudy*. This task is a
paper-derived sensitivity application on public ds000228 derivatives, not an exact
reproduction of the paper's primary-motor/artifact-adjusted preprocessing.

Use all155 subjects from nilearn.datasets.fetch_development_fmri (122 children,33 adults).
Join Age/Child_Adult using actual participant_id, not array position. Extract9mm spheres
at the MNI coordinates below. Use the reduced confounds: six motion parameters,
framewise_displacement, six a_comp_cor components, white_matter and csf, filling their
missing first-volume values with zero; detrend and zscore_sample the ROI signals.
Compute two pipelines: without and with an added detrended whole-brain global signal.
No additional temporal filter is required.

ToM coordinates: DMPFC(-2,56,28), MMPFC(0,54,20), VMPFC(0,46,-16),
PCC(0,-56,36), RTPJ(54,-56,24), LTPJ(-54,-56,24).
Pain/body: rSII(52,-24,22), lSII(-52,-24,22), rINS(38,4,6), lINS(-38,4,6),
dACC(0,8,38), MFG(0,16,46).

Aggregate correlations as tanh(mean(Fisher-z)) across off-diagonal within-network
edges and all across-network edges. Report within-ToM/within-pain under the no-GSR
pipeline and across-network under both. For children only, calculate Spearman r/p
and motion-adjusted rank r/p by residualizing age/connectivity ranks on meanFD rank
plus intercept (df=n-3). Report adult network means separately.

Write to OUTPUT_DIR (default /app/output):
- network_connectivity.csv: exactly155 unique actual subject_id,age,group,mean_fd,
  within_tom,within_pain,across_network,across_network_gsr.
- age_effects.json: each connectivity column's child r,p,motion_adjusted_rank_r/p;
  adult_means,n_children,n_adults.
- run_metadata.json: analysis_scope="paper-derived GSR/motion sensitivity adaptation",
  cohort, preprocessing, ROI definitions and source SHA256 receipts.
- findings.md: measured results and limitations. No predetermined null/negative pair
  is required. GSR sensitivity does not establish an artifact or refute the paper.

If data or cohort integrity cannot be established, exit nonzero, write parseable metadata
with status="failed_precondition" and a reason, and preserve a concise findings.md.
