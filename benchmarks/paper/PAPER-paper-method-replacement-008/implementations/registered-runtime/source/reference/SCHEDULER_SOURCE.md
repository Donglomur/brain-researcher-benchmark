# Source-derived scheduler correction

The existing pinned official `barista/train.py` supplies `get_lr_scheduler`:
LinearLR from0.2 to1 over5 iterations, then ExponentialLR gamma0.99 through
SequentialLR milestone5. `run_epoch` advances the scheduler after each training
epoch. The existing requirements file pins Torch2.4.0.

PyTorch2.4's implementation starts LinearLR at its initial factor and invokes
the next scheduler at epoch0 when a SequentialLR milestone is reached. The
corresponding closed-form epoch multipliers are .2,.36,.52,.68,.84,1,.99,.99²,… .
This inference follows the [versioned implementation](https://docs.pytorch.org/docs/2.4/_modules/torch/optim/lr_scheduler.html),
including LinearLR's closed form and SequentialLR.step's milestone branch.
The generic SequentialLR example is not used to determine the milestone value.
No local Torch installation or native scheduler execution was performed.

Alpha scheduling and the missing historical H remain separate declared reference choices.
