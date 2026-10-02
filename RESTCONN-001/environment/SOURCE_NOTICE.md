# Source scope and attribution

The closed runtime inventory contains ten unmodified source/document files plus
its byte-identical manifest: one ADHD-200 BOLD derivative, its complete confound
table, three original cohort/timing tables, the MSDL39 image and labels, and
three provenance notices. Only participant `0010064` enters the analysis. The
retained cohort tables do not make this a multi-person study.

## ADHD-200 derivative

The exact NITRC subject archive is
`https://www.nitrc.org/frs/download.php/7783/adhd40_0010064.tgz`; documentary tables
come from `https://www.nitrc.org/frs/download.php/7781/adhd40_metadata.tgz`.
The [Nilearn0.13.1 loader at its fixed commit](https://github.com/nilearn/nilearn/blob/8de9de0cabc4170d6c6c4be8c709818cffba7a62/nilearn/datasets/func.py)
identifies these releases and supplies an operational TR of2 seconds. Preserve
the actual NIfTI timing/scaling/units separately; neither filenames nor a loader
default establish a complete raw-acquisition clock or preprocessing history.

The manifest's NITRC archive/member digests are locally measured identities from
prior fresh HTTPS capture, not publisher-advertised checksums or immutable
release commitments. Selected local bytes were reauthenticated for this repair;
portable staging must reproduce the same archive/member bytes. The source is a
released processed derivative, not raw data. Its complete inherited preprocessing
history has not been independently established.

The retained [official dataset description](https://github.com/nilearn/nilearn/blob/8de9de0cabc4170d6c6c4be8c709818cffba7a62/nilearn/datasets/description/adhd.rst)
attributes the ADHD-200/INDI project coordinated by Michael P. Milham and describes
noncommercial research use. Its exact Git blob and measured SHA256 are pinned;
the description is documentary provenance, not an expected numerical answer.

## MSDL atlas

The [author's Inria ZIP](https://team.inria.fr/parietal/files/2015/01/MSDL_rois.zip)
contains the original image, labels and README. These digests are measured
author-origin identities, not publisher checksums. The recorded ETag is transport
metadata, not a content digest or immutable version guarantee.

The README cites Varoquaux et al., *Multi-subject dictionary learning to segment
an atlas of brain spontaneous activity*, IPMI2011. Its component names are useful
labels, not finalized anatomical localizations. Fit all39 continuous overlapping
maps jointly; do not threshold them into disjoint ROIs or interpret the selected
pair as a validated population cerebellar map. Operational affine-coordinate
resampling alone does not verify historical nonlinear template correspondence.

## Rights and interpretation limits

The pinned Nilearn descriptions for ADHD and MSDL both state noncommercial
research use. The author MSDL README does not establish a separate comprehensive
atlas-data license. Nilearn's software license does not override data terms.
This repair does not establish unrestricted commercial use or redistribution
rights and does not authorize publishing source bytes or source-bearing images.

This is a single-recording circular-rank method control. It does not reproduce
the xDF estimator or a named population finding, establish neural/causal coupling,
or validate circular-shift type-I-error control. Data identity, implementation
agreement and oracle success are separate from those scientific claims.
