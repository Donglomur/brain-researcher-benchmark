# FIND025 normalized covariance-variance arithmetic

This independently authored component computes eight released-code normalized
variance quantities from **operator-adjudicated covariance matrices** and a
hash-bound candidate basis artifact. It fills a matrix-arithmetic gap; it does
not activate the canonical task's two currently unsupported variance groups.

`variance_panel.evaluate_panel(operator, candidate_bytes, expected_sha256)`
derives descending covariance spectra, validates jointly orthonormal null and
potent bases, and evaluates the eight source-specific projection/denominator
combinations. The response-null denominator uses the movement rank; the
delay-potent denominator uses the preparatory rank. Ratios above one survive.
Undefined denominators retain their assigned outputs.

The strict operator object has `schema: find025_covariance_operands_v1`, the
source commit, ordered `unit_ids`, positive `d_prep`/`d_move`, a nonempty
`preparation_id`, and exactly four `covariances` and `support_ids` keyed by
`stationary`, `moving`, `delay`, and `response`. Each covariance is a finite,
exactly symmetric real matrix in that unit order. Candidate UTF-8 JSON has only
`schema: find025_subspace_bases_v1`, the same ordered `unit_ids`, `null_basis`
and `potent_basis`; basis rows are units and columns are dimensions.

The current software ceilings are 1,024 units, 4 MiB candidate bytes, and finite
entry magnitudes at most 1e100. Exceeding a bound rejects the complete input;
never shorten a scientific panel. Covariance definiteness and basis validity
use explicit binary64 roundoff checks, not paper-reproduction tolerances.
Input covariance symmetry is not repaired, and eigenvalues are not clipped.
The implementation requires NumPy; it installs nothing and opens no files.

All results are operator evidence. Returned numerators and denominators can
reveal properties of protected observations and must not be exposed as
participant feedback without a separately admitted policy. Hash equality and
support identifiers do not establish source authenticity, preparation, fitting
discipline, complete cohorts, execution isolation, or paper correspondence.

The pinned caller derives stationary/moving covariances from selected time/trial
rows but constructs delay/response matrices from all supplied input trials.
This component does not choose those rows, infer a motion mask, select ranks,
fit subspaces, or repair the original source. Its operator must adjudicate these
operands separately. Original source-versus-final-paper cohort, preprocessing,
case, fit/test and endpoint differences remain unresolved.

The source manifest records helper bodies and their retained Git identities.
The duplicate projection helper in the pinned tree has the same Git blob;
this closes that specific shadowing concern only. No upstream MATLAB body is
redistributed and its original license terms remain separate.

Run `test_variance_panel.py` through the shared construction test pool. Its
generated matrices test unequal ranks, rotated covariances/bases, zero variance,
invalid supports and tampering. They are not original observations or a
MATLAB parity/reference execution. This component emits no paper pass,
improvement claim, inference test, overall benchmark score or readiness change.
