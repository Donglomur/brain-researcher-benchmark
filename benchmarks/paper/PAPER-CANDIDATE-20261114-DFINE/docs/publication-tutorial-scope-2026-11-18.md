# DFINE publication-day tutorial and the original motor-data benchmark

Source inspection: 18 November 2026. This note supplements the existing inference-source reconciliation. It changes no endpoint, scorer, registration, or readiness declaration.

The complete source of the [publication-day tutorial](https://github.com/ShanechiLab/torchDFINE/blob/c278035be4b750caab6e0d2cd57e2e9a09484a15/tutorial.ipynb) has now been recovered. The previous rendered-page inspection exposed only a loading placeholder. The new source is 763,762 bytes, Git blob `ce671545031627757d5291c5b3ead1dca371a9b9`, SHA-256 `f31e007e092026ae382bbffe5e6e3c8639065cfe1e0fe122bc858ea625f3424f`. Its decoded Git blob matches the retained complete initial-release tree. Code and Markdown were inspected without executing the notebook or interpreting its saved outputs.

The source binds the public tutorial to a synthetic Swiss-roll demonstration. It does not identify the historical motor-data analysis that generated Figure 7e and Extended Data 6e–f.

| Question | Authenticated tutorial source | Original motor-task requirement |
| --- | --- | --- |
| Inputs and target | `data/swiss_roll.pt`; inferred neural trajectories compared with noise-free synthetic observations | The paper's seven grid-reaching sessions and cursor position/velocity targets |
| Configuration | Explicit seed 0, two-dimensional latent factors and four 20-unit hidden layers | Original effective empirical configuration, selected neurons and trained readout |
| Partition | First 80% of synthetic trials for training; remaining 20% named test, also supplied as the trainer's validation loader | Original ordered fivefold sample membership and its selection boundaries |
| Missingness | Independent Bernoulli draws at 13 drop probabilities; plotted retained ratios are nominal probabilities | The paper's fixed-count dropping within each 100-step motor-data block, with original ratio grid and realized masks |
| Numerical comparison | Synthetic reconstruction NRMSE and a true-system UKF prediction comparator | Behavioral-correlation curves for filtering/smoothing and the LDM/SAE controls |

The tutorial's seed, ratio list and partition therefore cannot authenticate the corresponding historical motor choices. Its validation-loader use does not by itself prove how a historical empirical model was selected. Likewise, a public release dated on publication day is not proof that its revision generated a particular figure.

The [primary paper](https://pmc.ncbi.nlm.nih.gov/articles/PMC11735406/) identifies [Zenodo record 3854034](https://zenodo.org/records/3854034) for the grid-reaching data. The retained metadata pins that exact record DOI, `10.5281/zenodo.3854034`, under concept DOI `10.5281/zenodo.788569`, with CC-BY-4.0 licensing. Metadata revision 27 is distinct from a scientific dataset-version label. The record has a version relationship with index 1 but no separate `metadata.version` value. The earlier seven-file date-interval match remains an inferred roster; it is not an author-confirmed analysis manifest. No MAT arrays were retrieved.

The missing empirical artifact is an author-linked Figure 7e/Extended Data 6e–f analysis manifest or driver together with its original numerical output export. It must join the exact source/configuration/readout to the selected sessions and neurons, ordered folds, full ratio grid, 100-step block conventions, realized masks and per-session/fold behavioral correlations. An additional tutorial replay cannot supply that historical provenance. The original code-content failures remain failed; this acquisition resolves only the tutorial-source gap.

Reproduction, same-task improvement, native execution and scientific qualification remain unestablished.
