# Original-source method-control repair

The original legacy cohort and object identities were frozen before signal
analysis: 177 candidates, five documented unavailable derivative sets, 172
selected subjects (50 SCHZ, 122 CONTROL). All 697 selected original files were
acquired and authenticated: 2,305,653,613 bytes. No selected subject was silently
dropped and no synthetic replacement was introduced.

Source identity SHA256: 931a3e8792a0e8e8d503dd9d16b2e407fccbc609004b2b8fd77af6548e188854.

All 172 subjects' surface/confound axes and finite-value checks passed. One
original recording (sub-10524) has 128 frames; the other 171 have 152. Preserve
those lengths. Primary preprocessing code supports TR 2 s and FD in mm, with
the first FD undefined. Annotation labels explicitly identify Unknown (0) and
Medial_wall (42), leaving 74 named cortical parcels per hemisphere. The pial
headers' UNKNOWN-to-TALAIRACH identity transforms are recorded literally; use
stored coordinates with documented native SurfaceRAS/mm provenance, not a
claim of measured MNI registration or byte identity to the 2017 FS6 install.

The public numerical contract was frozen at 2026-10-02T04:18:47.592Z, before
parcel extraction, FC calculation or new group models:

- Method SHA256: 7378a0ccd4663907e2e8df3db724ba9caa3e21ee80b955ea637863db1769a23c.
- Source manifest SHA256: f4ea1c9f5a3a75d722fedd2cece082dd84502f20c5c7d2d11704c5bcc45594e3.

## Recorded local execution

The fixed sub-10159 pilot passed before full-cohort execution. The offline
oracle processed all 172 participants in 35.4 seconds with two CPUs and 8 GiB.
All 148 cortical parcels were valid in every subject, producing 1,871,016
subject-edge values on the common 10,878-edge family. No Fisher clipping was
needed. All nuisance ranks were 13; no participant or edge was dropped after
seeing the diagnosis result.

The measured short-range diagnosis coefficients were +0.03718198637 (crude),
-0.00086703310 (mean-FD adjusted), and +0.01383483833 in the strict low-FD
restriction. That restriction contains 125 participants: 27 SCHZ and 98 CONTROL.
These are conditional, signed observations, not preselected success targets.
Neither attenuation nor a change of significance establishes motion causation,
equivalence or absence of diagnosis-related signal.

A separate original-source implementation used fsum parcel means, manual
forward/backward SOS filtering, SVD nuisance projection, frame-ordered covariance
and FWL diagnosis estimation. It matched all identities, categorical decisions
and counters. Maximum raw-correlation difference was 8.17e-14; edge-statistic
difference was 1.51e-13. Raw parcel means, confounds and FD matched exactly.
Its 111 source-free fixtures are separate from original-data validation.

A third original-source route rebuilt the grading bank, consulting oracle
outputs only after source construction. It shares low-level readers/filter/QR
primitives and verifier statistics, not oracle arrays. The old 8,071-byte bank
is preserved outside this task; it is not used by the new verifier.

- New bank: 29,751,915 bytes.
- SHA256: b9bc12e0ed5b87b6eb733f8c0f0280acbd052acab99e83d2195c5bd11b9a717f.
- Complete native suite: **276 passed, zero skips**.
- Genuine matrix: five positive variants (including independently computed
  valid outputs), one contract-identity check and 85 wrong-output rejections.

An actual wrong-method control reread original FD values and treated the missing
first measurement as zero. The resulting T denominator changed one subject's
QC membership (sub-10228), increasing the restricted cohort from 125 to 126.
The verifier rejected its numerical FD values, with unchanged valid FC and
metadata; neither prose nor an expected effect direction caused rejection.

The first source-free test run retained one mistaken fixture expectation that
the constant-input numerical-zero bound underflowed to zero. The frozen formula
correctly yields a positive subnormal; only that fixture expectation changed.
No source, estimator or acceptance tolerance was tuned after signal outcomes.

## Acceptance boundary

Clean-commit Harbor execution and final-image regression/byte-identity checks
are separate post-commit gates. Their authoritative receipts are recorded under
`tracking/pr_repairs_2026-10-01/pr-173/` in the local repair-tracking workspace;
the static native results above must not be mistaken for those later receipts.

This is an easy observational CNP method/sensitivity control, not an original
paper finding, a causal test or evidence of Sol difficulty. Geometry lineage is
documented, but the original installed FS6 mesh was not independently recovered.
Atlas/mesh redistribution licensing remains unresolved. No Sol run, push, merge
or public data/image release is authorized by this repair.
