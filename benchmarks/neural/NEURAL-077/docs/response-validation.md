# Current waveform response validation

The current direct-response collector enforces the existing JSON schema's trial
identity bounds: a string containing **1 through 48 characters**. It checks every
expected public ID before writing an output. Empty IDs and overlong IDs are
rejected, including pairs that would otherwise collide when written into the
collector's fixed-width Unicode array. A complete panel still contains exactly
400 distinct responses, returned in the fixed public order.

The [current source descriptor](../../../integrity/current-closures/neural077-direct-response/SOURCE_PINS.json)
binds the updated response validator and its tests. The package's original
`SOURCE_PINS.json` and historical README bodies remain unchanged; their statements
that the parser was unchanged describe that earlier source version. The current
descriptor retains the same ten source members, and only the validator and test
file have new pins. The schema, model prompt, probability rules, metrics and
scientific comparison conditions remain unchanged.

Run the current source controls from the repository root:

```sh
python3 -I -S -B -m unittest discover \
  -s benchmarks/neural/NEURAL-077/implementations/direct-response \
  -p 'test_collector_destination.py' -v
```

The nine controls authenticate the current descriptor and use invented responses
with a mocked NumPy writer. They check the length boundaries, complete-panel
coverage and refusal before output creation. They do not establish native NumPy
serialization, model transport isolation or scientific performance. The fixed
waveform packet's existing IDs contain 40 characters; no valid packet IDs or
benchmark conditions change.
