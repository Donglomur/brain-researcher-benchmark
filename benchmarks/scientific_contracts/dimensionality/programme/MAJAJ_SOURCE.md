# Majaj source correspondence and limits

This is a NumPy translation and labelled-array adapter for specific released
notebook cells in [badooki/dimensionality](https://github.com/badooki/dimensionality)
at `f18de35818502744329f7c92bb17a80af8f48549`. It is not a claim to reproduce the
final paper, its native JAX execution, its random realizations, or a biological
result. Upstream software is MIT, copyright (c) 2026 Chan Woo Chun; retain the
complete accompanying `UPSTREAM_LICENSE.txt` with substantial translated code.
That software license does not establish rights to neural recordings or figures.

The source envelopes were authenticated by exact Git blob identity. Neither
notebook was executed. Embedded outputs remain outside this source projection.

| Source at that revision | Git blob | Source correspondence |
| --- | --- | --- |
| `legacy/biology/BrainScore/Get_DiCarlo_Data_and_Save.ipynb` | `0c6da4dd4ad9c5cee093c8a7a2bef7ba7d6b3481` | C0 loads `MajajHong2015.public`; C2 transposes the labelled assembly, selects animal/ROI, retains first duplicates, intersects sorted support over repetitions 0–27, and squeezes the singleton time bin. |
| `legacy/biology/BrainScore/on_Majaj.ipynb` | `fa1b912c17ec4d45da209b89379b82e3300941f1` | C1 `gett_all` and `getest_all`; C4/C6 Q/P sweeps; C5/C7 plot summaries. |

`prepare_assembly` requires explicit presentation and neuroid coordinate vectors,
unique stable neuron identities, object identity agreement across retained
repetitions, and an explicit dimension permutation. It preserves neuron order.
It never infers an acquisition window, merges time bins, averages repetitions,
normalizes neurons or trials, or downloads the BrainScore assembly. The upstream
assembly/package revision, units and time-bin description remain operator-bound
operands whose genuine provenance still needs external qualification. Extra
repetition labels are reported as excluded by the source's explicit 0–27 loop.
Stimuli absent from any repetition are reported and dropped from the sorted common
intersection; duplicates retain their first original position and a discard map.
Invalid stimulus domains, empty repetitions/intersections, missing groups,
nonfinite values and mismatched identities refuse explicitly.

The complete released cohort is Tito/Chabo crossed with V4/IT, in source loop
order. It does not map Majaj V4 onto the paper's separate Papale V4 dataset.
Q sweeps use ten integer-cast logarithmic grid ordinals from 10 to F at P=M;
P sweeps use ten ordinals from 200 to M at Q=F. Repeated integer sizes remain
distinct ordinals. Out-of-support grid entries retain explicit failed draw slots,
never clipping the size or deleting the case. There are 1,000 paired draws per
ordinal: 80,000 planned draws, 320,000 four-estimator records across all eight
animal/ROI/axis panels. These are conditions and repeated draws, not benchmarks.

The released process mixes unseeded NumPy repetition choices with advancing JAX
keys. Its realized state cannot be recovered from the code. The new protocol is
explicitly prospective: NumPy PCG64 with SeedSequence `[operator_seed, group_index,
axis_index, grid_ordinal, draw_ordinal]`, with axis index P=0/Q=1. A pair always
uses two distinct repetitions and the same without-replacement stimulus and
neuroid selections. NumPy version and this protocol must accompany future runs.

`seven_terms` uses all seven exact patterns `ijji`, `iiii`, `ijjj`, `ijjl`,
`iijj`, `iijl`, `ijlm`. Each takes the all-column sum and subtracts its equal-column
sum. Both matrices are divided by sqrt(P)*sqrt(Q). The `ijji` contraction is a
nonsymmetric trace-square, not a Frobenius norm. The four moment pairs preserve
the source finite-P/Q coefficients, including the source column-only expression.
Existing corrected S3 moment estimators are not substituted. NumPy float64 and
contraction optimization can differ in roundoff from literal JAX dtype/runtime;
native parity and numerical qualification remain unperformed.

The source plots use nanmean and nanmedian of per-draw A/B, ordinary std with
ddof=0, and ordinary mean squared error against the **last grid point's** both
estimator mean(A)/mean(B). Integer casting means that reference need not be full
support. The final grid's MSE is omitted from the plotted curve exactly as in the
source, while all its records remain. Mean(A/B) and mean(A)/mean(B) are distinct.
The new adapter separately calls unchanged S3 `scoring.curves`: every planned
draw remains in its denominator; any invalid draw makes those protected summaries
unavailable. Literal NaN-skipping plots cannot turn those failures into success.
Numeric/status consistency is checked before aggregation. Negative finite ratios
remain literal diagnostics with an explicit positivity flag, not biological truth.

The final ICLR 2026 paper's C.1 says 500 draws, while these pinned released cells
say 1,000. Root's primary-source reading also places Majaj IT and Papale V4 in
different Figure 2 branches. Final Figure 2/S1 mapping, upstream measurement
window/release identity, 500-versus-1,000 version correspondence, and native parity
remain unresolved. This branch cannot satisfy those final-paper obligations by
renaming its outputs. Auxiliary averaged-repetition and class-conditioned cells
are different analyses and are not silently substituted here.
