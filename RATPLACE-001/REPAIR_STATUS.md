# Replacement methods-case validation

The original rat/spaceflight formulation is retired because its released positions
were sampled at spike occurrence times rather than an independent behavior clock.
SOURCE_BLOCKER.md preserves that historical diagnosis. The user approved a
different public continuous-tracking source and an honestly labeled methods case.

The replacement uses one immutable mouse CA1 NWB from DANDI 001695. Its independent
25 Hz camera provenance is documented, but conflicting coordinate calibration and
upstream interpolation limit interpretation. After structure-only review and
before spike statistics, the method was fixed to a dimensionless 4-by-5 grid over
the supplied camera observation window, with no physical speed or maze-epoch claim.
Public environment/methods.md and the pinned contracts give the full estimator.

Two independently composed source reconstruction paths produced byte-identical
full primitive arrays and source ledgers. They share bounded source-I/O guards,
NumPy/HDF5 libraries, and disclosed information/reporting algebra; they do not
share the spike-to-tracking counting implementation. The verifier authenticates
original bytes and replays accepted source-close primitives and submitted receipts.
There is no hidden numerical answer bank or forced place-cell count/outcome.

Precommit local evidence: 157 distinct full-QA cases passed, including 142
manufactured cases, one production check, four coherent actual-output positives and
ten effective actual-output rejection probes. The production wrapper separately
passed its single scoring case. A genuinely cold source-only build fetched exactly
one pinned 61,347,328-byte NWB with no retries/redirects; a no-mount hash-only check
verified its closed runtime inventory. Harbor and final-image delivery receipts
are external tracking records and are not implied by these precommit checks.

The old 5,410-byte bank was preserved opaquely outside the active task before
removal (SHA256 8482e8df60a93a51401f4e89a280ea927393a6c3aaee7f3e297e4ef8c3f3ba8f).
Its numerical contents were not read or reused. Retired code remains recoverable
from Git history. These checks establish source/implementation consistency, not
a reproduction of the original paper estimator, biological place-cell identity,
a spaceflight result, population inference, or model-difficulty calibration.
