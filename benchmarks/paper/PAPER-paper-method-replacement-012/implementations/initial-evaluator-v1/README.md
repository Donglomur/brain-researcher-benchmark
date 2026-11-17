# NuCLR Bugeon initial evaluator

An owner-side readout for supplied neuron embeddings: complete identity and split
checks, train-only scaling, source logistic regression, validation-only checkpoint
selection, pooled classification metrics, and matched context-ablation comparison.
The three Bugeon exposure/split panels and EI, five-subclass, and 11-class label
families remain distinct.

Requires existing Python 3.10+, NumPy and scikit-learn. The optional author
`resample` branch also requires imbalanced-learn; it fails if unavailable. No
installation, data download, pickle loading or NuCLR training is performed.

From this directory:

```sh
PYTHONDONTWRITEBYTECODE=1 python3 -m unittest discover -s tests -v
python3 evaluator.py owner_packet.json --output result.json
python3 evaluator.py context.json --ablated ablated.json --output comparison.json
```

The packet's labels, splits and provenance must remain owner-controlled. Read the
[full task interface, source mapping and limits](../../docs/initial-evaluator-v1.md)
before preparing a packet. Every result remains an engineering component result:
authentic acquisition, paper-era split equivalence, repeated-cell linkage, rights,
native reference runs, protected evaluation and scientific qualification are open.
Generated controls are not paper reproduction evidence.
