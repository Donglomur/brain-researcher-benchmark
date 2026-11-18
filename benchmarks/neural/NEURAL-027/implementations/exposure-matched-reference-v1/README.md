# Reference with the same displayed training examples

The existing direct packets can show a predeclared subset of training examples. Comparing their responses with the predecessor's reference trained on **all** training packets would confound access mode with training exposure. This component fits the existing Gaussian reference using exactly the examples displayed in each frozen public packet. It supplies complete predictions for the same queries and preserves the existing paired neural versus movement/position comparison.

This is a numerical reference component. It does not run an LLM, enforce participant isolation, establish native interpretation, qualify authentic input, or demonstrate reference competence. The original source intake, cohort, phase, alignment, regional-pooling, protected-evaluation and scientific-admission holds remain. No benchmark, outcome, cohort or metric is added.

## Input and recipe

`reference.py` accepts only the public `neural.json` and `movement_position.json` produced by the [direct packet builder](../direct-packets-v1/README.md). It has no private-binding, target-file, original-array or full-training input argument. It checks the reviewed delivery implementation before import; that implementation also checks the unchanged initial evaluator. Both conditions must have matching class order, demonstration condition, ordered query identities and displayed demonstration labels.

For nonempty demonstrations, the comparator calls the unchanged diagonal-Gaussian `Reference` API. Normalization, centroids and variance are fitted only on displayed examples; the original uniform class prior and variance floor remain. Adding or reordering queries cannot change the fit. The unused feature modality passed through the predecessor's API is empty; no other-arm measurements are introduced.

The direct builder requires equal demonstration counts in every training mouse/class cell. If there are `M` mice, `K` classes and `n` displayed examples per cell, the predecessor assigns each example weight `1/(M K n)`. Pooling these public examples into one internal fitting group assigns `1/(K M n)`, the same weight. The pool identifier is an API adapter, **not** an inferred animal or a scoring unit. Original animal IDs remain exclusively in the operator-private binding and the existing scorer. This equivalence depends on authentic builder output: public class balance alone cannot prove the hidden mouse balance or original provenance.

A zero-demonstration packet selects explicit uniform probabilities over the frozen classes. It does not silently substitute extra training examples or claim a competent learned comparator. Missing or unequal class support in nonempty demonstrations is rejected.

## Use and scoring

Python 3.11 and the existing NumPy dependency are required. No new package installation is needed.

```sh
python3 reference.py \
  --public-dir /exchange/n027-direct \
  --output-dir /operator/n027-matched-reference
```

The output directory must be new and disjoint from the public input directory. It receives `neural-responses.json`, `movement_position-responses.json` and `reference.json`. The report binds both public packets and response lists by the existing canonical JSON digest. These are engineering identity checks, not source-authenticity proofs.

Pass those response files to the unchanged direct collector with its frozen private binding. That collector verifies public content against the operator's original hashes, grades the original held stimulus labels, and retains mouse/phase aggregation and paired uncertainty. Keep the comparator's results separate from any direct-participant results. This component itself neither reads the gold answers nor scores outputs.

## Validation

Ten generated controls cover a numerical Gaussian oracle; equivalence to the predecessor's mouse/class weighting; query noninterference; separation of observation conditions; explicit zero-example behavior; incomplete demonstration rejection; paired coverage/exposure failures; target-field rejection; numerical overflow rejection; and the CLI-to-existing-collector path. Finite inputs that overflow the reference arithmetic fail without emitting invalid predictions. These controls exercise constructed values and establish software behavior only. They do not establish performance on the original dataset.

```sh
python3 -I -B tests/test_reference.py -v
```

This test command needs explicit enrollment when the component is integrated. Existing historical component tests are unchanged; a successful construction test is not an authentic benchmark run or a delivered participant programme mode.
