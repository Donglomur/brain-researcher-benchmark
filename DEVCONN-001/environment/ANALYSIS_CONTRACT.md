# Analysis and interpretation contract

This is a fixed-data methods case motivated by Fair et al. (2009), not a literal
replication. Movie viewing, the derivative processing, 264 Power spheres and
distance-based summaries differ from the named resting-state analysis. The
participant is the independent observational unit. Neither cross-sectional age
association nor FD adjustment identifies within-person development or a causal
motion-free effect. Difficulty has not been calibrated on the repaired task.

The named paper anchor is [Figure 5](https://doi.org/10.1371/journal.pcbi.1000381.g005),
which compares child/adult connections by distance. The original method used four
distance groups and restricted which cross-midline connections were examined.
This task's all-pair tertiles, per-person Fisher-z means and child rank inference
are declared adaptations. The short-minus-long quantity called segregation here
is not the paper's community assignment or a claim to reproduce Figure 4.

## Source and primitive authority

The source manifest fixes all 316 members and their identities. Reconstruct all
155 subjects and all 168 frames from the original image and table bytes. The
headers have unknown spatial/time unit codes and a fourth zoom of 1; retain these
observations. The released processing description supplies the operational mm
and TR=2 s conventions used for geometry and filtering. This is not independently
verified registration or measured movie-onset timing.

Each header has its own scaling. Convert stored voxels to float64, multiply that
subject's effective slope and add its intercept. Require finite values only in
the contributing sphere union. The 5 mm sphere convention is Nilearn 0.12.1's
physical-radius neighbors plus its rounded nearest-voxel and integer-world seed
inclusions. Overlap is allowed. No empty sphere may be dropped or relocated.
The public method specifies the exact support digest serialization.

The cleaning design is, in order, six translations/rotations, six aCompCor
components, CSF, and white matter. FD is excluded from regression. Empty string
and `n/a` alone are declared missing and are zero-filled at their original frame
locations; record both nuisance and FD missingness separately. Other nonnumeric
or nonfinite values are invalid. Mean FD is the original finite sum divided by
the full frame count, with missing values contributing zero. An observed initial
zero is not missing. There is no arbitrary upper FD cutoff.

Demean and linearly detrend signals and confounds. Apply the order-5 Butterworth
0.009–0.08 Hz SOS forward/backward filter, fs=0.5 Hz, odd padding and default
SOS pad length to both, before regression. Population-standardize confounds,
using scale 1 below float64 epsilon. Economic pivoted QR retains columns with
abs(diag(R))>100*epsilon. Subtract `(Q @ Q.T) @ Y` from Y.

Activity is evaluated before final sample standardization: raw centered L2 must
be positive and residual/raw centered L2 must exceed 1e-12 using stable arithmetic.
Inactive columns are zero; their submitted tiny tolerated jitter does not create
edges. Active residuals are sample-z-scored (ddof=1, scale 1 below epsilon).

Submitted raw signals are receipts. Source-close submitted cleaned signals are
the sole downstream numerical authority. Canonical source activity, geometry,
age and FD remain the authority for support and fixed choices. Pointwise source
tolerances and continuous centered-relative fidelity are public in the method.
No hidden canonical rank, p-value, sign or effect-size gate is used.

## Connectivity and inference

Compute all 34,716 unordered ROI-pair Euclidean distances in the original CSV
order. Linear one-third/two-thirds quantiles define strict short/long bins;
boundary ties are excluded, not moved to force equal counts. Within each person,
use every edge whose two ROIs are canonically active. Report nominal and used
counts. Empty families are null. Varying edge support limits between-person
comparability; it is not equivalent to a fixed-edge paper replication.

Correlations use stable centered unit directions. Clip only numerical excursions
within 1e-12 of [-1,1]; larger failures are unavailable. Clip supported r to
[-0.999,0.999], take atanh, and compute the signed arithmetic mean with fsum.
These means are in Fisher-z units, not restricted to [-1,1]. Segregation is the
unrounded short-minus-long difference, with no tanh or absolute value.

The primary age population is exactly the 122 source-labelled children. Use
average tied ranks. Ordinary Spearman uses n-2 degrees of freedom. Adjusted ranks
use intercept plus ranked source FD, SVD with the published numerical cutoff,
actual design rank q, and n-q-1 degrees of freedom. Perfect supported |r|=1 has
p=0. Inactive rank residuals, missing complete support and other degeneracies
retain explicit nulls and reasons rather than small invented denominators.

For each child metric, source-exact constancy defines unavailable association;
otherwise apply centered-relative continuous fidelity, not a canonical tie or
rank-correlation gate. Apply the same rule to every bootstrap resample. Use
sorted child IDs and 1,000 successive `default_rng(11).integers(0,n,size=n)` draws.
The same matrix drives all three metrics and both associations. Retain duplicate
participants, rerank, and recompute nuisance rank and df. Keep all 1,000 slots;
any undefined slot makes its CI unavailable with its defined count. Only a fully
defined set gets linear 2.5/97.5 percentile limits. Draw IDs may be permuted
coherently; canonical child order and within-draw RNG slots may not be relabelled.

Group means need complete expected membership; constants are valid means.
Full and FD<0.2-restricted Welch comparisons use signed child-minus-adult
segregation, sample variances and actual Welch-Satterthwaite df. A source-exact
constant group contributes zero variance despite tolerated submitted jitter;
nonconstant groups require centered-relative fidelity. Means/differences remain
the accepted values. One zero variance with positive standard error is valid;
zero total standard error gives null t/p/df, retaining means and difference.
Explicit overflow/underflow is unavailable. No hidden target t or p is checked.

Bootstrap uncertainty is conditional on these fixed preprocessing and atlas
choices. FD restriction is descriptive selection, not matching or proof of
artifact removal. Do not conclude no effect merely from a large p-value.

## Grading

`output_schema.json` defines complete fields, identities, tolerances, safe output
limits and null semantics. Metadata must describe the actual originals and
computation, but narrative wording and software-version strings are not scoring
fingerprints. The shared public reporting kernel is byte-identical to the private
copy; extraction/cleaning routes are separately authored, with generic parsing
and numerical libraries shared explicitly. Authoring mutation tests are not
extra production scoring gates. The production reward is binary after one
source-bound artifact validation. No expected developmental or motion result is
stored as a grading answer.
