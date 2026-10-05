# Local source-bound repair

The task is a whole-brain, one-subject method control, not the original Haxby
VT pattern-correlation finding, anatomical localization or population inference.
Float64 full-run cleaning including rest, training-only ANOVA-500, exact tie
handling and fixed SVC settings are public. Held-run normalization is offline.

Original subject-2 archive, labels and separate NITRC mask were content-pinned;
published archive MD5 and unchanged read-only cache comparisons agree. Original
source totals are 1,452 volumes, 864 non-rest volumes, 12 runs and 39,912 mask
voxels. The final image includes only the three selected original files and
manifest, not the archive's additional anatomy/ROI masks. Runtime is offline.
The publisher's documented archive/checksum URLs use HTTP; origin authentication
is therefore limited despite content pins. The dataset's CC-BY-SA-3.0 notice is
preserved, while separate mask licensing/generation provenance is unestablished.

The genuine full execution gives 567/864 correct = 0.65625, with all 12 fits
converged and no source-fit warnings. Complete predictions, 6,000 selected-feature
receipts, all training F scores and fitted classifier state are retained. The
reference was regenerated after original-source ANOVA/linear-state checks; old
rounded references were not treated as targets.

Independent original extraction, SciPy detrending/sample standardization,
centered ANOVA, Python tie ordering and 12 fresh classifier fits reproduce every
prediction and selected voxel/coordinate. Largest selected-F difference is
8.526512829121202e-14. NiBabel/NumPy/SciPy and sklearn/libsvm remain shared; this
is not an independent classifier implementation or biological replication.

A separately executed select-once control gives 654/864 correct and changes
152 predictions. It is rejected numerically despite internally coherent scores
and valid declared metadata; no particular accuracy difference is a grading rule.
Full native regression matrix: 242 passed, zero skipped. One warning belongs to
the synthetic NiftiMasker-equivalence fixture, not original-source fitting.

The first clean-commit Harbor trial computed the oracle correctly but its
verifier could not start: the script called `python` in a Python3-only image.
That reward-0 trial is retained. The entrypoint now uses `python3`, with an
additional packaging regression; no scientific result, bank or tolerance changed.

Final clean-commit Harbor, exact task digest and final-image regression evidence
are recorded externally in tracking/pr_repairs_2026-10-01/pr-159. Native checks
above are not a claim that those later gates have already run. No Sol/frontier
difficulty run, push, PR comment, merge or public data/image release is claimed.
