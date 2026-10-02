# EMOMATCH-001 — fixed-cohort duration-model sensitivity

## Scientific target

On the same twenty AOMIC PIOP2 participants, compare signed emotion-minus-control
coefficients under common-median-duration and individual-RT-duration models.
Keep participants, frames, spatial supports, HRF, drift, nuisance regressors and
contrast definition fixed. Retain all 100 cortical parcels and eleven spheres,
each model's signed results, and equal-person paired changes.

This is an explicit paper-derived **method/sensitivity control**, not a
reproduction of Hariri's sample or an AOMIC Figure 7 finding. The source paper's
emotion-matching task description provides the acquisition/task substrate;
Grinband et al. motivate examining event-duration models. Neither source makes
a fixed-twenty regional attenuation pattern a compulsory correct answer.

The task's response-terminated displays make RT partly an exposure measure.
Changing duration changes regressor shape/scale and its fitted coefficient; it
does not isolate a causal RT confound. Median imputation for omissions differs
from the observed timeout duration. Both facts belong in the interpretation,
not in a hidden prose-keyword grader.

## Public contract and provenance

All source, spatial, event, normalization, design, numerical-rank, aggregation
and uncertainty rules are public. The target is canonical source-based
computation, not a secret estimator or a guessed regional ordering. Equivalent
implementations and coherent row/axis reorderings are supported within the
declared computational/serialization bounds.

The version-pinned offline inventory has 131 original files, 2,197,402,958 bytes,
including twenty BOLD runs plus their complete source events/confounds and
metadata. The released matching-template Schaefer atlas replaces the old
unstated cross-template substitution. All 226 participant rows are retained as
a cohort ledger; exactly sub-0002–sub-0009 and sub-0011–sub-0022 are analyzed.
There is no fourteen-person availability fallback.

See environment/SOURCE_NOTICE.md and the public source manifest for exact
versions, hashes, URLs and retained license/exporter limitations. Original
participants.json contains a duplicated identical documentary NEO_A definition;
it is not an analysis variable and is preserved, not silently rewritten.

## Verification design

The grader authenticates the source bundle using grader-owned pins, reconstructs
the original measurements, and binds all signed fits to the public contract.
It does not import the participant-visible staging helper or oracle. The oracle
uses nibabel image decoding and NumPy SVD; the grader uses sequential NIfTI
volume decoding and SciPy SVD. Shared nibabel header interpretation, NumPy,
LAPACK and pinned Nilearn HRF/cosine primitives remain shared dependencies,
not an assertion of fully independent software.

Accepted per-person aggregate receipts are the authority for their group and
paired arithmetic. Accepted primitive contrasts drive sphere/network groups;
source-bound per-person RT measurements drive RT groups. There is no second
historical group-t bank, desired sign, significance threshold, correlation
floor, region-by-value model assignment or mandatory narrative.

All eight evidence artifacts are checked. Binary reward requires complete
source identity, membership, numeric and arithmetic consistency; a partial
run or diagnostic failure report is not a successful submission. This is a
computational-control task. The metadata label easy is not a measured Sol
success rate; agent difficulty remains uncalibrated.

## Evidence status

At the pre-commit checkpoint, all originals are authenticated, the public method
and schema were frozen before signal analysis, and both the fixed-subject pilot
and full twenty-person oracle pass. The native independent source-bound grade
and whole test suite pass: 502 tests, zero failures/skips, including 501
manufactured/source-free cases and one production grade. Four additional
authoring checks pass. The production Dockerfile builds its pinned sources
successfully; no numerical answer bank is shipped or read.

Earlier documentary-JSON and local build-reference failures remain preserved.
Clean-commit Harbor and actual final-image evidence are recorded separately
after this checkpoint, before Sheet completion. No Sol success rate, paper-finding
replication, push, or public image/data release is claimed.

## Sources

- Snoek et al. (2021), AOMIC:
  https://www.nature.com/articles/s41597-021-00870-6
- AOMIC PIOP2 release 2.0.0:
  https://doi.org/10.18112/openneuro.ds002790.v2.0.0
- Grinband et al. (2008), event-duration model motivation:
  https://pmc.ncbi.nlm.nih.gov/articles/PMC2654219/
