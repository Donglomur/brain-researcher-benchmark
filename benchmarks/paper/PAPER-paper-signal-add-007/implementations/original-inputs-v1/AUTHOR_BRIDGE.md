# Original-model probability bridge

`AuthorProbabilityBridge` connects an operator-supplied ICNet model to the existing
`predictions.run` interface. It exposes categorical probabilities before sampling,
so the existing converter can retain both sampled counts and expected counts.
This is source construction, not an authentic model replay or scientific result.

The [pinned author helper](https://github.com/fotisdr/ICNet/blob/7a631f1779662ee70b1819ac0c9ce0191bcaf158/src/ICNet_functions.py)
selects each animal's time input and decoder position, samples its distribution,
then optionally sorts columns by characteristic frequency. The bridge selects
the same original branch and keeps every column in original order. The existing
prediction converter supplies the separately declared PCG64 sampling policy;
TensorFlow sampling parity is not claimed.

The [pinned configuration](https://github.com/fotisdr/ICNet/blob/7a631f1779662ee70b1819ac0c9ce0191bcaf158/DNN/config.yaml)
defines 2,048 preceding audio samples, audio scaling of 0.04 and time scaling of
1/36,000. The bridge requires an explicit context record for every
animal/sound/trial, with exact sample bytes and the operator's alignment-evidence
identity. It has no padding default and does not infer the unlabeled source
measurement-time columns. Time values remain in seconds. Copying audio before
normalization preserves the shared public waveform.

The trusted operator supplies an already authenticated model, a context-provider
callable and a binding containing the exact source revision/helper digest,
checkpoint digest, context-alignment evidence digest and measurement-time-mapping
evidence digest. The context provider receives the four-field case identity and
returns that identity, a float32 `left_context_pa` vector of length 2,048,
`samples_sha256` of its C-order little-endian float32 bytes, and
`alignment_evidence_sha256`. Correctly formatted digests do not authenticate
the external evidence; reviewing and freezing those inputs remains required.

```python
predictor = AuthorProbabilityBridge(authenticated_model, context_provider, binding)
predictions.run(public_manifest, new_destination, predictor,
                predictor_sha256=reviewed_operator_source_sha256, seed=explicit_seed)
```

`predictor_sha256` retains the existing operator-wrapper meaning; it is not a
transitive dependency or checkpoint attestation. The binding and all inputs must
be retained in the operator's separately qualified source closure. No checkpoint,
TensorFlow installation or author source is bundled. The optional branch factory
supports meaningful generated tests; using a replacement factory in an actual
run requires independent qualification.

Only export is streamed in blocks. The author model can allocate the complete
22,784 × 512 × 5 probability output (233,308,160 bytes at float32), plus its own
working memory. This component does not establish an inference memory envelope.
It preserves all 28 cases and both trials through the existing caller; it does
not supply original development data, LNP replay, historical context/mask/crop
proof, a scalar paper comparison or a protected execution environment.

Generated checks use a tiny broadcast-backed fake branch with the full original
output shape and the real probability conversion boundary. They check complete
stream support, original-column identity, both trial times, calibrated input
scaling, mandatory context, invalid source/layout/output refusals and preservation
of public audio. They do not test TensorFlow, checkpoint compatibility or native
numerical equivalence. Run `python -B tests/test_author_bridge.py -v` from this
component directory; it requires the same NumPy dependency as the existing code.
