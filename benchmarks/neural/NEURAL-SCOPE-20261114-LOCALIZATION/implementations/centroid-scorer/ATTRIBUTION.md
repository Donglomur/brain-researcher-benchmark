# Scientific source and implementation provenance

The registered task is motivated by the paired-recording localization study at
[PLOS Computational Biology, DOI 10.1371/journal.pcbi.1014059](https://doi.org/10.1371/journal.pcbi.1014059)
and its [official Spike-Localization-Algorithms repository](https://github.com/haozhao1996/Spike-Localization-Algorithms/tree/a50fa6814937b281e8680d1602ea1a0856447281).
The associated released derivative is identified by
[Figshare DOI 10.6084/m9.figshare.31566010.v1](https://doi.org/10.6084/m9.figshare.31566010.v1).
These links are provenance pointers; publication includes none of their arrays,
workbooks, reference positions, model outputs or native method source.

The normalized validator/projector/scorer and geometry-centroid control are
benchmark construction code. They do not copy the native COM/MT/GC implementations.
The scorer retains the accepted benchmark's complete 11-cell/16-condition/5-seed
scope and balanced metric. Its source is reproduced unchanged; the control only
changes the dependency locator to the sibling source in this portable package.

The original repository's license and the separate paper/data permissions do not
automatically qualify redistribution of every associated artifact. This component
redistributes only its own source and invented test fixtures. Future original-data
preparation must resolve the applicable rights and scientific provenance separately.
