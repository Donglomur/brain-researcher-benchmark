# Attribution and scope

The Python implementation and synthetic controls are newly authored benchmark code, informed by the scientific method and source mapping for [the associated paper](https://doi.org/10.1038/s41593-026-02342-9) and the [official HybridModellingProject source at the pinned commit](https://github.com/simonedambrogio/HybridModellingProject/tree/3d343beb6dc7f1b7c6c7521ebec61f7dcef35b12).

The implementation documentation records inspection of the official R preprocessing, Julia data generators and model forward paths. “Source-derived” describes that relationship; no independently documented clean-room process is asserted. The public package contains the authored Python source and invented fixtures. It does not vendor the official Julia/R files, paper or supplementary text, authentic observations, author fits, protected predictions or local execution histories.

This repository's MIT license applies to the released benchmark code. It does not grant rights to the separate article, data, preprocessing assets or other third-party materials. The retained source mapping reports a prior MIT-license binding for the official repository; this package neither republishes that repository nor represents a blanket data-license audit. NumPy is installed separately and carries its own distribution notices.

Method differences remain explicit: the active Linear/UCB forward calculations omit an unused original loader field; the ridge reference penalizes every coefficient, including class intercepts; evaluation uses whole held-session folds and participant-balanced scoring. These choices do not establish original Julia/Float32 numerical parity or reproduction of the paper's broader hybrid, symbolic, lesion or transfer claims.
