# S11 panel binding for corrected finite-offset scores

This successor preserves the complete-support checks, arithmetic, axes and
undefined-state policy from [paired-panel-v1](../paired-panel-v1/README.md).
Only `DECODER_SHA256` changes to bind
[`source-decoder-v3/decoder.py`](../source-decoder-v3/decoder.py), SHA-256
`51f64a6f928856c804fb730ce8fe562026b71d6d859bf6784f09e581b11c7977`.
The prior panel module and its decoder-v2 binding remain unchanged.

The corrected decoder keeps the `/v2` record schemas and original signed
within-fold Pearson metric. The focused integration regression lives in
[`source-decoder-v3/test_numerics.py`](../source-decoder-v3/test_numerics.py): it
checks the actual decoder bytes and complete fold-array/mean join for generated
prediction scores. No full-panel source acquisition or scientific run occurs.

The receipt still reports supplied-input paired arithmetic only. It does not
authenticate source support, decide reproduction or superiority, introduce a
scalar aggregate, or turn these source components into a finished benchmark.
