# Original 2ACDC reward-prediction arithmetic

This component recovers and implements the seven-symbol RNN/LSTM reward score
used by the author's prediction callers. It also records source conflicts that
prevent treating every deposited notebook as a publication-equivalent baseline.
The existing Figure 2f evaluator and the canonical task/contract remain unchanged.

**The source quantity named accuracy is reward recall.** Its numerator is the
number of next-symbol reward positions at which the predicted argmax is reward;
its denominator is the number of next-symbol reward positions. It does not
penalize false reward predictions. An always-reward prediction therefore obtains
1.0 on every sequence admitted by this arithmetic kernel. This is a generated
software counterexample, not a trained-model result or a paper improvement.
The additional false-positive and next-symbol counts in the output are clearly
marked diagnostics; they do not replace the original endpoint.

## Use

Python 3.11+, standard library only:

```sh
python reward_score.py INPUT.json NEW_REPORT.json
```

Input has exactly two fields: `test_symbols`, a list of integer symbols, and
`logits`, a list of seven-number rows. Supply one prediction row for **every**
input symbol, as the source caller does. Row `t` predicts symbol `t+1`.
The final row has no observed next target and cannot contribute a hit. The
smallest symbol index wins an argmax tie. Nonfinite values, booleans, incomplete
trials and changed encodings are rejected; output is created exclusively.

The original near and far trials each contain 23 symbols and one reward:

```text
near: 1 1 1 1 1 1 2 2 2 2 1 1 1 4 6 1 1 1 5 5 1 1 0
far:  1 1 1 1 1 1 3 3 3 3 1 1 1 4 4 1 1 1 5 6 1 1 0
```

Reward predictions are eligible at zero-based input positions 13 for a near
trial and 18 for a far trial, offset by the trial start. The kernel accepts any
positive number of complete original trials because source callers use different
trial counts. This is **not** permission to change a particular model's trial
count, training exposure or evaluation population. The kernel does not train a
model, generate historical splits, select runs, aggregate a panel, or prove
prediction provenance. It reads explicitly supplied scorer inputs only and is
not a participant-facing evaluator or protected final-target transport.

## What was recovered

All source identities are bound in [source_manifest.json](source_manifest.json).
The immutable repository revision is
`c1d1788b54c737efe24402e02762eee10da0d0d7`. Eleven model notebooks, the Extended
Data 9c plotting notebook, README, and transformer helpers were inspected as
text. Git blob hashes authenticate the recovered bytes against the complete
repository tree. No source notebook was executed. Repository presence and a
pinned revision do not prove publication-era execution lineage.

The [sigmoid RNN](https://github.com/sprustonlab/OSM_Paper_Figures/blob/c1d1788b54c737efe24402e02762eee10da0d0d7/ext_data_figures/ext_data_fig_9/ext_data_fig_9_a_b_c/Vanilla_RNN_Sigmoid.ipynb)
cell 0 supplies the scoring kernel. The same reward-index intersection occurs
in the seven-symbol LSTM and other vanilla RNN callers. The RNN zeroes hidden
state at the start of each forward call; the custom LSTM zeroes both hidden and
cell states. Training and testing are separate forward calls. Source training
generates a new trial-type sequence per epoch and splits its first half from its
second half. It is not one fixed historical train/test sequence.

The recovered configurations are source observations, not an admitted run census:

| Caller | Trials train / test | Training epochs | Declared seeds | Saved final epoch |
| --- | ---: | ---: | --- | ---: |
| RNN sigmoid | 50 / 50 | 1200 | 200–211 | 1190 |
| RNN ReLU | 20 / 20 | 60 | 0–9 | 59 |
| RNN polynomial | 50 / 50 | 500 | 200–247 | 490 |
| RNN softmax | 50 / 50 | 500 | 200–247 | 490 |
| LSTM correlation penalty | 50 / 50 | 2000 | 0–3 | 1990 |
| LSTM L1 | 50 / 50 | 3000 | 10–13 | 2990 |
| LSTM dropout | 50 / 50 | 3000 | 0–7 | 2990 |
| Figure 4 LSTM without regularization | 50 / 50 | 2000 | 10–13 | 1990 |

Saved checkpoints occur when `epoch % save_each == 0`, after that epoch's update.
The table therefore does not relabel the last saved score as an evaluation after
all declared updates. RNN sigmoid/polynomial/softmax and ReLU reject trial draws
unless both trial types appear more than once among `trials[:-1]`; the inspected
LSTM callers apply a related condition to the training half. These conditions
must be preserved by any source-protocol rerun and must not be reconstructed as
balanced sampling. Seed ranges alone do not recover historical arrays.

## Consequential source conflicts

1. The [Extended Data LSTM without regularization](https://github.com/sprustonlab/OSM_Paper_Figures/blob/c1d1788b54c737efe24402e02762eee10da0d0d7/ext_data_figures/ext_data_fig_9/ext_data_fig_9_a_b_c/LSTM_no_reg_with_cell_state.ipynb)
   has the original seven-symbol trials commented out. Its active trials contain
   27 position-specific symbols, while the score still treats symbol 6 as reward.
   That active code cannot be admitted as the original sensory task. The
   [Figure 4 LSTM notebook](https://github.com/sprustonlab/OSM_Paper_Figures/blob/c1d1788b54c737efe24402e02762eee10da0d0d7/fig_4/fig_4_f_Batch_LSTM_no_reg.ipynb)
   retains the seven-symbol trials, but choosing it does not establish that it
   produced the published Extended Data 9a values.
2. Both no-regularization trainers declare four simulations. The deposited
   Extended Data 9c correlation plot contains twenty no-regularization cell-state
   values. These correlation values are **not prediction scores**, and cannot
   establish the prediction panel or its run identities. Other plotting cells
   select runs by final training loss. Such selections are distinct from the
   declared number of launched simulations.
3. The recovered Hebbian notebook uses 26-symbol trials with different reward
   structure. It is outside this seven-symbol arithmetic kernel. The transformer
   has its own chunk/context and scoring caller. In
   [trainer.py](https://github.com/sprustonlab/OSM_Paper_Figures/blob/c1d1788b54c737efe24402e02762eee10da0d0d7/fig_4/fig_4_f_transformer/mingpt/trainer.py),
   `look_back=4` with `test_dataset[start:i+1]` supplies up to **five** input
   symbols, including the current symbol. `Trainer_with_test.run` returns
   reward **error rate**, despite downstream names containing `accuracy`.
   Its reward mask accepts symbols 6 or 7, but the deposited generator uses
   only 0–6. Reversing the error-rate direction or treating this as all-token
   accuracy would change the source result. These are findings about this
   pinned code, not a resolution of its relationship to the published figure.
4. The transformer samples its twenty-trial training pattern before the
   per-repetition seed call and reuses it across ten repetitions. It then
   samples 1,000 length-100 chunks per repetition and generates a separate
   100-trial test sequence. A replacement that redraws the training pattern
   within each seeded repetition changes the deposited protocol. Run-level
   independence and historical RNG state remain separate questions.

## Qualification boundary

Reproducing original findings and exceeding them are separate outcomes. This
component enables exact arithmetic checks for the recovered seven-symbol
prediction route; it does not establish either outcome. The original Figure 2f
reproduction component remains available separately. No historical result is
promoted by this addition.

Remaining requirements are publication-bound Extended Data 9a numeric outputs,
complete model/run identities and selections, source-equivalent generator and
split replay with authentic baseline execution, model-specific contexts and
budgets, companion descriptive analyses, and a justified comparison protocol.
The reward-recall ceiling counterexample also requires a scientific decision
about what evidence can support a meaningful improvement claim. It must not be
hidden by replacing the endpoint with the diagnostic next-symbol count.

Paper+data and paper+data+author-code conditions must expose the same admitted
cases and retain separate scores. Author-code recovery here improves the second
condition's possible source package; it does not deliver a complete paired
participant package, nor justify supplying hidden evaluation labels to a solver.

Generated tests cover the next-symbol shift, reward support, final-row exclusion,
argmax ties, false-positive degeneracy and rejection of changed task encodings.
They establish software behavior only. No native data preparation, fitting,
inference, candidate trial, or scientific result was run.
