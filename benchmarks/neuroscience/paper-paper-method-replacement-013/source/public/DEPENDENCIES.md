# Dependency status

The newly authored preparation/scoring and generated controls use Python3.12.8 and NumPy2.2.6. The supplied Dockerfile is unbuilt; its base digest and wheel lock remain unqualified. The prospective ridge helper uses NumPy and runs no fit at import. No authentic arrays, Torch model, weights or scientific algorithm were executed.

The exact original requirements.txt and setup_env.sh are supplied unchanged in B. Requirements records Torch1.13.1, torchvision0.14.1, NumPy1.22.4, SciPy1.9.3, pandas2.0.3, scikit-learn1.2.0, OmegaConf2.3.0, gdown4.6.0 and timm0.5.4. It also contains nonportable local build URLs, including torchmetrics. The shell recipe has unpinned installs and a commented Python3.11 environment. These are provenance, not a validated dependency lock; do not install the legacy list as though qualification were complete.

The native model additionally needs independently qualified original inputs, tokenizer/configuration, initial/own trained checkpoint, hardware and isolation. Original scripts may automatically download if the data directory is missing and use W&B; those paths were never invoked. Data/model downloads and empirical execution are not enabled by this package. Original MIT source license is supplied. Raw-data and manuscript redistribution rights remain unqualified.
