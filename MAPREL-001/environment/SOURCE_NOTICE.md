# MAPREL-001 source and interpretation notice

This local task is a conditional centroid-spin application to published group
maps. It is not a reproduction of a named finding from the spin-method paper,
not a400-person population analysis, and not a demonstrated hard model task.

Four hemisphere maps and the fsLR32k sphere archive are identified by the
neuromaps0.0.7 catalog at immutable commit
`ffcc2e0f657943ce00a1b6a968396f32250e495c`, public OSF node `4mw3a`.
Version1 metadata and release MD5 checks bind the OSF objects. The source
manifest separately records published hashes, locally measured hashes,
archive-to-member lineage and final installed-file membership.

- Margulies et al.2016, *Situating the default-mode network along a principal
  gradient of macroscale cortical organization*, PNAS113:12574–12579.
  The selected file is **fcgradient02**, the second diffusion-map embedding of
  group-averaged functional connectivity, not the principal gradient. The
  catalog reports N820; its released sign is retained.
- HCP-S1200 cortical thickness: the catalog cites Glasser et al.2016,
  *A multi-modal parcellation of human cerebral cortex*, Nature536:171–178.
  It reports ages22–35 and no sample count for this map. The S1200 release name
  does not establish N1200, and overlap/independence with the gradient cohort is
  not established by these map files.
- Schaefer2018 400-parcel/7-network atlas, fsLR32k CIFTI: immutable CBIG commit
  `634f676630929a71297852d01dd92a287103e861`, published Git blob
  `d803a04005997b473712be6f99c87c2f641f72e2`. Original cortical BrainModelAxis
  vertex IDs, not compressed row indices, establish map/sphere correspondence.

Method motivation is Alexander-Bloch et al.2018
(doi:10.1016/j.neuroimage.2018.05.070) and the neuromaps framework
(doi:10.1038/s41592-022-01625-w). The task retains normalized arithmetic parcel
centroids and three specified assignment variants; it does not claim exact
spatial-autocorrelation preservation or unconditional null calibration.
NiBabel format decoding and NumPy/SciPy numerical conventions are shared
dependencies of oracle and verifier. Their source joins and statistic replays
are independently implemented; this is not fully independent scientific software.

## Access and reuse boundary

Public availability is not blanket redistribution or commercial permission.
The captured neuromaps repository notice is CC-BY-NC-SA4.0 and requests citation
of original datasets/methods. The selected map metadata does not provide a
separate per-map license; the OSF node license field is null. HCP source-specific
terms and attribution remain relevant. CBIG's repository notice describes
software/documentation permissions, not independent proof of atlas/map rights.

Preserved repository notices and catalog metadata document these limits. This
repair authorizes local validation only; it does not authorize publishing the
input bundle or container. No original participant-level raw data are created,
inferred or claimed here.
