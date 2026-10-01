# Child-only movie-data connectivity/motion sensitivity (DEVCONN-001)

Fair et al. (2009), "Functional Brain Networks Develop from a Local to Distributed
Organization", motivates the question. This task uses public ds000228 movie-watching
data as a paper-derived methods case, not a reproduction of Fair's resting-state
four-network finding.

Use all155 subjects from nilearn.datasets.fetch_development_fmri (122 children,33 adults),
joining age/group by actual participant_id, not array position. Extract the Power2011
264 coordinates with5mm spheres. Preprocess with detrend,zscore_sample,bandpass.009–.08Hz,
TR2s and nuisance sixmotion+six aCompCor+WM+CSF (zero-fill missing confound values).

Use Euclidean ROI-pair distances. Short-range edges fall strictly below the lower
distance tertile; long-range strictly above the upper tertile. Average Fisher-z
correlations within each bin. Segregation is short_range-long_range.

Primary age estimands are children only. For short_range,long_range,segregation,
report Spearman r/p and motion-adjusted rank correlation r/p (residualize connectivity
and age ranks against meanFD rank+intercept,df=n-3). Include participant-bootstrap95%
percentile CIs for both correlations: sort child rows by actual subject_id, then
1000 complete-row resamples using default_rng seed11. Preserve child/adult means.
FD<.2 group comparison is low-motion restriction, not matching; report Welch t,p
and sample counts. Pooled-child/adult age associations, if included, are exploratory.

Write to OUTPUT_DIR (default /app/output):
- connectivity.csv: exactly155 unique subject_id,age,group,short_range,long_range,
  segregation,mean_fd. MeanFD is mean zero-filled framewise_displacement.
- age_effects.json: population="children_only",n_children,n_adults;
  children_age_spearman measure objects with r,p,ci95,motion_adjusted_r,
  motion_adjusted_p,motion_adjusted_ci95,n; group_means; motion_control containing
  segregation_low_motion_restriction with t,p,n_child,n_adult,fd_thresh.
- run_metadata.json: analysis_scope="paper-derived child-only movie-data motion sensitivity",
  cohort, atlas/bins, preprocessing, original-source SHA256 receipts.
- findings.md: measured associations, uncertainty and limitations. No forced attenuation,
  non-significance or causal-motion-artifact conclusion. Do not infer absence from p>.05.

If data/cohort integrity cannot be established, exit nonzero and write parseable
failed_precondition metadata and a reason in age_effects.json/findings.md.
