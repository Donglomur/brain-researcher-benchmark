# Attribution and licenses

The benchmark infrastructure is accompanied by the repository's unchanged MIT license and its **Copyright (c) 2026 Brain Researcher** notice in [LICENSE](LICENSE). No new license is assigned to external datasets, papers, author implementations or runtime products by this release. Original comments and notices in all 63 selected source files are preserved byte-for-byte.

The three files under `runtime/reference_sources/` are benchmark connection and dispatch code. They reference separately admitted MINT MATLAB source, `bci-decoders`, and `Glaser/Neural_Decoding`; those external author source bodies are not included. The package also references NumPy, TensorFlow, MATLAB Engine, Docker, Linux cgroups and an NLB evaluator without bundling or qualifying those products. Exact external license/version, redistribution and code-exposure questions remain the `code_exposure_and_rights` and `implementation_environment` gates. The repository license does not resolve them.

Paper-relative source anchors and historical ambiguities remain in `runtime/SCOPE.json` and `runtime/GAP_REGISTER.json`. No manuscript is bundled. The following dataset locators are copied from that source inventory; this audit did not visit, download, authenticate, or make a licensing determination about their payloads:

- [Area2_Bump](https://doi.org/10.48324/dandi.000127/0.220113.0359)
- [DMFC_RSG](https://doi.org/10.48324/dandi.000130/0.220113.0407)
- [MC_Cycle](https://doi.org/10.5281/zenodo.14769761)
- [MC_Maze](https://doi.org/10.48324/dandi.000128/0.220113.0400)
- [MC_Maze-L](https://doi.org/10.48324/dandi.000138/0.220113.0407)
- [MC_Maze-M](https://doi.org/10.48324/dandi.000139/0.220113.0408)
- [MC_Maze-S](https://doi.org/10.48324/dandi.000140/0.220113.0408)
- [MC_RTT](https://doi.org/10.48324/dandi.000129/0.241017.1444)
- [MC_PacMan](https://doi.org/10.5281/zenodo.14769889)

The source includes published nonhuman dataset/session names and metadata-level exposure declarations. It contains no private human identities, communications, raw observations, protected target arrays, model weights, credentials or signed acquisition URLs identified by this static audit. Historical source hashes and repository-relative provenance paths are references only; their private histories and evaluation artifacts are excluded.
