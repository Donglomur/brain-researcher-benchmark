# Stable Poisson deviance component

This version repairs the scalar loss used by NEURAL-092's protected count
prediction endpoint. The mathematical endpoint stays
`2 * (y * log(y / mu) - y + mu)`, with `2 * mu` for a zero count.
The original registered runtime is preserved byte for byte. This is tested
replacement source awaiting integration into a newly bound runtime version.

The predecessor's `programme/gain/solver.py::deviance_term` loses positive
losses by cancellation. For `y = 1` and `mu = nextafter(1, +inf)`, it returns
zero although the loss is about `4.93e-32`. For `y = 2**63 - 1` and
`mu = float(2**63)`, rounding the integer loses the one-count residual. For
`y = 1, mu = 1e-320`, its intermediate ratio overflows although the loss is
finite. The generated controls reproduce these behaviors by importing the
actual preserved predecessor; no copied imitation supplies the regressions.

`poisson_deviance.py::deviance_term(y, mu, calls=None)` accepts the existing
nonnegative signed-int64 count domain and positive finite float64 means.
Near equality it preserves the exact integer/float difference using the
float's integer ratio. With `v = (y - mu) / (y + mu)`, it evaluates

```text
loss / 2 = (y - mu) * v + 2*y*(v**3/3 + v**5/5 + ...).
```

This branch has `abs(v) < 0.1` and at most 32 iterations. Away from equality,
it avoids `y / mu`; when `mu / y` is subnormal, it uses separate logarithms
to avoid the ratio's lost relative precision. It rejects a loss outside the
finite float64 range and never clips negative results, predictions or counts.

Nine generated software tests passed. They use a separate direct-definition
oracle with 150-digit Decimal arithmetic and exact conversion of each input
float. Controls cover both sides of equality, the integer precision boundary,
the series branch boundary, the minimum positive float, subnormal ratios,
zero counts, true result overflow, malformed inputs, accounting, and a
candidate/reference gain that the predecessor incorrectly reports as tied.
One initial repair failed two subnormal oracle cases; that failure was retained
externally and fixed before the passing run. These tests measure numerical
correctness, not predictive performance or runtime capacity.

Integration must replace the scalar primitive for **both**
`prediction_deviance` and `frozen_deviance` in a new source-bound solver version.
Retain their existing live-host checks, full-row averages, fixed-reference
failure handling and complete-panel freeze barrier. Preserve `FitFailure`
translation where the solver requires that error type. Update every affected
source descriptor and dependency declaration together; this directory changes
none of them. The existing `cost.session_plan` allowance of 12 scalar
operations per deviance row does not bound the new series and must be revised
before any native profile selection. The component records each attempted row,
each series iteration, and each logarithm through the existing `Calls.enter`
interface. Its bounded temporary list has at most 33 floats; integer-ratio
temporaries and interpreter overhead also require accounting.

The source basis is the preserved task contract and registered runtime at
repository base `c620e64d39fda59e049c40b3bc7d6d328d1534f9`:

- `understanding.v1.json`: SHA256 `e6f7840702dcc6583d8e0a5875875e511379eb8e82446564a9893d271c0d6e67`.
- `programme/gain/solver.py`: SHA256 `4262d49adcf2bf5a1d498f93b2579c6352b6819649ecc9e63eee4b1b5b8c1c45`.
- `programme/gain/features.py`: SHA256 `f0b32661465fbea77ccf23f9bfb1ba975f4bb3446d46c2e8c6529e383f84c246`.
- `programme/gain/scoring.py`: SHA256 `2697ce5393abef1711b1f4abddeb6e25b130132e8087b479dcffe739df8df1ce`.

The source cohort remains the 32-session/32-mouse Allen Visual Coding
Neuropixels panel, with blocks 2/5/7, 1.9-second exposure, six fixed areas and
15 area pairs. The later observed-state reconstruction, missing-pupil
dispositions and all access-mode distinctions are unchanged. This component
does not prepare authentic data, issue host authority, fit models, deliver
direct/viewer interpretation or establish causal state effects. Authentic
packet coverage, a newly bound runtime and independent complete reference
execution remain necessary. No dataset download, model call or authentic
target access was used to develop it.
