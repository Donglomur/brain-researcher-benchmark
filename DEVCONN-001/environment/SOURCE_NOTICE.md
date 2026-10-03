# Source scope and attribution

The closed runtime bundle contains 155 unchanged released BOLD derivatives,
155 complete original confound tables, `participants.tsv`, the original Power
coordinate CSV, the released processing README, Nilearn's software license,
and its development-data and Power-atlas descriptions: 316 files and
940,543,951 bytes, plus the identical public source manifest. Historical answer
banks, reduced confound caches, and the PR198 template are not source inputs.

The [Nilearn 0.12.1 development index](https://github.com/nilearn/nilearn/blob/4c76adf58b6b48cdbd3e2cfa9e848f3a9324e570/nilearn/datasets/data/development_fmri.csv)
identifies the original OSF-backed release. The manifest preserves each object's
recorded version, URL, published SHA-256/MD5 and size. The processing README is
OSF object `5c8ffbf04712b400173b57d6`, version 2, project `5hju4`. These are
preprocessed public movie-viewing derivatives associated with ds000228, not
Fair's original resting-state data or raw scanner files.

The [Power coordinate CSV](https://github.com/nilearn/nilearn/blob/4c76adf58b6b48cdbd3e2cfa9e848f3a9324e570/nilearn/datasets/data/power_2011.csv)
is preserved byte-for-byte: Git blob `4c6469f02e81a05eb9e081466e63c92b3ad0f09f`,
SHA-256 `a052a4231d727348a44f8ba55e6663cb8beedc4f5b0415b3563beb82f16f9564`,
3,579 bytes. Literal ROI IDs and the original ROI,X,Y,Z columns are retained.
These are operational MNI coordinates; applying spheres to the released affine
does not independently verify the anatomical registration.

All BOLD images have a 50 x 59 x 50 x 168 shape and individual int8 scaling.
Raw spatial/time units are unspecified, with fourth zoom 1. The retained release
documentation supplies the operational 4-mm spacing and 2-second TR conventions.
Raw fields remain unchanged and no measured movie-onset claim is made. All 14
selected nuisance columns and the separate FD column are finite in this release;
no imputation was needed in the header/table inspection. Finite first-row FD
zero is an observation, not missingness.

The task is motivated by [Fair et al. (2009)](https://doi.org/10.1371/journal.pcbi.1000381),
but uses a different public cohort, viewing condition, ROI set, distance bins and
estimand. It is an explicitly labelled methods/sensitivity application, not a
replication, confirmation or refutation of that paper. Generic parsing, numerical
libraries and the public reporting kernel are shared; the independent extraction
and cleaning implementations are engineering cross-checks, not independent
scientific replications.

## Rights and distribution boundary

Captured OSF project metadata states CC-BY-4.0; the retained Nilearn development
description separately states non-commercial research use. The packaged Power
description says **License: unknown**. Nilearn's software license is not a
substitute for the source-data or coordinate license. These statements are
preserved without asserting precedence, commercial clearance, or unrestricted
redistribution rights. This local repair does not publish source bytes or a
source-bearing container image. Further distribution needs a separate rights
review. Nothing here grants rights to the movie.
