# Voltron: deposited data and the scoring contract

The complete metadata census supports **six declared subjects, twelve cells and 34 movies**. It does not support applying the older seven-animal, nominal-400/1000-Hz scorer directly to the deposit. These are data-preparation findings for the existing draft `NEURAL-DISC-20261114-VOLTRON-SPIKES`, not an additional benchmark or a completed signal evaluation.

The primary sources are the [versioned Janelia collection](https://doi.org/10.25378/janelia.c.5325254.v1), the [Cell Reports paper](https://doi.org/10.1016/j.celrep.2021.108954), and the [author's loader notebook](https://doi.org/10.25378/janelia.14141609.v1).

## What was inspected

All twelve archive directories were reconciled: 2,271 entries. All 263 selected JSON metadata members were recovered and reviewed: 34 movie records and 229 electrical-sweep records. The six-subject/twelve-cell mapping comes from this complete metadata census, beyond the earlier filename-only observation. It is a deposited-subject grouping; it does not resolve why the paper's acquisition methods describe seven mice.

The original TIFF movies, frame-time arrays and electrical waveforms have not yet been decoded for this task. Metadata consistency is not validation of physical synchronization, optical extraction or spike labels.

Movie metadata reports rates near 401.606 Hz and 996.016 Hz. The loader describes exposure-midpoint timestamps already expressed relative to electrophysiology. A converter must preserve the native recorded time vectors; it must not substitute nominal rates or add a movie-start offset twice. The metadata's 10 kHz electrical rate and the paper's 100 kHz acquisition description still need reconciliation.

## Full input scope

| Selected input scope | Members | Compressed bytes | Advertised decoded bytes |
|---|---:|---:|---:|
| Native frame-time arrays and electrical sweeps | 263 | 468,553,334 | 549,414,968 |
| Optical TIFF chunks | 1,067 | 170,200,432,800 | 319,441,732,938 |
| Both signal groups | 1,330 | 170,668,986,134 | 319,991,147,906 |

These are complete member-metadata totals, not downloaded signal bytes or observed decoder memory. The twelve full archive objects advertise 170,740,637,908 bytes. Small-member range requests also consume headers and transport metadata.

The 32 deposited mean-image PNGs are a possible aid to defining optical regions, but their contents, coordinates, processing stage and temporal support remain unverified. Two movies have no corresponding mean-image entry. Mean images cannot replace the full movie traces or establish which optical region belongs to the patched cell.

Five files from the [official processing repository](https://github.com/adamcohenlab/invivo-imaging/tree/ab8e57db8e5a878809d879cfcc317918a5fb3b38) explain a demonstration pipeline with spatial registration, denoising and later motion-regressor removal. Their blob bodies were verified; their commit/path association is supported by a retained derived tree projection, not an authenticated complete raw tree/commit response. They also show cropping and frame trimming. They do not establish that this pipeline produced the deposited files. No transformation from that demonstration is silently applied to the deposit.

## Explicit successor direction

The separate proposed profile is `voltron-six-subject-native-frame-events/v1`. It retains all twelve cells and 34 movies, uses native frame centers and six held-subject folds, and limits each prediction to one event per frame. Matching uses an inclusive five-millisecond tolerance and maximum-cardinality one-to-one assignment inside valid intervals. Event counts are summed across all movies within each cell before computing that cell’s F1; the primary remains six subject-specific equal-cell summaries, with undefined outcomes and extraction failures retained. Access roles, folds and cases are not additional benchmark IDs.

The private timing-resolution ceiling must match all available frame centers to reference events with the same one-to-one rule. Counting occupied frame bins is not equivalent. This ceiling is evaluated only after all candidate/comparator predictions are frozen.

The older [seven-group component](../implementations/voltron-complete-spike-events/README.md) remains a historical mathematical interface with invented controls. Its code is unchanged. The successor does not inherit authentic-data qualification from those tests.

Before authentic scoring, the project still needs complete signal custody and decoding, the deposited processing/clock relationship, independently justified patched-cell regions, optical-only extraction choices, electrical spike-label rules, valid-support masks, and matched training-only comparator outputs. None of the current metadata or source checks establishes neural understanding, improvement, SOTA, paper reproduction or submission readiness.

The [native-frame scoring core](../implementations/voltron-native-frame-events-v1/CONTRACT.md) now implements the six-subject event endpoint with exact timing, complete coverage and generated verification. Authentic inputs, electrical references, comparator producers and protected execution remain unqualified. This source addition does not increase the benchmark count.
