# Child-only movie connectivity and motion sensitivity (DEVCONN-001)

Fair et al. (2009), *Functional Brain Networks Develop from a “Local to
Distributed” Organization* ([paper](https://doi.org/10.1371/journal.pcbi.1000381)),
motivates the question. Apply a related distance-based connectivity analysis to
the released ds000228 movie-watching derivatives. This is a **paper-derived
methods and sensitivity case**, not a reproduction of Fair's resting-state
cohort, four-network analysis, or developmental finding.
The specific motivation is the paper's Figure 5 distance-dependent child/adult
comparison, not Figure 4 community detection. The tertile Fisher-z summaries and
child-only rank inference below are explicit adaptations, not the paper's estimator.

Use the fixed originals under `/app/data/devconn`, whose complete identities are
in `/app/source_manifest.json`: 155 participants (122 children, 33 adults), their
full confound tables and phenotype table, and the original 264 Power ROI centers.
Everything needed is available offline. Do not fetch substitute data. Preserve
literal participant/ROI IDs and join by identity, not position.

The public numerical contract is `/app/method_contract.json`, with explanations
in `/app/ANALYSIS_CONTRACT.md` and output fields in `/app/output_schema.json`.
`/app/reporting_kernel.py` is the disclosed downstream reporting implementation;
you may use it or implement an equivalent calculation. Source extraction and
cleaning still need to be reconstructed from the originals. The verifier compares
source-close primitives and then replays the submitted cleaned signals, not a
hidden target effect or a prescribed conclusion.

Extract 5 mm spheres at every Power coordinate, using the stated sphere support
convention. Keep all 168 released frames for each participant. Preserve original
header/scaling metadata; use the separately documented operational MNI-mm/TR=2 s
convention, not an invented measured onset. Detrend and band-pass both ROI signals
and the 14 specified nuisance columns at 0.009–0.08 Hz, regress the nuisance design,
and sample-standardize. FD is a separate motion covariate, not a nuisance regressor.
Only the declared missing tokens may be zero-filled, with their locations recorded.

Use signed correlations and average their Fisher-z transforms within strict lower
and upper distance-tertile bins. Do **not** transform these means back with tanh.
Segregation is short-range minus long-range. Report canonical-active ROI and edge
coverage; undefined values must remain explicitly unavailable rather than become
zeros, dropped people, or replacement draws.

For children only, report age Spearman and FD-rank-adjusted associations for all
three metrics, and 1,000 seed-11 participant-bootstrap draws with percentile CIs.
Retain child/adult means and signed segregation Welch descriptives, both for the
full cohort and the separate strict FD<0.2 restriction. This restriction is not
motion matching. Recompute rank/variance support and degrees of freedom as stated
in the public contract, including degenerate and undefined cases.

Write these five files to `/app/output`:

- `signal_evidence.npz`: raw and cleaned ROI signals, identity/activity axes, and
  complete bootstrap receipts with defined/status masks.
- `connectivity_metrics.csv`: all 155 participant metrics, covariates and edge counts.
- `age_effects.json`: child inference, uncertainty, group means and Welch descriptives.
- `run_metadata.json`: source identities, headers, missingness, geometry and QC receipts.
- `findings.md`: the measured results, uncertainty, coverage and interpretation limits.

Coherent output-axis permutations and numerically equivalent implementations are
accepted. Scores are binary: one complete source-bound validation must pass;
there is no proportional-scoring promise. No direction, attenuation, significance,
effect-size floor, narrative keyword, or implementation version is required.
If a precondition fails, preserve the evidence, exit nonzero, and write a
`failure_report.json` in a safe output directory. Do not change inputs or overwrite
an earlier output to make the task pass. See `/app/SOURCE_NOTICE.md` for provenance
and the unresolved license notice attached to the packaged Power coordinates.
