# PAPER-paper-method-050 initial conversion and diagnostics

This complete construction component converts pinned pyDANT MATLAB v7.3 `spikeInfo` references into identity-preserving numeric NPY files and computes paired full-population tracking diagnostics: directional session yield and independent PETH Fisher-z agreement. It enforces declared animal splits, matching-feature exclusions and unit/track integrity. It does not execute DANT or UnitMatch or establish true neuron identity.

Requires Python 3.11+, NumPy and h5py already available locally:

```sh
python3 evaluator.py convert /operator/spikeInfo_Nasha.mat /operator/converted/Nasha --dataset Nasha
python3 evaluator.py score /operator/protected_packet.json /operator/diagnostics.json
PYTHONDONTWRITEBYTECODE=1 python3 -m unittest discover -s tests -v
```

`--generated-engineering-control` is explicit fixture mode. Source mode validates the frozen inventory size/MD5 and requires all 13 datasets for scoring. The protected JSON packet is operator-controlled; declared receipt/settings lineage still requires audit. GPL-3.0 source and CC-BY-4.0 data obligations remain.

No authentic data, model run or native campaign was used. The all-pair mean diagnostic does not reconstruct the paper's day-specific, rate-filtered, three-method median/Friedman comparison or unmatched-distance/EMD endpoints. Native schema, biological animal metadata, protected-reference, resource and scientific qualification gates remain open.

See the [complete interface, source mappings and limits](../../docs/initial-evaluator-v1.md) and `provenance.json`. `tests/test_evaluator.py::packet` provides an executable generated packet example.
