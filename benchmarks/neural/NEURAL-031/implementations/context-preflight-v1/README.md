# Single-context participant preflight

This utility checks one NEURAL-031 prediction file using exactly the participant's
own exported `data.npz` and `manifest.json`. It needs neither the operator's full
store/support nor another mouse's context. This matters because another fold's
training labels contain the current mouse's answers.

```sh
python -I -B preflight.py \
  --input /input/data.npz \
  --manifest /input/manifest.json \
  --submission /output/predictions.json
```

Run it in the same allowed context, with Python and NumPy already available. It
prints a validation report to stdout and exits zero on acceptance, or prints an
error to stderr and exits two. It does not execute the submitted programme, write
predictions, fit a model, perform runtime probes, or grade a response.

The checker binds the supplied archive to the supplied manifest, checks the
original fold/view semantics, decodes only integer query identifiers, and requires
exact ordered coverage and finite nonnegative follow-up/baseline ratio predictions.
Zero is a permitted prediction; one means no predicted change. It uses the
existing pinned integer decoder from `runtime-qualification-v1/control.py` and
the numerical domain from `ratio-scoring-v2/endpoint.py`. No feature or training
label array is decoded. The other five archive member names and extents are
checked by the existing decoder.

An accepted preflight means the output agrees with these supplied public bytes.
It does not independently authenticate the original 27 source members, verify
the feature/label values inside the archive, prove programme identity or isolation,
or establish complete experimental execution. The operator must still authenticate
the retained source roster, collect all 40 outputs through
[`paired-delivery-v1`](../paired-delivery-v1/README.md), verify custody, and grade
the complete 774-request/731-observed-target panel. All requests, including ones
whose follow-up is unavailable, still require predictions. This utility never
receives the missing-target mask and cannot select scoring exclusions.

The current frozen executor remains bound to its historical scoring source.
Adding preflight does not retarget that executor, alter the equal-mouse metric,
or qualify a new runtime. No authentic-input, participant-performance, direct/viewer
understanding or scientific-readiness result is claimed.

Generated tests exercise both views and all 20 fold identities, malformed rows
and numerical values, swapped context identities, archive mutation, query-only
decoding, input access bounds, and fresh-process CLI validation. Run
`python -I -B test_preflight.py`. During source staging only,
`NEUROBENCH_SOURCE_ROOT` can select the read-only repository for the two pinned
dependencies; it does not select an input store or relax their hashes.
