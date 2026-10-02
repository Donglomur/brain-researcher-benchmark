# FCVAR-001 source provenance and use boundaries

This task retains an explicit 30-person convenience subset of the public
Nilearn ADHD demo and the Harvard–Oxford cortical max-probability 25% 2-mm
atlas. It is not the current loader's first30 and is not Allen et al.'s study
sample. Retain literal seven-digit IDs and the original full metadata tables.
The archive/member URLs, sizes, hashes and documentary lineage are listed in
`source_manifest.json`. No numerical answer is included in that manifest.

The ADHD BOLD/confound archive hashes were measured from earlier fresh HTTPS
captures and reauthenticated for this task. The Harvard–Oxford archive was
captured from the exact URL in the pinned official Nilearn loader and checked
against the selected local cache members. These NITRC hashes are locally
measured identities, not publisher-provided checksums or guarantees that a
mutable download endpoint can never change. A future mismatch must stop the
build; it must not silently refresh the identity or replace the cohort.

The official Nilearn0.13.1 ADHD and Harvard–Oxford documentary notices are
included unchanged under `provenance/`, with their commit and Git blob
identities. Nilearn's atlas description attributes the atlas to structural
segmentations from the Harvard Center for Morphometric Analysis; those atlas
participants are distinct from this task's functional recordings.

The ADHD notice restricts commercial use. The
[FSL Standard Space Atlases license section](https://fsl.fmrib.ox.ac.uk/fsl/docs/license.html)
lists Harvard–Oxford separately under CC BY-SA4.0; this is distinct from the
main FSL software license. Preserve source attribution and applicable terms.
Public download access and successful validation are not legal clearance for
commercial use or redistribution. This local repair does not authorize
publishing the data bundle or container image.

Affine nearest-label resampling to a released BOLD grid does not establish a
new nonlinear anatomical registration. The task uses the public release as
provided and does not independently establish the original preprocessing
pipeline merely from its filename or the historical task's CPAC label.

Scientific interpretation is restricted to this finite-record method control.
See `instruction.md` and the public method contract for the paper connection,
support policy and limits of the surrogate comparison.
