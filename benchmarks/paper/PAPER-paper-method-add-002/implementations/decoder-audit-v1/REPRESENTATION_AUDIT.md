# Mixed components and readout inputs

`representation_audit.py` adds an optional connection between the original
score-packet components and the three named mixed-model readout tensors. The
existing linear audit authenticates each supplied representation's declared
content and coefficient-to-prediction arithmetic independently. Those checks
alone do not establish that the full, trial-only and time-only tensors come
from the components displayed in the same score packet.

The new audit reconstructs twelve trial-slicing outer products and one
time-slicing outer product from the packet's nonnegative exported factors. It
compares the trial sum, time product and their total to `mixed_trial_only`,
`mixed_time_only` and `mixed_slice12_1`, respectively. Every original 511 trial,
182 neuron and 150 bin position is checked, including positions outside the
decoder window. Ten-bin blocks bound additional reconstruction storage; the
already supplied representations and packet readers retain their own costs.
No factor rescaling, rotation, component reordering or new metric is introduced.
Products retain the supplied factor precision before float64 accumulation, as
in the preserved producer, including legitimate float32 factor exports.

This follows `construct` and `construct_single_component` in the pinned
[author tensor implementation](https://github.com/caycogajiclab/sliceTCA_paper/blob/62b0ca1267fe9d615111a193080577eda601687e/run_sliceTCA/core/classes.py#L89-L107)
and the named factor/reconstruction layout of the existing
[source producer](../source-producer-v1/README.md). The released
[Figure 2 code](https://github.com/caycogajiclab/sliceTCA_paper/blob/62b0ca1267fe9d615111a193080577eda601687e/figures/Fig2/code/Fig2.py#L217-L240)
decodes supplied reconstruction tensors. Checking their relation to supplied
factors closes an arithmetic gap; it does not recover historical model objects.

After constructing the existing hash-bound `AuditPacket` and its core
`bridge.Packet`, an operator can call:

```python
# Load representation_audit.py using an ordinary local module loader.
linkage = representation_audit.verify_mixed_representations(evidence, representations)
# Or include the unchanged complete original linear-readout verification:
report = representation_audit.verify_original_linear_result(evidence, prepared, representations)
```

The three mixed tensors must match the audit packet's representation pins and
remain immutable through verification. Core/plan identity is checked again.
The returned report binds the exact supplied factor arrays and preserves the
existing numerical tolerance (`rtol=atol=1e-10`). This is an arithmetic tolerance,
not a paper reproduction margin. The combined function checks linkage before
the original readout audit; it does not run decomposition or decoder fitting.

The original audit and score interfaces remain available. This optional original
factor/readout route adds no requirement to a novel candidate decoder. Trusted
input custody, actual fitting, historical component identity/gauge, source
comparators including LFADS, original masks/ranks/seeds, paper/code discrepancies,
and scientific reproduction/improvement decisions remain unresolved. No new
authentic observations were read or scored for this addition.

Run `python3 -B -m unittest -v test_representation_audit` in this directory using
the existing NumPy/SciPy environment. Generated controls use all 511 trials,
150 bins and 12+1 ranks with three features; a separate guard checks the public
182-feature requirement. They write no array artifacts and are not a paper run.
