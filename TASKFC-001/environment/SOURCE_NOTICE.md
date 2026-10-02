# Language-localizer source notice

Dataset creators: Christophe Pallier and Martin Perez Guevara; Neurospin,
ANR CONSTRUCT. The archive README describes ten French participants, a 3T Siemens
Tim Trio language-localizer task, spatial realignment/MNI normalization and
resampling from 1.5-mm to 4.5-mm voxels. These are source declarations, not an
independent reconstruction of the original acquisition/preprocessing.

The official Nilearn 0.13.1 loader at commit
`8de9de0cabc4170d6c6c4be8c709818cffba7a62` references
[OSF file 3dj2a](https://osf.io/3dj2a/). This task fixes
[archive version 1](https://osf.io/download/3dj2a/?revision=1):
749,503,182 bytes, SHA256
`e107ef9c99dcbebf9057a6506c1dc39242613ddf868839f1da4cb0220aa3204a`,
MD5 `5ec8731d4248711d78271613fabab925`.
Checksums are published by the current-file resource, whose observed current
version matches version1 metadata; the version resource itself publishes no
separate checksum. Every extracted member also has a measured SHA256/MD5 and
archive CRC in `source_manifest.json`.

All47 archive files are retained unchanged, plus the 936-byte pinned Nilearn
description. `access_data.py` is inert provenance; the stager, oracle and verifier
do not execute it. No generated signal replaces an original. The source directory
contains48 members plus its manifest. Build-time acquisition authenticates these
bytes; the agent runs offline.

## Preserve the distinct source notices

- The archive README and root `dataset_description.json` declare ODC-BY-SA;
  `CHANGES` links [the stated attribution-sharealike norms](https://www.opendatacommons.org/norms/odc-by-sa/).
- The derivative description literally spells its license `ODS-BY-SA`.
  It is preserved, not silently corrected.
- The pinned Nilearn description names ODC-BY-SA and links the documented
  [project k4jp8](https://osf.io/k4jp8/).
- Public metadata for k4jp8 advertises CC-BY 4.0. The actual archive resides in
  the separate public [mirror node 5dr8p](https://osf.io/5dr8p/), which has no
  node-level license. Captured API records do not establish parent/child lineage
  or byte identity between releases on those two nodes.

These records are attribution/provenance, not a new license or a resolution of
their precedence. Local capture/testing does not establish permission for a new
public data or container-image release. Preserve all original notices and resolve
redistribution terms before publishing either. This repair does not publish them.

The language-localizer demo is not Cole et al.'s original data. Cole 2019 provides
the method-sensitivity motivation only. Exact spatial registration, frame-origin
alignment, neuronal specificity and population generalization are not certified
by the container or its verifier.
