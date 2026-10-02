# FCSTAB-001 source provenance and use boundary

This local research task uses released ABIDE I Preprocessed Connectomes Project
(PCP) CPAC `filt_noglobal/rois_cc200` ROI time series and the original
`Phenotypic_V1_0b_preprocessed1.csv`. These are already preprocessed derivatives,
not raw BOLD images or a new atlas extraction. No new denoising, registration,
diagnostic inference or causal interpretation is established by using them.

## Fixed membership and byte identity

The runtime contains the original 40 Pitt ROI `.1D` files named, in canonical
order, by `/app/subject_ids.txt`; the original full phenotype CSV; and one
commit-pinned Nilearn dataset notice. Those 42 source members total 16,147,721
bytes. Internal `source_manifest.json` and the public cohort-order file are
identity metadata, not additional scientific source members. No current fetcher
query, replacement subject or phenotype-driven cohort selection is permitted.

The full phenotype contains 1,112 records: 1,035 named derivative rows and 77
`no_filename` rows. Only 40 named rows join this fixed task cohort. Unselected
named rows are not missing data, and their values are not analyzed here.
All 40 original time series have 196 frames and 200 positional columns. The
authenticated selected phenotype rows have SITE_ID `PITT` and
EYE_STATUS_AT_SCAN token `2`. TR is not verified and is not needed for the
frame-indexed analysis; duration must not be inferred from row count.

The 41 original ROI/phenotype identities are an exact subset of the previously
authenticated manifest
`d4e930b84667e58831880100039cde688d56ccd0ff8c509f0f363fd1c4685aeb`.
This is reuse of source bytes only: no prior task's estimator, processed array,
connectivity, reference bank or results are scientific inputs. The frozen
manifest SHA-256 is
`c57fed19c165e8a606c2b6a9aef89099103a2642d6ab54b93bf525d71ea46171`.

The phenotype has the named S3 version recorded in the manifest. ROI objects
report literal version `null`, not an immutable release. Capture uses the exact
version query and `If-Match` ETag, then checks byte size and SHA-256. ETags are
conditional identity tokens, not presumed MD5 checksums; the recorded SHA-256
values are measured capture identities, not publisher-supplied checksum claims.
Unavailable or changed objects stop staging, without fallback/retry or cohort
changes. Local source reuse authenticates every input before copying.

The unmodified 1,195-byte Nilearn notice is pinned to commit
`8de9de0cabc4170d6c6c4be8c709818cffba7a62`:
[ABIDE_pcp.rst](https://raw.githubusercontent.com/nilearn/nilearn/8de9de0cabc4170d6c6c4be8c709818cffba7a62/nilearn/datasets/description/ABIDE_pcp.rst).
Its Git-blob identity is `e414ca3c0648f273b1c724ffcd3e4c5bf02a8db5`; SHA-256 is
`e3dcd9a90751427c232028320fa05b4982289e26d24de53a44825f15d421589c`.
This pins the notice, not an immutable S3 derivative release.

## Terms and attribution

The [official ABIDE I usage page](https://fcon_1000.projects.nitrc.org/indi/abide/abide_I.html)
states non-commercial research use, acknowledgement and registration conditions,
and links [CC BY-NC-SA 3.0](https://creativecommons.org/licenses/by-nc-sa/3.0/).
Public S3 access does not waive these conditions or establish commercial-use or
redistribution clearance. Users must review the source conditions, including
registration and acknowledgement of ABIDE I, its contributing investigators and
funding sources, Di Martino et al.(2014), and the PCP work described by Craddock
et al.(2013), as directed by upstream documentation.

This notice is not legal clearance for another use or a public dataset/container
release. The current preparation is an authorized local research workflow;
publication of source bytes or source-bearing images is not authorized here.

## Offline runtime

Build-time staging authenticates opaque originals. It makes no connectivity,
selection or outcome calculations. The final image contains the source and
public arithmetic/output contracts, not private tests, source loaders, solutions,
historical answer banks or participant outputs. Build receipts stay outside the
runtime inventory. Independent source reconstruction and output verification
are separate from source identity and do not establish scientific validity or
model-calibrated difficulty.
