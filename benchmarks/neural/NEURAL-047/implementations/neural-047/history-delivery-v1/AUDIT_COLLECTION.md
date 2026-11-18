# Collecting saved observation-session audits

`audit_collection.py` adds an opt-in operator collection step to the existing
NEURAL-047 direct-observation and typed-viewer transports. It requires one audit
for every context, successful closure and response persistence, the complete
ordered hash chain, exact terminal response/request bindings, and consistent
response-byte accounting. Missing, duplicate, foreign, failed and modified
session artifacts are refused. The paired route retains the existing complete
worm/arm support and identical-observation requirement across the two modes.

The original collector supplies panel admission and the submission consumed by
the existing scorer. No target is opened during audit collection. An explicit
abstention remains a complete, unscored response; the existing target-last scorer
still avoids private-target access. Neither the endpoint nor the predictions,
underlying observations, source clock policy or metrics are changed.

For one condition, supply the existing frozen context list, result list and the
corresponding list of operator `--transcript-output` objects:

```sh
python3 -I -S -B audit_collection.py --mode typed_viewer \
  --panel panel.json --contexts contexts.json --responses responses.json \
  --audits audits.json --output audited-collection.json
```

For `--mode paired`, each context/result/audit file is a mapping containing
`direct_observation` and `typed_viewer` lists. Expected contexts must come from the
trusted operator's frozen preparation, not be reconstructed from participant
submissions. Extract `collection.submission` from a single-condition output, or
`collections[mode].collection.submission` from a paired output, for the existing
separate scorer.

This is saved-artifact integrity, not execution attestation. Hash-only intermediate
records cannot replay viewer requests or prove that a process ran; an actor able
to fabricate every trusted input could construct a self-consistent forgery.
Independent process closure, authenticated inputs, file isolation, reference
competence and scientific admission remain separate requirements. The viewer
continues to expose exact numeric histories with an SVG illustration and is not
an image-only vision condition. No model performance or native understanding is
established by generated controls.

Run the focused generated controls from this directory:

```sh
python3 -I -S -B test_audit_collection.py
```

The controls use the existing generated three-animal fixture. They cover complete
paired collection, missing/duplicate/cross-mode audits, unsuccessful closure,
chain corruption, prediction substitution, byte accounting and explicit
abstention without private-target access. Authentic animal identity, physical
clock, SAAV admission and a qualified full execution are still unresolved.
