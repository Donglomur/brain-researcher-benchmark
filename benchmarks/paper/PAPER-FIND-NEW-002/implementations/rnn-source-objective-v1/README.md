# Released Figure 4 RNN objective

This component recovers the original RNN training loss from the official Zenodo source and implements its mathematical reduction. It advances the current Figure 4 recovery task; it does not replace the retained Figure 2C calibration scorer or activate a paper-improvement benchmark. The canonical task and improvement contract remain unchanged.

`inspect_source.py` reads and authenticates only `code/RNN_seqmodel.ipynb` and `src/modules_simpleRNN.py` inside the official archive. It checks exact member size, ZIP CRC and SHA-256, then emits code cells and the loss function without running them. It neither extracts the figure data nor imports author code. Member authentication does not reverify the full archive checksum.

```sh
python3 inspect_source.py --archive /operator/source/sequenceFiltering.zip
```

The source `loss_mse` computes

\[
L = \frac1R\sum_{r=1}^{R}\frac{\sum_t\frac1D\sum_d[m_{rtd}(y_{rtd}-\hat y_{rtd})]^2}{\sum_t m_{rt0}}.
\]

The mask is squared with the residual. Trials receive equal weight after each trial's own denominator. The denominator uses mask channel zero, even when masks have multiple channels. The notebook uses an all-one mask with the same shape as its targets, so its loss is ordinary MSE across **all 32 sequence rows × 1,000 time steps × 500 outputs**. Every row remains in the reduction; the final 18 rows cannot be dropped as empty trials.

`rnn_loss.py` provides this arithmetic with bounded per-sequence temporaries and float64 accumulation. It accepts a singleton mask channel for the general author helper. Its notebook-panel entrypoint requires the full shape, all-one full-output mask, and zero targets on the final 18 rows. Target/output broadcasting, empty axes, nonfinite values, negative masks and zero denominators fail explicitly. Float64 arithmetic is mathematically faithful but is not a claim of bitwise parity with PyTorch float32. Only NumPy is required.

```sh
python3 rnn_loss.py --output-array /operator/frozen/output.npy \
  --target-array /operator/frozen/target.npy --mask-array /operator/frozen/mask.npy
```

This is an **operator arithmetic interface**, not a participant grading route. It does not authenticate the stochastic source realization, compare a candidate to an author baseline, calculate uncertainty or declare improvement. No protected targets or targets reconstructed from source were staged in this revision. File inputs must be numeric NPY arrays; pickles are disabled. Shape agreement alone cannot establish original target identity.

## Source findings and unresolved comparison

The source pins and exact cell locators are in [SOURCE_FINDINGS.json](SOURCE_FINDINGS.json). They resolve the loss formula and notebook reduction, while exposing discrepancies that prevent automatic benchmark activation:

- The notebook defines 14 contiguous five-pattern sequences from 18 patterns. It appends 18 randomly sampled sequence lists, but sets their actual training input and target values to **zero**. Those rows are null-input controls in this code; they are not presented scrambled stimuli. Both input and target branches do this. The 18 random lists are not seeded or saved.
- The original input matrix gives each of 18 disjoint patterns 20 units (360 of 500 units), sorted exponential amplitudes with scale 0.05. Its target scaling is 2 for the first seven stimulated units and 0.5 for the remaining 13. Identity readout weights are fixed; recurrent weights are trained. Target time step zero uses target input step zero; target step `i+1` uses input step `i`.
- The executable training call specifies **600 epochs**. `n_ep = 100` is unused by that call. The current contract's final-paper Methods evidence records **500 epochs**. This implementation preserves the discrepancy and does not choose one recipe for a paper comparison.
- The helper's default minibatch size is 32. With 32 rows, each epoch samples the whole panel in a random order and takes one optimizer step. The recurrent network adds fresh Gaussian noise during forward calls, including evaluation. NumPy, Python and PyTorch RNG seeds/states are not fixed in the notebook.
- Stored notebook logs print the initial loss and every tenth epoch using three decimal places, all displayed as `0.000`. These rounded strings are not exact zero, an exact baseline or a final post-update score. The helper records each loss **before** that epoch's optimizer step. The later output call uses updated weights and fresh noise, and no exact final fit score is saved by that cell.
- Panel L separately demonstrates trained `[1,2,3,4,5]` and untrained `[13,5,16,14,2]` inputs. Panel M uses matched `[5,6]` and unmatched `[2,6]` contexts. They plot mean responses; the notebook does not score them against prescribed targets. They remain companion demonstrations, not interchangeable MSE test sets.
- The previously recovered archive README describes 76 Figure 4 arrays for empirical panels AC, DE, F, HI and JK. It does not identify saved RNN weights, random states or training targets. This is an inventory limitation; no Figure 4 numerical payload was opened to claim that such evidence is absent.

Authenticating a complete original run requires resolving paper/notebook recipe differences, freezing the actual stochastic inputs/targets/initialization and all conditions, obtaining the author comparator under the accepted original protocol, and defining a justified paired effect/uncertainty rule. No new split, target predictor, data cohort or loss is introduced. This component is source recovery plus generated arithmetic controls, with no native preparation, model execution, performance claim or current-SOTA claim.

Source: [author archive, Zenodo 18726362](https://zenodo.org/records/18726362); [final article](https://doi.org/10.1016/j.neuron.2025.12.024).
