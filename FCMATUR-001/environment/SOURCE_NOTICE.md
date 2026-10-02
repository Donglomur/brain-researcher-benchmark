# FCMATUR-001 source provenance and use boundary

This local research task uses released ABIDE I Preprocessed Connectomes Project
(PCP) CPAC `filt_noglobal/rois_cc200` ROI time series and the original
`Phenotypic_V1_0b_preprocessed1.csv`. It does not contain raw BOLD images or a new
atlas extraction. The supplied ROI derivatives are already preprocessed source
data; their use does not establish a new denoising, registration, or causal
interpretation claim.

## Membership and identity

The runtime source inventory contains 1,035 original ROI `.1D` files, the original
phenotype CSV, and one commit-pinned Nilearn 0.13.1 dataset notice: 1,037 members,
406,541,576 bytes. The internal `source_manifest.json` is additional identity
metadata, not a scientific source member. `/app/subject_ids.txt` is a public
cohort-order document, not another source member. The exact literal 1,035 FILE_ID
order is retained; no site/ID aliases, replacement subjects, or phenotype-table
substitutions are introduced by staging. The original phenotype has 1,112 rows,
including 77 `no_filename` rows; membership and analytical eligibility are
separate method-contract questions.

The first 1,036 manifest row records and their order are inherited unchanged
from the previously authenticated source manifest
`d4e930b84667e58831880100039cde688d56ccd0ff8c509f0f363fd1c4685aeb`.
Their measured SHA-256 identities were captured from exact fresh S3 responses
that matched the read-only original cache. This is source reuse only: no earlier
task's estimator, model, derived connectivity, reference bank, or outputs are
scientific inputs to this task.

The phenotype has the named S3 version recorded in the manifest. The derivative
objects report the literal S3 version `null`, which is not an immutable release
version. Each fresh request uses the recorded exact version query and `If-Match`
ETag and must match the frozen size and SHA-256. ETags are conditional identity
tokens, **not presumed MD5 checksums**; the original SHA-256 values are measured
capture hashes, not publisher-supplied digest assertions. A changed or unavailable
object causes staging to stop; no unpinned fallback, retry, or cohort change is
allowed.

The additional unmodified dataset-description notice is from Nilearn commit
`8de9de0cabc4170d6c6c4be8c709818cffba7a62`:
[ABIDE_pcp.rst](https://raw.githubusercontent.com/nilearn/nilearn/8de9de0cabc4170d6c6c4be8c709818cffba7a62/nilearn/datasets/description/ABIDE_pcp.rst).
Its 1,195 bytes match official Git-blob identity
`e414ca3c0648f273b1c724ffcd3e4c5bf02a8db5` and measured SHA-256
`e3dcd9a90751427c232028320fa05b4982289e26d24de53a44825f15d421589c`.
The code commit pins the notice, not the mutable S3 derivative release.

## Terms and attribution

The [official ABIDE I usage page](https://fcon_1000.projects.nitrc.org/indi/abide/abide_I.html)
states non-commercial research use, acknowledgement, and registration conditions,
and links [Creative Commons Attribution-NonCommercial-ShareAlike 3.0](https://creativecommons.org/licenses/by-nc-sa/3.0/).
The captured Nilearn notice also describes the non-commercial research boundary.
Publicly readable S3 URLs do not waive the upstream conditions or establish
commercial-use or redistribution clearance.

Users must review and comply with the source conditions, including required
registration and acknowledgement of ABIDE I, its contributing investigators and
funding sources, Di Martino et al. (2014), and the PCP work described by Craddock
et al. (2013), as directed by the upstream documentation. This notice is not a
legal determination that a new use, public dataset release, or public container
distribution is permitted. The present preparation is for an authorized local
research workflow; no publication of the source data or source-bearing image is
authorized by this task.

## Runtime boundary

Build-time staging authenticates opaque original bytes. Runtime computation is
offline and independently governed by the public method/output contracts. The
source-only image must not include solutions, tests, answer banks, participant
outputs, or derived scientific arrays. Download receipts and partial captures
remain outside the final runtime source inventory. Preserving source identity
does not itself validate an estimator or support a biological claim.
