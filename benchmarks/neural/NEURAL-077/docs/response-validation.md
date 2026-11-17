# Current waveform response validation

The current direct-response collector enforces the existing JSON schema's trial
identity bounds: a string containing **1 through 48 characters**. It checks every
expected public ID before writing an output. Empty IDs and overlong IDs are
rejected, including pairs that would otherwise collide when written into the
collector's fixed-width Unicode array. A complete panel still contains exactly
400 distinct responses, returned in the fixed public order.

The operator manifest's `development_ids` field must be an **ordered JSON array**
containing those 400 IDs. Objects, strings and other JSON types are refused before
array construction or output creation, even when iterating them would yield 400
distinct strings. Submission response order may differ; the collector returns
the completed predictions in the manifest's array order.

The [current source descriptor](../../../integrity/current-closures/input-neural077/SOURCE_PINS.json)
binds the response validator and its tests. It identifies the
[preceding identity-length repair](../../../integrity/current-closures/neural077-direct-response/SOURCE_PINS.json)
separately. That descriptor, the package's original `SOURCE_PINS.json` and historical
README bodies remain unchanged. Their statements about an unchanged parser apply
to their respective earlier versions. The current descriptor retains the same ten
source members; only the validator and test file have new pins relative to its
predecessor. The response schema, model prompt, probability rules, metrics and
scientific comparison conditions remain unchanged.

Run the current source controls from the repository root:

```sh
python3 -I -S -B -m unittest discover \
  -s benchmarks/neural/NEURAL-077/implementations/direct-response \
  -p 'test_collector_destination.py' -v
```

These controls authenticate the current descriptor and use invented responses
with a mocked NumPy writer. They check the identity-array type, length boundaries,
complete-panel coverage and refusal before output creation. They do not establish
native NumPy serialization, model transport isolation or scientific performance.
