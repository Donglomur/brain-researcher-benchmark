# Complete native-window preparation

This successor fixes a sample-coverage defect in the preserved NEURAL-098 FIF
preparation. At 100 Hz, an epoch starting at −0.49 s omits the required −0.50 s
baseline sample. The predecessor accepts that epoch because its completeness
tolerance allows one whole missing sample. For an invented linear ramp, the
pre-window feature becomes 0.195 instead of 0.200. Every baseline-subtracted
window is affected. The successor refuses incomplete coverage before reading
signal arrays.

The complete native sample indices for each half-open interval are computed
from the epoch's actual first time and sampling frequency. The grid may have an
arbitrary phase; zero is not required to be a sample. A required index outside
the recording fails preparation. The whole time grid must agree with that
clock within 1e-7 samples, preventing individually small time-step errors from
accumulating into shifted windows. This tolerance handles floating-point time
representation, not missing samples. No filtering, resampling, interpolation
or baseline substitution is introduced.

`prepare.py` retains the predecessor's exact six channels, baseline,
duration-dependent window availability, event/offset/button controls, metadata
rules and full support requirement. Batches remain at most eight epochs.
Structural NaNs remain absent short/medium-duration windows. Output is still
`features.npy`, `packet.json` and `PREPARATION.json`; the last now records
`window_projection.revision = native-coverage-v2`. The fixed 33-person,
66-fold, 330-fit analysis and 42-cell/24-contrast reconstruction endpoint are
unchanged. Preparation does not fit that analysis.

The source dependencies below are reused and checked by SHA256. The successor
does not modify or replace the preserved source package or central registration.
Its CLI takes an explicit operator-supplied cohort and hash because the original
protected cohort body is intentionally absent from this repository. That input
must be the already-authorized exact cohort, not a newly selected group; a hash
and 33 unique identifiers alone do not authenticate biological eligibility.
No protected cohort, phase list, recording or target body was accessed here.

```sh
python -I -B prepare.py \
  --source-plan /operator/plan.json --source-plan-sha256 PLAN_SHA256 \
  --cohort /operator/COHORT.json --cohort-sha256 COHORT_SHA256 \
  --output /fresh/packet
```

This command is for a separately authorized native preparation with pinned
dependencies and the original complete panel. It was not run on authentic data.
Generated controls are run with `python -I -B test_generated.py` through the
coordinator's shared test pool. They exercise the actual predecessor and
successor extraction functions on invented arrays, including the missing-sample
counterexample, complete-grid parity, physical boundary impulses, fractional
rates/phases, cumulative clock drift, mixed-duration structural NaNs, reversed
epoch selection across the eight-epoch batch boundary and rejected bad inputs.

Authentic source access, event-to-epoch mapping, complete support, independently
qualified reference, native execution and genuine agent comparisons remain
unresolved. These software controls establish no sustained-content result,
native understanding, viewer interpretation or model performance.

## Preserved source and terms

All paths below are relative to
`benchmarks/shared/four-programmes/_four_programmes_source_v1/originals/authoring/delivery-20261105/neural098/`.

| Source role | Path | SHA256 |
| --- | --- | --- |
| Preparation predecessor | `private/prepare.py` | `ca9c3439316576986b3e78e74a3805cf032ac53014d65e321e88295784e07cc3` |
| Fixed scientific protocol | `public/protocol.py` | `f08e50cf68f421ef43aa83391e30e5c51101673cb7f248289af30062ca1961fe` |
| Captured input/output helper | `public/io_utils.py` | `7bbb7a95ded626b4145860b2acf6252448f86dac95d9d417e1ea436d7bdf2df9` |
| Feature validity helper (no fitting invoked) | `private/reference_program.py` | `29e7c3d8530e9705cc35e96846b301a0cb660311aa4b339ad85e62e2a1ca386d` |

Modified 2026-11-17 from the benchmark preparation source, preserving its header.
The shared source's [scoped distribution notice](../../../../shared/four-programmes/_four_programmes_source_v1/NOTICE.md),
[GPLv3 license](../../../../shared/four-programmes/_four_programmes_source_v1/LICENSE),
[third-party notices](../../../../shared/four-programmes/_four_programmes_source_v1/THIRD_PARTY_NOTICES.md)
and original permissive component grants remain applicable; this successor is
distributed under those combined GPLv3 terms. No external author-source or
scientific parity claim is made.
