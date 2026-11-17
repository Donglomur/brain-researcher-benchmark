# Paired word support scorer

This task-local evaluator component computes the existing NEURAL-086 signed
finite-panel contrast while enforcing the original word and repeat support. It
does not change the registered task or activate a new campaign route.

The preceding `zuco/metrics.py:paired_contrast` checks that base and EEG-added
arms contain the same person/item cells. It does not check the original word
positions or repeats inside those cells. Consequently, it accepts a contrast
whose base arm contains word positions `{0,3}` and whose EEG-added arm contains
`{0,4}`. It also cannot detect both submitted arms dropping a word that was in
the frozen query census. Normal campaign preparation is intended to generate
the same support; the numerical evaluator previously relied on that upstream
property without checking it.

`score.py` joins every prediction against a separate protected census using
`(person, item, word_index, label, repetition_ordinal)`. Job-specific HMAC IDs
cannot serve as cross-arm keys because `splits.py:partition` includes the job
identity in each ID. Duplicate source occurrences, missing or extra occurrence
keys, mismatched source duration/block metadata and invalid probabilities are
rejected before arithmetic. An operator must supply the complete independently
frozen census, not derive it from the predictions. Repetition ordinals must be
unique within each person, exact item and source condition; the original-source
join still needs qualification.

The arithmetic remains: repeat losses within each source condition; equal two
conditions per original word; equal words per person/item; equal all exact
matched items per person; equal 18 people. Natural-log loss uses epsilon
`1e-6`, and a tie at probability `0.5` predicts TSR. The full signed cell matrix,
seed `194086`, 1,000 crossed person/item resamples, and fixed-prediction
interpretation remain unchanged. Word rows and repeats never become additional
biological people. A source census missing any person/item cell yields null
full-panel losses, difference and uncertainty, plus the observed matrix and
missing cells. An entirely unavailable secondary context follows the same rule.
It never substitutes a supported subset or another context for FFD.

The callable interface is:

```python
paired_contrast(base, plus, people, items, expected_support)
```

`base` and `plus` are lists of protected joined rows from already admitted
predictions. Each row has the five identity fields above and probability `p`.
An optional `id` is checked for uniqueness within each arm. If the census has
`block`, `duration_seconds` or `window_duration_ms`, both arms must preserve each
field exactly, including null. The optional metadata's presence must also match.
`people` is the ordered complete list of 18 opaque people; `items` is the ordered
complete nonempty exact shared-text set. `expected_support` has the same source
identity and metadata fields, with no prediction required. These axes retain
their declared order for source-compatible resampling. Output excludes row
labels, probabilities, word-level identities and class-specific occurrence
counts; it includes a hash of the canonical protected census and total counts.

For an operator-owned JSON packet containing exactly those five arguments:

```sh
python3 -I -B score.py --packet /external/protected/packet.json --output /external/results/contrast.json
```

No inference about origin or custody follows from the JSON file alone. The
existing campaign's global submission admission and target-last barrier must
precede this function. The function neither loads source recordings nor fits
models. Call it separately for the independent fixed reference (`D_R`), the
candidate (`D_C`), and each required control/context/representation. Never
combine these calls or relabel `D_C` as `D_R`. The six-dimension investigation
rubric remains separate and requires independently qualified raters.

All four access conditions are preserved. Direct observation, typed viewer,
and a distinct tool-assisted actor remain undelivered. Frozen programme source
remains available but unqualified. This numerical component supplies no new
transport or access mode, and no score establishes direct neural interpretation.
Fixed chronology still prevents causal reading-demand attribution.

Integration proposal: after independent review, the shared owner can replace
the N086 arithmetic call with this implementation, pass the frozen protected
source census independently of submitted predictions, and refresh current
source closures. Do not monkey-patch a live interpreter, change historical
manifests, or bypass the existing pinned score entry. The canonical bridge,
shared implementation and all task/understanding contracts remain untouched.

`test_score.py` uses generated controls only, including unequal repeat counts,
the old scorer's word-support counterexample, exact nonconstant uncertainty
parity, sign reversals, absent cells/contexts, duplicate axes/rows, metadata
misbinding and CLI failure behavior. This is software evidence, not authentic
data preparation, author qualification or a model result.
