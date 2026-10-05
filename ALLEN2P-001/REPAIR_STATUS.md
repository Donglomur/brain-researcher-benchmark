# Repair evidence — original-source method validation

The prior first-pass patch and legacy answer arrays are not acceptance evidence
for this revision. Public estimator/schema, frozen offline source, numerical
lineage verification and independent checks replace rank/prose/numeric-band gates.
This is an easy single-field method control, not a hard-task or scientific
replication claim. No Sol/frontier run, push, comment, merge or publication.

## Source and scope

The original released Allen experiment 501271265 NWB (WellKnownFile 514516625,
container 511509529) is 565,631,796 bytes, SHA256
`7c9f26aea7f636126c7fe0c1fdf445229b1850601d03be7d30a13c3cda4578b1`.
One conditional HTTPS S3 transfer established that local digest; it was frozen
before processing and independently checked during image build and each reader.
The source's multipart ETag is not a whole-file MD5; its null S3 version is not
immutable. No published upstream SHA256 or separate API/mirror body equivalence
has been established. Runtime is offline; separate analysis/event assets were
not fetched or used as answer sources.

NWB-1.0.5 / Brain Observatory pipeline3.0 contains 215 unique source cell/ROI
pairs in unsorted ID order, 115,755 frames, 628 presentations (598 nonblank,
30 blank) and 40 conditions. Two conditions have 14 rather than 15 presentations.
The legacy dF/F `unit="frame"` metadata is inconsistent with the documented
DfOverF semantic path; no numeric rescaling was applied. Eye tracking failed.
This repair does not validate the acquisition or upstream image/fluorescence
processing. Allen research/noncommercial and attribution terms remain distinct
from SDK licensing; no public image/data redistribution clearance is claimed.

The paper's Figure3/response metrics concern detected events and responsive
neurons across fields, areas and layers. Here custom half-open dF/F windows and
all-cell threshold flags are explicitly a different, descriptive endpoint.
Repeated splitting is a specified sensitivity, not a paper-prescribed or
unbiased estimator of neuronal prevalence.

## Original-data measurements and independent check

Both public methods ran on every source cell and presentation:

- Same trials: **167/215 = 0.7767441860465116**.
- Mean of defined split ratios, then threshold once: **107/215 = 0.49767441860465117**.
- Separate mean of paired split-specific fractions: **0.5367441860465116**;
  population SD across 50 overlapping splits: **0.022890148463933543**.

Every metric is defined in this particular source run; that does not establish
stability. Split estimates have 1,159 negative OSI denominators and 1,173 negative
DSI denominators. Minimum nonzero absolute denominators are approximately
1.45e-6 and 1.83e-6. OSI ranges from -301.49 to 774.51; DSI from -680.72 to
614.60. There are 2,917 and 2,506 respective estimates outside [-1,1]. Signed
values were retained under the public contract; no clipping, exclusion, epsilon
or required same-versus-split direction was introduced after inspecting results.
These unstable ratios help explain why the split result is not a latent truth.

An independent source-only HDF5 reader re-paired original IDs and windows and
used scalar `math.fsum` plus dictionary-based condition/preference arithmetic.
All **135,020 trial means match exactly**, as do source identities and all
prescribed PCG64 masks. Maximum difference over 8,600 condition means is
2.22e-16; over 21,500 split estimate rows it is 7.67e-11; final per-cell means
differ by at most 7.64e-13. All threshold counts and summaries agree. Complete
participant-format positives exist for both methods. Shared h5py/NumPy/PCG64
and the same processed acquisition are disclosed; this is independent numerical
implementation, not independent biological data.

The reference bank was rebuilt from independently reloaded original windows:
816,272 bytes, SHA256
`3891ef19ea7bc280fd26b66380d1471d64850d38b1881acfb18e18ec5c5d5bf5`.
Final offline native tests: **235 passed, zero skips**, including 96 substantive
genuine-output cases (8 positive, 88 rejection cases). Both independently
computed methods pass. Signed near-zero denominator algebra is checked directly;
harmless row/column ordering and declared equivalent implementations are accepted.
Two non-applicable test parameter combinations were removed after an initial
237-pass run; the final 235-case matrix was rerun in full. No source, method,
numeric tolerance, or reference change was made for that test-count cleanup.

Pending after commit: exact clean-commit offline Harbor oracle, actual-image
tests, artifact/content-digest verification and Sheet update.
Authoritative execution logs and post-commit results live outside the worktree
in `tracking/pr_repairs_2026-10-01/pr-162/receipt.json` and adjacent command logs.
