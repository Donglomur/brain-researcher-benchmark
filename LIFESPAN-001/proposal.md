# LIFESPAN-001: fixed-cohort age-association method control

## Scientific target

Measure two signed cross-sectional age associations in the declared NKI59
surface cohort: global mean Fisher connectivity and pooled-pair zero-clipped
system segregation. Chan et al. 2014 (doi:10.1073/pnas.1415122111, Figure 2) is the
conceptual source for within/between-system comparisons; Nooner et al. 2012
(doi:10.3389/fnins.2012.00152) describes the NKI resource.

This does not reproduce Chan's cohort, functional-system definitions or original
finding. Anatomical Destrieux parcels and an age-blind KMeans partition define
a deliberately narrow method adaptation. Label it **easy/method control** until
separate model calibration provides evidence otherwise. No Sol run is claimed.

## What is fixed and what is measured

Fix all 59 historical cohort IDs, original source bytes, source vertex membership,
float64 parcel-mean accumulation with one float32 storage rounding, all-pair
Fisher connectivity, the explicit seven-cluster estimator, denominator conventions
and the two signed Pearson endpoints. Measure actual per-person and group values;
neither significance, a negative sign nor a global null is a required answer.

The precision rule is a prospective numerical amendment, not a claim of unchanged
legacy bits or clustering. Cohort selection is inherited, not retroactively made
confirmatory. No age-informed selection, covariate model, search grid, additional
preprocessing or exclusions are added during repair.

## Sources and verifier

The offline image retains 121 original files, not only a derived ROI bank. The
measured fresh-capture digests bind 4,997,109,352 bytes; 43 known local-cache counterparts
matched read-only. Fixed NITRC release IDs are not described as cryptographically
immutable versions, and measured SHA256/MD5 are not publisher-issued checksums.
Derivative/atlas redistribution terms remain unresolved; no data/image release
is authorized by this repair.

The verifier must authenticate originals with its own pins, reconstruct source
parcel/FC values, replay the public partition and recompute all scalar summaries
and age endpoints. It must accept coherent serialization/axis and cluster-label
permutations and the declared tolerances. Correlation-to-reference heuristics,
historical outcome bands, missing-person allowances and prose-keyword gates are
not acceptable. The old numerical archive is preserved externally and not used.

## Interpretation limits

The person is the independent unit for the stated Pearson approximation. The
partition is learned from the same cohort; its uncertainty is not propagated by
the plug-in Fisher interval. Fixed sampling, source preprocessing uncertainty,
sex/motion/nonlinear-age confounding and partition sensitivity remain limitations.
This is not within-person aging, causal/clinical evidence or population validation.

## Validation status

Local authoring validated source authentication, structure and the frozen public
contract. Both bounded original-source routes completed; their parcel time series,
connectivity primitives and group features agree exactly. Independent annotation
decoding, summary reductions and endpoint calculations provide additional checks;
shared numerical operations remain disclosed above.

All 435 native tests passed with no skips: 400 source-free checks, one production
grade, eight equivalent-output cases and 26 changed-evidence rejections. Two
separately recorded component controls—positive-only denominators and signed
rather than zero-clipped within/between summaries—changed every person's result
and failed numerical validation without changing source primitives or provenance.
These controls are not additional fitted scientific analyses or extra pytest cases.

Clean-commit Harbor execution and final-image delivery are recorded separately.
These checks validate the stated method implementation, not a reproduced paper
finding, causal or population claim, or model difficulty. No Sol calibration,
push, merge or public data/image publication is implied by a local commit.
