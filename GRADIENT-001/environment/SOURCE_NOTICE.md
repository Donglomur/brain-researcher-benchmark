# Source scope and attribution

This source bundle contains unmodified released derivatives and documentary
notices, not fitted gradients or reference answers. The fixed loader membership
is sub-pixar001–016 and sub-pixar123–126: 20 preprocessed BOLD files,
20 complete original confound tables, the original 155-row participants table,
and Schaefer 400/7-network/2-mm atlas image plus its original LUT. Three further
files retain the processing README, Nilearn 0.12.1 dataset description and CBIG
license. The manifest's ordered_participant_ids records the authenticated
Nilearn 0.12.1 selection replay under NumPy 2.1.3 and pandas 2.2.3, including
the loader's group sorting. Manifest file ordering is not analysis ordering.

## Released development-fMRI sources

The official [Nilearn0.12.1 loader and index](https://github.com/nilearn/nilearn/tree/4c76adf58b6b48cdbd3e2cfa9e848f3a9324e570/nilearn/datasets)
identify the OSF-hosted derivatives. Each manifest OSF row binds the recorded
version and object to its original size and published SHA256/MD5. A previous
cache's presence is not a fresh authentication. Full original confounds are
retained; generated reduced-confound caches are not additional released sources.

The retained processing README documents fMRIPrep/Nipype processing,
MNI152NLin2009cAsym normalization,4-mm spatial downsampling and calibrated int8
storage. Original header fields and scaling must be reported literally. The
2-second analysis clock comes from the acquisition/documentation convention,
not from claiming that the stored fourth zoom is2 or that unknown header units
are explicitly seconds.

[Richardson et al. (2018)](https://doi.org/10.1038/s41467-018-03399-2)
describes the movie acquisition, not this particular gradient estimator. This
is a secondary analysis of released movie derivatives, not a replication of
adult HCP resting-state gradients, within-person development, or proof of a
particular network apex. The deterministic loader halves have different age
composition: the first ten contain four adults and six children; the second
ten contain ten children. They are not randomized samples or independent
replications.

## Schaefer atlas

The [official CBIG release](https://github.com/ThomasYeoLab/CBIG/tree/d1454a611f7de10a3b36665e6fbb3fb6c770d140/stable_projects/brain_parcellation/Schaefer2018_LocalGlobal/Parcellations/MNI)
provides the exact400-parcel/7-network/2-mm image and LUT selected by the pinned
loader. Their Git-blob SHA1 identities cover the Git `blob <size>\0` prefix plus
payload; their manifest SHA256 values were measured after matching those
published Git identities during a gated opaque-cache authentication. They are
not publisher-advertised plain SHA256 checksums. Preserve numeric parcel IDs,
literal LUT names and network labels; no substitution with the100-parcel atlas.

Nilearn names the atlas template MNI152NLin6Asym; the released BOLD derivatives
name MNI152NLin2009cAsym. Any retained identity-world nearest label transfer is
an explicitly approximate operational mapping, not proof of nonlinear template
registration. Coverage and all original source prerequisites must be inspected
before numerical endpoint execution, without outcome-based parcel selection.

## Rights and distribution boundary

The [OSF project metadata](https://api.osf.io/v2/nodes/5hju4/) assigns CC-BY4.0.
The pinned Nilearn data description separately states noncommercial research
use. The retained CBIG root license is MIT. These statements are preserved with
their scopes; this repair does not resolve precedence, grant commercial
clearance, or grant rights to Pixar movie material. Software and article
licenses are not substitutes for data/source rights. Do not publish source
bytes or source-bearing container images as part of this repair.

The three documentary files are provenance, not expected numerical answers.
BrainSpace implementation provenance belongs in the public method/code record,
not in a hidden source-result bank. Stable and changed apex identities are both
possible observations under a valid, prospectively frozen method.
