# TASKFC-001 — canonical-response connectivity sensitivity

This task retains the public ten-person language-localizer demo and the original
bilateral 8-mm occipital spheres. It measures the signed change between
nuisance-cleaned and canonical-Glover-task-regressed whole-run connectivity.
The participant is the independent unit; all ten are retained, including
explicit undefined outcomes. The two-model contract is public.

## Scientific scope

[Cole et al. 2019](https://doi.org/10.1016/j.neuroimage.2018.12.054), Methods 2.7
and Figure 4, motivate examining task-response sensitivity. This is not that
paper's simulation/empirical result, FIR correction, SPM canonical implementation
or condition-specific analysis. A raw-minus-residual difference cannot identify
intrinsic coupling or prove successful removal of confounding. No decrease,
significance, population result or biological mechanism is prescribed.

The prior proposal's numerical tables, causal explanations, hidden background-FC
requirements, prose gates and hardness claims are retired. Historical answer-bank
values do not define this revision. This is a method control, provisionally easy;
model difficulty is uncalibrated.

## Reproducible inputs and estimator

The fixed source is the Nilearn-linked OSF `3dj2a` archive, version 1, with full
published archive checksum authentication and per-member identities. Forty-seven
original members plus the pinned Nilearn notice are baked into the image. No
runtime network, alternate cache/run, generated cohort or synthetic artifact is
used. Source licensing/lineage differences are retained in `SOURCE_NOTICE.md`;
local validation does not authorize publishing the source data or an image.

All runs contain 229 frames and matching TR=1.5-s headers/sidecars. The retained
0.75-s frame origin is explicitly an operational convention. Physical native-grid
sphere support, float64 means, exact event/motion membership, unregularized
Glover/cosine designs, SVD rank/projection, numerical activity and complete-cohort
Fisher/paired-t arithmetic are specified in the public method and output schema.
The rank/support policy is numerical resolution, not biological QC.

## Verifier and evidence boundary

The verifier independently authenticates sources and reconstructs ROI means,
designs, residuals, rank and support. Accepted source-close residuals drive one
replay of every downstream scalar. Rounded designs are never refitted; rounded
CSV correlations never become a second group-estimator input. There is no
hidden bank, expected outcome band, sign/count requirement or prose keyword.
Oracle and grader share declared nibabel header interpretation, HRF/LAPACK and
NumPy/SciPy primitives; independent decoding and implementation checks do not
independently validate those common dependencies.

Source-free malformed-input, geometry, rank, inactive-support and signed/undefined
arithmetic cases qualify the contract. Authoring-only equivalence/mutation
controls are kept separate from production acceptance: an accepted submission
need not survive an extra perturbation near a tolerance or byte limit.

Completion requires source-bound native execution, oracle/independent agreement,
offline Harbor reward, final-commit/image/source/artifact identity and retained
stdout/config/results. See `authoring/REPAIR_STATUS.md` for the achieved tier.
Local engineering tests and oracle success are neither paper replication nor
evidence that Sol cannot solve this task. No frontier-agent calibration is claimed.
