# Neuroformer source attributions

The original Neuroformer source was published by a-antoniades/Neuroformer at commit36ed94084628c253098d448048c980d3dea0050d with its MIT LICENSE (copyright2021 woanderer). That original license is retained. Repository-level MIT does not replace the applicable terms of identified third-party portions.

The following attributions accompany this distribution and every official-code B view produced by its source stager. Original scientific code is retained in full. Exactly simulation.py and utils.py carry added comment-only notices; their original bytes remain recoverable and are checked against the original SHA256 and Git-blob identities. No method repair is hidden in these notices.

* Jacob Gildenblat, vit-explain, MIT: attention_vis.py explicitly attributes VITAttentionGradRollout as an adaptation.
* Andrej Karpathy, minGPT, MIT: TrainerConfig/trainer and attention/model blocks have substantial source similarities. This ancestry is inferred, not a documented author claim.
* OpenAI, CLIP, MIT: model_neuroformer.convert_weights has substantial source similarity; ancestry is inferred.
* Peter Tatkowski, multidim-positional-encoding, MIT: get_emb is exact and2D/3D positional classes substantially match; ancestry is inferred.
* Alexander Rush, annotated-transformer, MIT: the positional-embedding class contains matching structure/comments; this notice is conservative and ancestry is inferred.
* HuggingFace Transformers, Apache-2.0: top_k_top_p_filtering in simulation.py/utils.py substantially matches the pinned generation example. Pertinent original source notices: Copyright2018 Google AI, Google Brain and Carnegie Mellon University Authors and the HuggingFace Inc. team; Copyright(c)2018 NVIDIA CORPORATION, all rights reserved. Inherited Neuroformer changes disable the one-dimensional assertion, add no_grad, change the default spelling and use two-dimensional indexing. This public distribution adds only prominent source-file notices. The exact donor tree contains no NOTICE-named file; the full Apache license is included.

Pinned donor identities and license files are recorded in UPSTREAM_RIGHTS.json at the package root. Each LICENSE-*.txt here is an exact primary-source license body. Neural datasets, paper text, pretrained weights and external runtime dependencies are not relicensed or bundled. Their separate admission and rights requirements remain open. Imported packages are dependencies, not copied package bodies in this source package.
