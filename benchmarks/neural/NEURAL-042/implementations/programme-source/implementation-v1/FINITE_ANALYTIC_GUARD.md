# Finite T1 analytic outputs

The current `program/pac_tool.py::Tool.analytic` rejects a nonfinite filtered or
analytic row before returning a result. It also checks the complete row shape,
so a malformed one-element transform cannot silently broadcast across the epoch.
Finite input alone does not ensure finite convolution or FFT intermediates. Both
independent references already enforce finite filtered and analytic outputs.

The calculation, passbands, input ABI, output shape and finite-path operation
order are unchanged. In particular, the declared MI rule remains unchanged:
empty phase bins, a nonpositive sum of bin means, or a nonfinite sum make MI
undefined. This guard does not reinterpret that frozen estimator rule.

The current source-only runtime and central closure bindings are refreshed to
select the corrected primitive. Historical specifications and executed evidence
are retained. Existing `source_only`, `actual_qualification=false` and registered
runtime admission limits remain in force. A source correction does not establish
authentic EEG compatibility, full reference agreement or participant performance.

Run the eight generated boundary controls from the repository root:

```sh
python3 -I -B benchmarks/neural/NEURAL-042/implementations/programme-source/implementation-v1/tests/test_pac_tool.py
```

The controls need NumPy for array containers. Kernel and SciPy stages are explicit
test doubles so invalid intermediates are reproducible without changing a
production dependency. They exercise the actual current `Tool.analytic` function
and preserve the existing MI null cases. They do not qualify the required
NumPy 2.2.6 / SciPy 1.15.3 production environment or calculate physiological PAC.

Local semantic anchors are `../MATHEMATICS.md`,
`references/r1/numerics.py::analytic`, `references/r2/numeric.py::direct_filter`
and `references/r2/numeric.py::analytic_fourier`. No authentic recording or private target
was used for this correction.
