# Figure 5 native accuracy results

This component reads the three original Figure 5 result archives and produces
all 360 replicate curves, their 18,000 accuracy cells, and the original per-lag
mean and population standard deviation. It uses Python's standard library and
does not import Torch, execute simulations, load pickle, or select a candidate.

It advances the [current same-task objective](../../improvement.v1.json) by
providing a numerical preparation path for the source accuracy curves. No real
Figure 5 archives were acquired or processed in this construction. It is not a
qualified baseline or improvement evaluator, and no across-lag AUC is introduced.

## Source support and unresolved differences

The pinned [author module](https://github.com/MouseLand/critical_init/blob/2c15edf4e770165fc3962dcc3920c8bcaf555bed/fig5/fig5.py)
allocates each `acc` and `acc_shuff` array as replicate × delay × family. The
existing recovered [notebook caller](https://github.com/MouseLand/critical_init/blob/2c15edf4e770165fc3962dcc3920c8bcaf555bed/fig5/fig5.ipynb)
specifies 20 replicates, 50 delays, and the family order symmetric, nonsymmetric,
echo-state. Its 2-ms steps become seconds by dividing the stored `wm_isi` by 500.
The exact source bodies, local provenance and prior recovery are pinned in
[SOURCE_EVIDENCE.json](SOURCE_EVIDENCE.json). This is reuse of previously recovered
callers; it is not a new source discovery.

| Panel | Notebook archive | Renderer archive | Literal examples | Delay endpoints, seconds |
| --- | --- | --- | ---: | --- |
| F5d binary | `acc_multi.npz` | `acc_multi2.npz` | 2,000 | 0.120–2.942 |
| F5e novel input | `acc_zero.npz` | `acc_zero2.npz` | 2,000 | 0.120–2.942 |
| F5f aligned input | `acc_zero_aligned.npz` | `acc_zero_aligned2.npz` | 600 | 0.120–8.822 |

The producer and renderer files have unresolved provenance and cannot be renamed
into equivalence. The literal aligned caller has 300 examples per fold, whereas
the paper-described comparison has 1,000 per fold. Literal echo-state gain 1.35
differs from paper-described 1.4. Binary decoding uses normalized class centroids;
the paper describes nearest-neighbor decoding. Zero-shot decoding uses randomized
two-fold membership, normalized embedded neural-space targets and ridge 10.
The source time-independent path progressively shuffles `out[:j]` in place and
decodes `out[0]`, excluding the current lag. This reader summarizes those saved
results; it does not adjudicate these source/prose differences.

The file layout cannot establish which simulation or decoder produced a result.
Archive pins identify supplied bytes only. Published-curve provenance, historical
RNG states, paper-method equivalence and the original failures remain separate
requirements. The component retains the complete literal source layout while
leaving the complete paper comparison unresolved.

## Read already acquired archives

Keep archives, selection files and resulting numerical reports outside Git.
Supply a selection JSON containing independently obtained file byte counts and
SHA-256 digests. Replace the illustrative values below with exact acquired-file
pins; zero bytes and placeholder hashes are rejected.

```json
{
  "schema": "fig5-archive-selection/v1",
  "artifact_role": "notebook_producer",
  "files": [
    {"name": "acc_multi.npz", "bytes": 0, "sha256": "REVIEWED_SHA256"},
    {"name": "acc_zero.npz", "bytes": 0, "sha256": "REVIEWED_SHA256"},
    {"name": "acc_zero_aligned.npz", "bytes": 0, "sha256": "REVIEWED_SHA256"}
  ]
}
```

Use `notebook_renderer` with all three `*2.npz` names for the separately identified
rendered results. No automatic fallback between roles is permitted. The reader
requires all three arrays in every archive: float64 C-order `acc` and
`acc_shuff`, each `(20,50,3)`, and int32 `wm_isi`, `(50,)`. It enforces the exact
source lag grid and reports all panels, families and modes. NPY versions 1–3 and
little/big endian numeric storage are supported; object arrays are refused.

From this component directory:

```sh
python3 -I -B fig5_results.py \
  --input-root /absolute/external/figure5-results \
  --selection /absolute/external/selection.json \
  > /absolute/external/figure5-accuracy-report.json
```

Exit 0 means all 18,000 cells are finite and the selected native layout was read.
It does not mean scientific qualification. Exit 1 still emits the complete report
when source failure NaNs occur. Exit 2 refuses malformed, incomplete, unpinned,
out-of-range or unsupported inputs.

NaN cells become JSON null and retain panel, mode, family, replicate and delay
coordinates. Any missing replicate makes that lag's mean and SD null, matching
the source's NaN propagation; no `nanmean`, denominator reduction, replacement
score or candidate win occurs. SD uses divisor 20, matching `std(0)`'s default
`ddof=0`; it is not SEM or a confidence interval. Small floating-point rounding
differences from NumPy reductions are possible. Replicate indices preserve file
order but do not establish matched seeds across families or panels. The archives
cannot recover swallowed exception messages.

## Verification and integration scope

[test_fig5_results.py](test_fig5_results.py) uses generated, full-layout numeric
archives and analytic moment controls. It checks axes, population SD, exact lag
units, NaN preservation, artifact roles, pins, malformed numeric files and the
CLI failure report, and authenticates the retained source and caller reductions.
These checks are software evidence only. During the parallel build, run them
through the coordinator's shared test pool; no scientific kernel is exercised.

This additive directory leaves the existing closed packages and canonical
contracts unchanged. Integration may link this result preparation route and
clarify that the literal notebook grid was already recovered. It must retain the
aligned support conflict, producer/renderer gap, unresolved paper correspondence,
missing numeric baseline, and missing qualified author execution. No primary
scalar, effect threshold, paired inference, final split or new benchmark is
selected here.
