# Modified upstream-file attribution

barista/models/TSEncoder2D.py is BaRISTA's adapted two-dimensional residual convolution encoder, including stride/checkpointing/normalization changes, from SimTS models/dilation.py (Apache2) and TS2Vec models/dilated_conv.py and models/encoder.py (MIT, copyright2022 Zhihan Yue). Its initializer cites torchvision densenet.py at309bd7a1512ad9ff0e9729fbdad043cb3472e4cb (BSD3, copyright2016 Soumith Chintala). Original source headers and full notices are retained.

barista/models/transformer.py adapts RMSNorm, rotate_half and rotary-position utilities from Transformers modeling_llama.py at8e164c5400b7b413c7b8fb32e35132001effc970, copyright2022 EleutherAI and HuggingFace Inc, under Apache2. It is BaRISTA's adapted implementation, not pristine upstream Llama. The original source body/header and complete Apache2 terms are preserved together with this file-specific notice.

The benchmark does not modify the computational bodies of these files. These attributions describe the upstream adaptations. Source-gate assembly and B staging must carry this notice and all accompanying full terms.
