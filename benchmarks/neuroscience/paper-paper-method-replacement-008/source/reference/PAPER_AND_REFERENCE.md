# BaRISTA masked reconstruction: explicit reference choices

This adds executable reconstruction source for PAPER-paper-method-replacement-008.
It is a declared reimplementation track, not recovery of the authors' missing
reconstruction implementation or a reproduced result. No authentic data, model
weights, native training, inference, grading or scientific score was used here.

The primary paper is external arXiv2512.12135v1,
sections3.3, AppendixB/C/E.3, and the official source at commit
83b27375eba60e9eba9da4e7dd8fb283baace376. The external paper descriptor and original source inventory pin the paper and code.
The official repository is https://github.com/ShanechiLab/BaRISTA. Its released
downstream implementation supplies F/G and classification, not reconstruction H.
No absence claim extends to private or unpublished material.

## Architecture and initialization

The paper's H description combines five network layers with three hidden layers,
without widths or an unambiguous count of affine transformations. The selected
reference uses **five width entries and four affine maps**:64→64→64→64→64.
All four affine maps have bias and GELU; the first three have registered dropout
at0.1. This is a concrete interpretation with three hidden layers. It is not five
fully connected transformations, and its widths/bias/seed are not recovered facts.
Explicit alternate hidden widths, biases and seeds are supported by the config.
The final waveform head is64→512 with bias. H's registered dropout deliberately
avoids the released generic MLP's construction of a new Dropout during forward,
which would not be disabled by eval. No checkpoint-parity claim follows from this
correction. H remains trainable and receives the pretrained parameter-group rate.

Three initialization modes are explicit: random_all for the three random controls;
pretrained_FG_fresh_H with strict supplied F/G state and newly initialized H/mask;
and bound_FGH with strict F/G and H states plus an explicit64-element mask token.
Fresh H uses the native Linear initializer and a zero mask token with seed0.
Bound H must fit the selected executable architecture; this alone cannot prove
historical H, EMA-tokenizer provenance, or a specific pretraining run. The public
release advertises three encoding×channel-mask checkpoints; nine independent
pretraining combinations are not established. The source retains all nine model
slots and refuses missing F/G; it never duplicates three weights into nine slots.

The official F/G is instantiated, not substituted with an arbitrary producer
callback. All12 transformer layers,4 heads,d64, feedforward ratio4, GELU, RMSNorm,
dropout0.1 and native token geometry remain. Channel encoding maps to the released
coords configuration, parcel encoding to destrieux, and lobe encoding to lobes.
The five-block CNN is retained. Official time-space interleaving, RoPE positions,
and concatenated sequence lengths are forwarded. At a masked channel, raw values
are zeroed before F is called; the resulting token is replaced by M, then E is
added exactly once. H is pointwise, so applying it to the complete sequence before
selecting masked outputs introduces no cross-token H interaction.

## Training and query rules

The paper establishes20 finetuning epochs, target-token reconstruction, an
observed-token auxiliary branch, rates1e-3 for the pretrained network including H
and1e-2 for the new linear head, and one seed per held session. The implementation
uses per-token sum of squared512-sample errors for each loss branch. It does not
divide by512. Observed reconstruction uses F's observed tokens, before E/G/H.
The full train split alone enters the optimizer. Validation and test identities
remain required and disjoint, but no validation or test array enters fitting.

Declared discrete reference choices: seed0; batch32; all F/G/H/M and head
parameters trainable; no gradient accumulation; AdamW beta(.9,.999), epsilon1e-8,
weight decay.01; final epoch selected, with no early stopping. Epochs0..9 use
alpha1; epochs10..19 use .9,.8,…,0. A five-epoch linear learning-rate warmup uses
multipliers.2,.36,.52,.68,.84 for epochs0..4, then epoch5 uses1, epoch6 uses.99,
epoch7 uses.99², etc. This matches the released train.py's LinearLR(start_factor.2,
total_iters5), SequentialLR milestone5 and ExponentialLR(.99), stepped after
each epoch under the pinned Torch2.4.0 dependency. Reconstruction
freezing/batch choices and the alpha endpoint convention remain explicit
amendments, including the rates applied to the random controls. See
SCHEDULER_SOURCE.md for the implementation-level scheduler evidence.

Training masking uses the model's named pretraining masking scale as a declared
finetuning convention; random controls use channel masking. A seeded subset-sum
sampler chooses a whole-group subset nearest30% of channels, excludes empty/full
masks, prefers smaller counts at equal distance, and records the realized token
fraction each epoch. With12 patches per channel, channel and token fractions
agree. Unequal groups can prevent exactly30%; no exact historical sampler claim
is made. Parcel/lobe groups must match the supplied official metadata. The
session roster preserves all seven people,945 channels, all Table6 split counts,
nine encoding×masking pretrained variants and three random variants, in both
paper/data and paper/data/code access arms:168 training cells and22,680 complete
one-channel output matrices. These are cells/outputs of one paper project, not
22,680 benchmarks. Ordered native split identities still require source binding;
cardinality and disjointness alone do not recover the original split.

The test caller accepts C−1 observed channels and the fixed test identities. It
constructs an absent target slot itself; it cannot receive target-channel values.
It uses eval/no_grad, never fitting or updating on test queries. Training state
must belong to that exact model/person/access arm. Interrupted training is not
marked fitted. The export bridge writes complete per-channel matrices using the
existing primitive NPY writer and panel/request checks.

## Metrics and retained scope

The original reconstruction R² denominator, flattening and aggregation remain
unresolved. No synthetic R² formula is assigned the original label. The existing
complete scorer still reports its separately named full-support MSE with equal
channels within each person and equal weighting of seven people. Training loss,
MSE and original paper R² are three distinct quantities. A candidate's prediction
is not automatically a score or an improvement over the paper.

Classification and chronological classification remain unchanged through the accompanying
classification package. The broader paper still includes pretraining and EMA
tokenizer generation, multi-seed/spatial-scale analyses and interpretation. This
addition does not implement those missing experiments, supply original assets,
recover original H/R², or narrow the paper to reconstruction alone. The amended
reconstruction source is concretely executable once its dependencies and bound
inputs are provided, but the full paper project remains incomplete and unqualified.
