# Stable deviance in both solver consumers

This inactive candidate connects the existing reviewed `stable-deviance-v1`
primitive to NEURAL-092's actual validation and frozen QUERY consumers. The
registered runtime remains unchanged. This directory is a concrete source
replacement candidate, not an issued execution profile or a new benchmark.

The preserved solver could return zero for a small positive Poisson deviance,
lose a one-count residual above `2**53`, or overflow an intermediate ratio when
the final loss is finite. Those scalar repairs already existed separately.
Here, `gain/solver.py::deviance_term` delegates both consumers to the exact same
stable primitive. Arithmetic failure becomes the existing `FitFailure`, retaining
its cause; invalid-domain `ValueError` remains distinct. There is no clipping.
All other solver function bodies, including both live-host guards and complete-row
averages, are unchanged, as checked through their syntax trees.

`gain/poisson_deviance.py`, `authority.py`, `constants.py`, and `__init__.py` are
byte-identical to their source components. Their identities and the exact
solver/cost predecessors are recorded in `SOURCE_BINDINGS.json`.

## Workload accounting

The old cost model's twelve scalar operations per deviance row does not cover
the stable series. This candidate withdraws the aggregate scalar-operation
bound (`conservative_scalar_arithmetic_bound` is explicitly null) rather than
substituting an unexplained multiplier. It provides independently conservative
source-level counts for the same full workload:

- At most `units * (45 * n_validation + 6 * n_query)` deviance rows.
- At most 32 series iterations and 32 `fsum` calls per row.
- At most `2 + 3 + ... + 33 = 560` values passed to those sums per row.
- At most two logarithm calls per row, on a separate branch.
- A series list containing at most 33 values. Binary64 integer-ratio conversion
  has bounded operands; 1,138 bits conservatively covers the count/denominator
  product and subtraction for a signed-int64 count and finite binary64 mean.

These are separate per-kind maxima, not simultaneous branch counts. They do
not bound `fsum`'s internal arithmetic, integer-object allocation, CPU time,
physical memory, or retained exception frames. Existing logical array extents
are unchanged. A new source-bound native profile must account for these Python
objects and library work, and must not interpret the null bound as zero work.
The original full-panel source and physical-capacity holds remain.

## Generated controls

Ten focused tests passed once. They exercise the actual candidate validation
and QUERY consumers on invented counts and predictions, checking complete
strided unit axes, near-equality ordering, exact int64/float64 edge cases,
overflow exception compatibility, invalid domains, and new workload counts.
An independent 150-digit Decimal direct-definition oracle supplies expected
losses. The unchanged real custody module rejects both consumers before any
input access when no host has been issued.

Positive consumer tests substitute the host gate and prediction producer for
generated fixtures only. They do not issue authority, prove native isolation,
fit reference models, access authentic recordings, or establish predictive
performance. The earlier nine scalar tests were not needlessly rerun.

After placing this directory at the proposed task-local path, the maintained
test command is:

```sh
python -I -S -B benchmarks/neural/NEURAL-092/implementations/stable-deviance-integration-v1/test_solver_integration.py
```

The integrator must enroll that command in the existing component CI. It is
not already enrolled merely because this proposal contains a test file.

## Remaining integration

`INTEGRATION_PLAN.json` maps candidate files to the eventual source-bound
runtime replacements. Applying only a solver patch would leave the original
source descriptors inconsistent. Root selection must create and bind a whole
successor module graph, update all affected task/API/source descriptors and
resource admission together, and preserve the registered predecessor history.
This component performs none of those mutations.

The endpoint remains the complete 32-session/32-mouse programme, with the same
FIT/VALIDATION/QUERY blocks, five reference families, six areas, 15 area pairs,
freeze barrier, and later observed association reconstruction. Pupil support
remains unavailable for the full panel. Authentic packets, measured reference
competence, direct/viewer interpretation and scientific readiness are not
established by this repair.
