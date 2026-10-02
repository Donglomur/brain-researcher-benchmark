# Source scope and attribution

This task retains unmodified released source bytes: 40 development-fMRI BOLD derivatives, their 40 complete original confound tables, the 155-row participants table, the two MSDL atlas members, and four provenance documents. The fixed cohort is sub-pixar001–031 and sub-pixar123–131. The closed runtime bundle has 87 files plus its byte-identical public source manifest. Source bytes, a source-bearing container image, or movie material must not be published as part of this repair.

## Development-fMRI release

The original derivative membership and URLs come from the [Nilearn 0.13.1 index at its pinned commit](https://github.com/nilearn/nilearn/blob/8de9de0cabc4170d6c6c4be8c709818cffba7a62/nilearn/datasets/data/development_fmri.csv). Its index bytes and the selected 40-person membership match the earlier 0.12.1 release. The manifest binds each OSF object to its recorded version, size, published SHA-256 and MD5; it does not treat the presence of a local cache as authentication. The complete confound tables are preserved, not Nilearn's reduced derived cache files.

The retained processing README describes the released fMRIPrep/Nipype derivative pipeline, MNI152NLin2009cAsym coordinates, spatial downsampling and calibrated int8 storage. The NIfTI header's own zooms, scaling and unspecified units are reported literally. The 2-second analysis clock comes from the acquisition/loader documentation, not from reinterpreting the stored fourth zoom of 1 as 2 seconds.

[Richardson et al. (2018), Development of the social brain from age three to twelve years](https://doi.org/10.1038/s41467-018-03399-2) describes the movie acquisition. Its functional-maturity analysis used different networks/cohorts and TRs 11:168. This benchmark retains all 168 released frames and does not reproduce that published endpoint, silently remove initial frames, infer a measured movie-onset alignment, or make a developmental group claim from the selected sample.

## MSDL atlas

The atlas is the original [Inria MSDL ZIP](https://team.inria.fr/parietal/files/2015/01/MSDL_rois.zip), linked by the [author's spatial-patterns page](https://team.inria.fr/parietal/research/spatial_patterns/spatial-patterns-in-resting-state/). Its SHA-256, MD5 and member hashes are measured from the fresh author-origin capture, not publisher-advertised cryptographic checksums. The observed ETag is transport metadata and is not claimed to be a digest or immutable version. Subsequent staging must reproduce the measured bytes exactly.

The author README cites Varoquaux et al., *Multi-subject dictionary learning to segment an atlas of brain spontaneous activity*, IPMI 2011. It explicitly cautions that the labels are useful names rather than finalized labels. Preserve literal map-axis/name identity; do not relabel three selected maps as independently validated anatomical parcels. The 39 continuous overlapping maps are jointly fitted after the declared affine-grid resampling, not thresholded into disjoint regions. Operational world-coordinate resampling does not establish an exact historical template bridge beyond the documented provenance.

## Rights statements and limits

The source OSF project metadata states CC-BY-4.0. Separately, the pinned Nilearn descriptions for both development-fMRI and MSDL state non-commercial research use. These statements apply to their respective sources and are retained without resolving precedence or asserting commercial clearance. The captured Inria page and atlas README do not supply a separate explicit comprehensive data license. Nilearn's software license is not a substitute atlas-data license. Nothing here grants rights to the Pixar movie or authorizes unrestricted redistribution of source data or source-bearing images.

The four exact provenance files in the manifest are the source processing README, MSDL author README, and both pinned Nilearn dataset descriptions. They are documentary evidence, not expected numerical answers or a hidden result gate.
