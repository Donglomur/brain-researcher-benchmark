# NKI59 surface method-control source notice

This task uses an explicitly fixed historical convenience subset of 59 people,
not a cohort recruited for this benchmark or the sample analyzed by Chan et al.
The identity list corresponds to the first 60 entries in the pinned Nilearn
loader minus A00051882; its historical selection came from the prior task.
That selection is not retrospectively justified as signal-based quality control.

## Original sources and attribution

The NKI Enhanced Rockland resource is described by Nooner et al. (2012):
https://doi.org/10.3389/fnins.2012.00152 . The released surface derivatives are
attributed to Franz Liem's nki_nilearn project and distributed through NITRC's
NKI Enhanced 1.0 release 3163 (package1362). The exact selected file identifiers,
original names and measured-byte identities are listed in source_manifest.json.

Nilearn0.13.1, commit8de9de0cabc4170d6c6c4be8c709818cffba7a62, documents
fsaverage5 surfaces and a645ms repetition time:
https://github.com/nilearn/nilearn/blob/8de9de0cabc4170d6c6c4be8c709818cffba7a62/nilearn/datasets/description/nki_enhanced_surface.rst .
The Destrieux annotations are the fsaverage5 assets from NITRC Destrieux
Surface1.0 release3353, attributed to Destrieux and FreeSurfer:
https://github.com/nilearn/nilearn/blob/8de9de0cabc4170d6c6c4be8c709818cffba7a62/nilearn/datasets/description/destrieux_surface.rst .

The selected GIFTI filenames state fwhm6. Public preprocessing code at
https://github.com/fliem/nki_nilearn/tree/dab177b6931f055fe364631b36c9669caa6cbed3
provides broad provenance but its surface script uses fwhm0 and postdates the
registry release. It does not establish an exact historical export command for
these bytes. No upstream preprocessing is regenerated or silently substituted.

## Identity and rights boundaries

NITRC provides fixed release/file identifiers, but no publisher cryptographic
checksums or immutable object versions were established in this review. Frozen
SHA256/MD5 values are measured from a fresh direct HTTPS capture. Read-only
comparison to known local cache counterparts is additional consistency evidence,
not a publisher signature or an original-acquisition validation.

Both pinned Nilearn descriptions mark the data license as unknown. Public URL
access and a software license do not clear redistribution of derivatives or
annotations. This repair does not authorize publication of the source data or
container images. Preserve attribution and resolve asset-specific permissions
before redistribution. No registration or restricted-access route was bypassed.

## Relationship to the scientific paper

Chan et al. (2014), https://doi.org/10.1073/pnas.1415122111 , motivates comparing
within- and between-system connectivity and system segregation (Figure2).
This task uses another cohort, a surface anatomical atlas, a cohort-derived
age-blind KMeans partition and a pooled pair-weighted ratio. It is a paper-derived
method control, not reproduction of that paper's sample, system definition or
reported finding. Two signed, unadjusted cross-sectional age associations are
descriptive; no direction, significance or null result is required.

The fixed-cohort selection, source preprocessing uncertainty, sex/motion/nonlinear
age confounding, and shared-sample partition uncertainty remain limitations.
An age-blind partition is not independent validation. The stated plug-in Fisher
interval does not propagate clustering uncertainty and is not a longitudinal,
causal, clinical, population-generalization or Sol-hardness result.

## Authenticated structural observations

All118 GIFTIs have895 original-order DataArrays of10,242 float32 values per
hemisphere. Each array has `TimeStep="1000.000000"` without a timing unit.
This token is not interpreted as seconds or replaced with documented TR0.645s.
No new time-dependent filtering/resampling is performed. Hemisphere/space lineage
comes from the authenticated release/filenames, not absent anatomical-structure or
coordinate-transform header fields. The annotations contain74 cortical parcels
per hemisphere; Medial_wall is table42 (888left/881right vertices), and Unknown
is table0 with no vertices. All59 exact phenotype IDs join uniquely to the102-row
source CSV. Source age tokens remain distinct from float32 computational age.
