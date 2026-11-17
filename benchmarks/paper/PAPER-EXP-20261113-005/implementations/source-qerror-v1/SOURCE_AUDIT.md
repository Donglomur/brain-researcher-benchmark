# Source fidelity audit

Scope: PAPER-EXP-20261113-005's current original-capacity SOM reconstruction
contract. The source was inspected from the existing public frozen archive and
existing public article XML. No private historical answer, numerical neural data,
learned map, or participant packet was opened. No downloads were needed.

Exact byte identities and immutable URLs are in [SOURCE_PINS.json](SOURCE_PINS.json).
The frozen ZIP comment identifies revision
`9ae52eddc47fbb590ef4e1b1949507334707a0f1`. Its SHA256 is
`66efc8c239d85ab3cc3d6d3467e331c8fbb09fe7f68ea5b1deac557db1e7b251`.
This audit inspected the archive members directly; it did not assume a separately
extracted directory had matching bytes.

The anatomical constants and selector semantics are adapted from hejDMC/pfcmap;
its complete BSD-2-Clause notice is retained in [UPSTREAM_LICENSE](UPSTREAM_LICENSE).
The metric implementation uses Python's standard library and does not import or
execute the upstream training pipeline.

## Recovered implementation facts

- `python/settings.py:9` maps `wwspont` to `runC00dMP3_brain`.
  `config/somsettings/somsettings_carlenSpont.yml:1-18` selects active/prestim,
  dur3, all layers, Carlen, the six source task types, wide-waveform units,
  features `B_mean, M_mean, rate_mean`, equal weights and nominal `nnodes: 400`.
- `python/SOM/calc_SOM.py:43-63` builds the feature matrix, takes population
  means and standard deviations (NumPy default `ddof=0`), standardizes features,
  constructs the PCA-shaped grid, initializes with PCA and uses batch SOM on a
  hexagonal topology. `settings.py:35` fixes 200 iterations.
- `python/utils/som_helpers.py:81-89` computes grid dimensions from the two
  largest covariance eigenvalues, rounding **both dimensions upward**. Therefore
  the nominal 400 does not authenticate the actual node count. The original
  saved `kshape` and prototype matrix must be recovered. The evaluator uses that
  realized shape; it neither hardcodes a 20-by-20 grid nor silently allows 400
  replacement nodes.
- `python/utils/som_helpers.py:334-341` selects the nearest prototype by
  Euclidean distance with the first node winning a tie. `plot_SOM.py:205-226`
  and `plot_SOM_brain.py:80-102` compute unit-wise distances and plot medians
  with SciPy `scoreatpercentile`'s default fractional 25th/75th percentiles.
  The global mean at `som_helpers.py:879-883` is a different summary.
- `plot_SOM.py:71-78` and `plot_SOM_brain.py:62-69` reuse the saved source
  means/stds and feature weights; they do not re-standardize by region or map.
  `unitloader.py:495-497` contains the identical referencing transformation.
- `settings.py:119,188-205,227` supplies the ordered PFC labels, parent lookup
  and ordered parent labels. `unitloader.py:631-636` assigns parents by exact
  `Unit.area` membership. `Unit.area` comes from `unitloader.py:24-25` and
  `settings.decompose_area_layer`; CA1/CA2/CA3 retain their numeric suffix.

## Material unresolved selector discrepancy

The original `plot_SOM.py:211` selects a subregion with
`el.region.count(reg)`, whereas `plot_SOM_brain.py:85` selects the exact assigned
parent. Consequently a `VPL` unit also matches the `PL` subregion selector if
`PL` occurs in the source area roster. This is demonstrated with an invented
control. It is **not evidence** that actual source data contain VPL units or that
the published panel is wrong. The paper's Extended Data Figure 2 caption reports
19,186 units overall and 10,413 PFC units; those values and the exact plotting
selectors must be reconciled against authenticated source input. The evaluator
retains the author selector and refuses production scoring if the reconstructed
panel counts conflict with the caption. It never changes to an exact-match
selector and calls that a reproduction.

The separate existing conditional-reconstruction implementation documents 19,186
fitting units but 10,243 scored PFC units. Its ROI-specific scored population must
not stand in for the paper's 10,413-unit QError panel.

## What remains unestablished

The current source pins establish code identity and the equation/selector route.
They do not recover original unit features, original map weights and realized
dimensions, complete animal/probe joins, published numerical quantiles, or author
replay. No covariance, SOM, error vector or source score was computed on authentic
data. The small standard-library implementation can exercise the original metric
on a future authenticated packet, but scientific admission, original neighborhood
controls, full-panel comparison and uncertainty remain unresolved. The canonical
task and improvement contract are intentionally unchanged.
