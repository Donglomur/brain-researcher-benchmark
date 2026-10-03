# Source scope and attribution

The closed bundle contains 155 unmodified released BOLD derivatives, their 155
complete original confound tables, `participants.tsv`, one anatomical template,
17 pinned Nilearn code/notice documents, and the original processing README:
330 members, 942,572,457 bytes, plus the identical public source manifest.
The cohort is literally sub-pixar001 through sub-pixar155. Reduced confound
cache files and historical answer banks are not source inputs.

## Public movie data

The [Nilearn 0.12.1 index](https://github.com/nilearn/nilearn/blob/4c76adf58b6b48cdbd3e2cfa9e848f3a9324e570/nilearn/datasets/data/development_fmri.csv)
identifies the development-fMRI release. Each original is bound in the manifest
to its recorded OSF object/version, published SHA-256 and MD5, size and URL.
Presence in a local cache alone is not authentication. The processing README
is OSF object `5c8ffbf04712b400173b57d6`, version 2, project `5hju4`.

[Richardson et al. (2018)](https://doi.org/10.1038/s41467-018-03399-2)
studied social-network development during *Partly Cloudy*. This benchmark uses
that public-data substrate for a two-network GSR/motion sensitivity application.
It does not reproduce the paper's primary-motor/artifact-adjusted pipeline,
establish a causal developmental effect, or test within-person development.

All selected BOLD files have 168 frames and a 50 x 59 x 50 grid. Their spatial
and temporal unit fields are unspecified; the fourth header zoom is 1. The
pinned loader documentation supplies 4-mm spatial spacing and a 2-second TR.
We use its millimeter convention for world-coordinate sphere geometry while
preserving the raw header fields. No timing field is rewritten or interpreted
as measured movie-onset alignment. There is no temporal filter; detrending uses
original frame order. Int8 storage is decoded using each file's own scaling.
All 15 selected confound columns have finite entries on every released frame;
no values are imputed and the finite first-row FD zero remains an observation.

## Anatomical template and operators

The exact template is Nilearn's packaged
`mni_icbm152_t1_tal_nlin_sym_09a_converted.nii.gz` at the pinned commit above,
Git blob `2a712f1211d6c66e9690dcb06202bc4d8e00b182`, SHA-256
`421a10e872fd6cadae7f61d358dffbcc1795a497d61ee76c5dda2503e1a1e9e6`.
Its raw units are also unspecified; the loader documents 1-mm resolution.
The public method states the float32 normalization, resampling and mask rule.
The packaged asset name says `sym_09a`, whereas the retained description refers
to asymmetric 2009a; we preserve this documentary discrepancy. The BOLD README
names MNI152NLin2009cAsym. Operational affine resampling does not independently
verify anatomical registration or establish that these template editions are
identical.

The pinned source-code documents describe the chosen numerical conventions;
they are inert provenance, not code dynamically executed from the data bundle.
Oracle extraction uses Nilearn operators. The private verifier independently
decodes and reconstructs signals with NumPy/SciPy/sklearn. Generic table/header
parsing and the public downstream reporting kernel are shared explicitly;
agreement is therefore not a fully independent scientific replication.

## Rights statements and distribution boundary

Captured OSF project metadata states CC-BY-4.0; separately, the retained Nilearn
development-data description states non-commercial research use. The template
description states `License: unknown`. Nilearn's software license does not
substitute for a data/template license. These source-specific statements are
preserved without resolving precedence or asserting commercial clearance.
Nothing here grants rights to the movie or authorizes unrestricted source-data
redistribution. This repair validates locally and does not publish source bytes
or a source-bearing container image.
