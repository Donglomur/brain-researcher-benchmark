# Source attribution and scope

The existing task is motivated by
[Modeling spatial contrast sensitivity in responses of primate retinal ganglion cells to natural movies](https://doi.org/10.1371/journal.pcbi.1014157)
and the original release [DOI10.12751/g-node.t43ph1](https://doi.gin.g-node.org/10.12751/g-node.t43ph1/).
The source inquiry inspected the official
[SpatiotemporalSCModel code at76b733421cc16131c2229e66a7714d8892de39d7](https://github.com/gollischlab/SpatiotemporalSCModel/tree/76b733421cc16131c2229e66a7714d8892de39d7).

Official `sc_model/dataio/dataio.py` loads both response arrays before checking
the `responses` flag (lines74–84,104–107); its training/test path construction
and reads are at277–294, and its WN-only STA path is at252–253. The accompanying
README names the original DOI and two preparations. These source observations
motivate the replacement's training-only path construction and explicit
calibration access. They do not authenticate native artifact membership or axes.

The adapter and invented fixtures are benchmark construction code. No official
source body, model, recording, stimulus movie, target or primary-source capture
is redistributed here. Original neural data, film stimuli, official code and
expanded processed releases have distinct provenance and rights requirements;
this component does not transfer their permissions or treat the four-preparation
processed mirror as the original two-preparation experiment. Future authentic
preparation requires its own rights and scientific-source qualification.
